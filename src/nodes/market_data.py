import io
import ccxt
import pandas as pd
import mplfinance as mpf
import os
import datetime
from typing import List, Dict, Any, Optional
from langfuse import observe
from ..state import AgentState
from ..utils.event_bus import get_event_bus
from ..logger import get_logger
from ..utils.timeframe_config import get_data_limit
from ..utils.brooks_chart import save_brooks_chart  # Use Brooks chart renderer

logger = get_logger(__name__)

# --- Helper Functions ---

def calculate_ema(prices: List[float], period: int = 20) -> List[float]:
    """Calculate EMA using pandas"""
    return pd.Series(prices).ewm(span=period, adjust=False).mean().tolist()

def generate_bar_data_table(df: pd.DataFrame, count: int = 30) -> str:
    """Generate text table for LLM"""
    # Defensive checks
    if df is None or len(df) == 0:
        return "## No market data available"
    
    if count is None:
        count = 30
    
    recent = df.tail(count).copy()
    lines = []
    lines.append("## Bar Data (Most Recent 30 Bars)")
    lines.append("")
    lines.append("Bar Index | Open | High | Low | Close | Trend | EMA20 Relation | Volume")
    lines.append("----------|------|------|-----|-------|-------|----------------|-------")
    
    # We iterate from oldest to newest in the slice, but label them relative to current (0)
    # Actually, let's list them chronological: oldest first, with index.
    # index: 0 = current (last row), -1 = previous.
    
    total_bars = len(recent)
    # We want to display from -N to 0
    
    for i in range(total_bars):
        row = recent.iloc[i]
        # Calculate index: if we have 30 bars, i=29 is the last one (0). i=0 is -29.
        bar_idx = i - total_bars + 1
        
        trend = "Bull" if row['close'] >= row['open'] else "Bear"
        ema_rel = "N/A"
        if not pd.isna(row['ema20']):
            if row['close'] > row['ema20']: ema_rel = "Above"
            elif row['close'] < row['ema20']: ema_rel = "Below"
            else: ema_rel = "At"
            
        vol_str = f"{row['volume']:.0f}"
        if row['volume'] > 1e6: vol_str = f"{row['volume']/1e6:.1f}M"
        elif row['volume'] > 1e3: vol_str = f"{row['volume']/1e3:.0f}K"
            
        lines.append(f"Bar {bar_idx} | {row['open']:.2f} | {row['high']:.2f} | {row['low']:.2f} | {row['close']:.2f} | {trend} | {ema_rel} | {vol_str}")
        
    return "\n".join(lines)

# --- Node Logic ---

@observe()
def fetch_market_data(state: AgentState) -> dict:
    """
    Fetch market data, calculate indicators, and generate chart.
    Populates 'market_states' list for the strategy node.
    """
    logger.info("Fetching market data...")
    bus = get_event_bus()
    bus.emit_sync("node_start", {"node": "market_data"})
    symbol = state.get("symbol", "BTC/USDT")
    interval = state.get("primary_timeframe", "15m")
    
    # Convert timeframe to CCXT-compatible format
    # E.g., '60m' -> '1h', '240m' -> '4h', '1440m' -> '1d'
    if interval.endswith('m'):
        minutes = int(interval[:-1])
        if minutes >= 1440:  # >= 1 day
            days = minutes // 1440
            timeframe = f"{days}d"
        elif minutes >= 60:  # >= 1 hour
            hours = minutes // 60
            timeframe = f"{hours}h"
        else:
            timeframe = interval  # Keep as is for minutes
    else:
        timeframe = interval  # Already in correct format
    
    logger.info(f"Using timeframe: {timeframe} (from {interval})")
    
    # 使用配置管理器获取数据量
    limit = get_data_limit()
    
    # 1. Initialize Exchange (Binance Public)
    exchange = ccxt.bitget() 
    
    # 2. Fetch Data
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    if not ohlcv:
        logger.error(f"No data fetched for {symbol}")
        return {"messages": [("system", f"Failed to fetch data for {symbol}")]}

    # 3. Process Data
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Calculate EMA20
    df['ema20'] = calculate_ema(df['close'].tolist(), period=20)
    
    # 4. Generate Artifacts
    bar_data_table = generate_bar_data_table(df)
    
    # Use Brooks-style chart renderer
    chart_path = save_brooks_chart(
        df=df,
        symbol=symbol,
        timeframe=timeframe,
        chart_type='primary',
        annotate_bars=True,
        show_volume=True
    )
    
    current_price = df['close'].iloc[-1]
    ema20_val = df['ema20'].iloc[-1]
    
    # 5. Return state updates (plain dict format)
    market_data_dict = {
        "symbol": symbol,
        "timeframe": timeframe,
        "ohlcv": ohlcv,
        "current_price": float(current_price),
        "ema20": float(ema20_val) if not pd.isna(ema20_val) else None,
        "bar_data_table": bar_data_table,
        "chart_image_path": chart_path
    }
    
    # Convert OHLCV to simple bar format for state
    bars = [
        {
            "timestamp": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5])
        }
        for row in ohlcv
    ]
    
    bus.emit_sync("market_update", {
        "symbol": symbol,
        "price": float(current_price),
        "time": int(df.index[-1].timestamp()),
        "timeframe": timeframe
    })

    return {
        "market_data": market_data_dict,
        "market_states": [market_data_dict],  # List format for consistency
        "bars": bars,
        "current_bar": bars[-1] if bars else None,
        "current_price": float(current_price),
        "chart_image_path": chart_path
    }
