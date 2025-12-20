import ccxt
import pandas as pd
import os
import datetime
from typing import List
from langfuse import observe
from ..state import AgentState
from ..utils.event_bus import get_event_bus
from ..logger import get_logger
from ..utils.timeframe_config import get_data_limit
from ..utils.brooks_chart import save_brooks_chart, get_swing_points  # Use Brooks chart renderer

logger = get_logger(__name__)

# --- Helper Functions ---

def calculate_ema(prices: List[float], period: int = 20) -> List[float]:
    """Calculate EMA using pandas"""
    return pd.Series(prices).ewm(span=period, adjust=False).mean().tolist()

def generate_bar_data_table(df: pd.DataFrame, count: int = 30, swings: list[dict] | None = None) -> str:
    """Generate text table for LLM with Brooks-style features and Swing Points"""
    if df is None or len(df) == 0:
        return "## No market data available"
    
    recent = df.tail(count + 20).copy() # Get extra context for H1/L1 calculation
    
    # Calculate body size and bar type
    recent['body_size'] = (recent['close'] - recent['open']).abs()
    recent['total_range'] = (recent['high'] - recent['low'])
    recent['body_pct'] = (recent['body_size'] / recent['total_range'] * 100).fillna(0)
    recent['bar_type'] = recent.apply(
        lambda r: ("Trend" if r['body_pct'] > 50 else "Doji"), axis=1
    )
    
    # EMA features
    recent['dist_to_ema'] = recent['close'] - recent['ema20']
    
    # Brooks H1/L1 counting (Simplified heuristic)
    # H1/H2: In a bull trend/pullback, first/second bar with high > prev high
    # L1/L2: In a bear trend/pullback, first/second bar with low < prev low
    recent['h_count'] = 0
    recent['l_count'] = 0
    h_counter = 0
    l_counter = 0
    
    for i in range(1, len(recent)):
        # High count logic
        if recent.iloc[i]['high'] > recent.iloc[i-1]['high']:
            h_counter += 1
        else:
            # Check if this is a "reset" (e.g. strong bear bar or new low in pullback)
            if recent.iloc[i]['close'] < recent.iloc[i]['open'] and recent.iloc[i]['body_pct'] > 60:
                h_counter = 0
        
        # Low count logic
        if recent.iloc[i]['low'] < recent.iloc[i-1]['low']:
            l_counter += 1
        else:
            if recent.iloc[i]['close'] > recent.iloc[i]['open'] and recent.iloc[i]['body_pct'] > 60:
                l_counter = 0
        
        recent.iloc[i, recent.columns.get_loc('h_count')] = h_counter
        recent.iloc[i, recent.columns.get_loc('l_count')] = l_counter

    # Subset to the requested count
    display_df = recent.tail(count)
    total_bars = len(display_df)
    
    lines = []
    lines.append(f"## Bar Data (Most Recent {count} Bars)")
    lines.append("Color Legend: Bull=Green, Bear=Red")
    lines.append("")
    lines.append("Idx | Type | Body% | High | Low | Close | EMA Dist | H/L Count | Swing | Volume")
    lines.append("----|------|-------|------|-----|-------|----------|-----------|-------|-------")
    
    for i in range(total_bars):
        row = display_df.iloc[i]
        bar_idx = i - total_bars + 1
        
        trend = "Bull" if row['close'] >= row['open'] else "Bear"
        type_str = f"{trend} {row['bar_type']}"
        
        ema_dist_str = f"{row['dist_to_ema']:.2f}"
        
        hl_count = ""
        if row['h_count'] > 0: hl_count += f"H{int(row['h_count'])}"
        if row['l_count'] > 0: 
            if hl_count: hl_count += "/"
            hl_count += f"L{int(row['l_count'])}"
            
        vol_str = f"{row['volume']:.0f}"
        if row['volume'] > 1e6: vol_str = f"{row['volume']/1e6:.1f}M"
        elif row['volume'] > 1e3: vol_str = f"{row['volume']/1e3:.0f}K"
            
        swing_label = ""
        if swings:
            # Find if this row's index (i) matches any swing point's internal index
            # Note: generate_bar_data_table works on display_df which is recent.tail(count)
            # We need to map row index to the original df index used by get_swing_points
            actual_idx = row.name # This is the timestamp index or integer index
            # For simplicity, let's pass swings that are already subsetted or use bar_idx
            for s_idx, s in enumerate(swings):
                if s['idx'] == row.name or (isinstance(row.name, int) and s['idx'] == row.name):
                    swing_label = f"S{s_idx+1}"
                    break

        lines.append(f"{bar_idx:3} | {type_str:10} | {row['body_pct']:5.1f}% | {row['high']:.2f} | {row['low']:.2f} | {row['close']:.2f} | {ema_dist_str:8} | {hl_count:9} | {swing_label:5} | {vol_str}")
        
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
    df = pd.DataFrame(ohlcv)
    df.columns = pd.Index(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Calculate EMA20
    df['ema20'] = calculate_ema(df['close'].tolist(), period=20)
    
    # Calculate Swing Points for identifying legs (Measured Moves)
    # Convert df to use integer index temporarily for swing detection consistency
    df_swing = df.copy().reset_index()
    swings = get_swing_points(df, window=7) # Sensitivity of 7 bars for significant swings
    
    # 4. Generate Artifacts
    bar_data_table = generate_bar_data_table(df, swings=swings)
    
    # Detail Focus Chart (Last 30 bars for high-detail analysis)
    focus_chart_path = save_brooks_chart(
        df=df,
        symbol=symbol,
        timeframe=timeframe,
        chart_type='primary',
        annotate_bars=True,
        show_volume=True,
        focus_num_bars=30,
        swings=swings
    )
    
    # Primary Context Chart (150 bars)
    chart_path = save_brooks_chart(
        df=df,
        symbol=symbol,
        timeframe=timeframe,
        chart_type='primary',
        annotate_bars=True,
        show_volume=True,
        num_bars_display=120, # Slightly reduced context for better bar width
        swings=swings
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
        "chart_image_path": chart_path,
        "focus_chart_image_path": focus_chart_path,
        "swing_points": swings  # Store for backend logic
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
    
    # Calculate metrics for frontend display
    price_change_24h = 0.0
    if len(ohlcv) >= 25:
        price_24h_ago = float(ohlcv[-25][4])  # Close price 24 bars ago
        price_change_24h = ((float(current_price) - price_24h_ago) / price_24h_ago) * 100
    
    volume_24h = sum([float(bar[5]) for bar in ohlcv[-24:]]) if len(ohlcv) >= 24 else 0.0
    
    bus.emit_sync("market_update", {
        "symbol": symbol,
        "price": float(current_price),
        "time": int(pd.Timestamp(df.index[-1]).timestamp()),
        "timeframe": timeframe
    })
    
    # NEW: Emit detailed market data complete event for frontend display
    bus.emit_sync("market_data_complete", {
        "node": "market_data",
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": len(ohlcv),
        "current_price": float(current_price),
        "price_change_24h": price_change_24h,
        "volume_24h": volume_24h
    })

    # Persistence
    run_id = state.get("run_id")
    if run_id:
        from ..database.persistence_manager import get_persistence_manager
        try:
            with get_persistence_manager() as pm:
                pm.record_observation(
                    run_id=run_id,
                    price=float(current_price),
                    bar_data=bars[-30:],  # Store recent history
                    indicators={
                        "ema20": float(ema20_val) if not pd.isna(ema20_val) else None,
                        "timeframe": timeframe,
                        "chart_path": chart_path
                    }
                )
        except Exception as e:
            logger.warning(f"⚠️  Failed to record market observation: {e}")

    return {
        "market_data": market_data_dict,
        "market_states": [market_data_dict],  # List format for consistency
        "bars": bars,
        "current_bar": bars[-1] if bars else None,
        "current_price": float(current_price),
        "chart_image_path": chart_path,
        "focus_chart_image_path": focus_chart_path
    }
