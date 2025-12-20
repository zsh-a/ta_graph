from typing import List, Dict, Any, Optional, Union, Literal
import math
from ..logger import get_logger

logger = get_logger(__name__)

# Use dicts or objects. Since data comes from CCXT ohlcv list, let's accept that.
# OHLCV format: [timestamp, open, high, low, close, volume]
INDEX_HIGH = 2
INDEX_LOW = 3
INDEX_CLOSE = 4

def get_tick_size(symbol: str) -> float:
    symbol_upper = symbol.upper()
    if "BTC" in symbol_upper:
        return 0.1
    elif "ETH" in symbol_upper:
        return 0.01
    else:
        return 0.0001

def calculate_entry_price(
    rule: Dict[str, Any],
    ohlcv: List[List[float]],
    current_price: float,
    symbol: str = "UNKNOWN"
) -> float:
    tick_size = get_tick_size(symbol)
    
    # rule['barIndex']: 0 = most recent (last element), -1 = previous
    # Convert to array index
    bar_index = rule.get('barIndex', 0)
    array_index = len(ohlcv) - 1 + bar_index
    
    if array_index < 0 or array_index >= len(ohlcv):
        # Fallback to current price if index invalid
        return current_price
        
    bar = ohlcv[array_index]
    base_price = current_price
    
    rtype = rule.get('type')
    if rtype == 'bar_high':
        base_price = bar[INDEX_HIGH]
    elif rtype == 'bar_low':
        base_price = bar[INDEX_LOW]
    elif rtype == 'bar_close':
        base_price = bar[INDEX_CLOSE]
    elif rtype == 'current_price':
        base_price = current_price
        
    offset = rule.get('offset')
    if offset is None:
        offset = 1 if rtype in ['bar_high', 'bar_low'] else 0
        
    if rtype == 'bar_low':
        return base_price - (offset * tick_size)
    else:
        # Default add offset (bar_high)
        return base_price + (offset * tick_size)


def calculate_stop_loss_price(
    rule: Dict[str, Any],
    ohlcv: List[List[float]],
    entry_price: float,
    is_buy: bool,
    symbol: str = "UNKNOWN"
) -> float:
    tick_size = get_tick_size(symbol)
    base_price = entry_price # Default
    
    rtype = rule.get('type')
    
    if rtype in ['bar_low', 'bar_high']:
        bar_index = rule.get('barIndex')
        if bar_index is None:
            raise ValueError(f"barIndex required for {rtype}")
        array_index = len(ohlcv) - 1 + bar_index
        if array_index < 0 or array_index >= len(ohlcv):
             raise ValueError(f"Invalid bar index {bar_index}")
             
        bar = ohlcv[array_index]
        base_price = bar[INDEX_LOW] if rtype == 'bar_low' else bar[INDEX_HIGH]
        
    elif rtype in ['pattern_low', 'pattern_high']:
        start = rule.get('patternStartBar')
        end = rule.get('patternEndBar')
        if start is None or end is None:
            raise ValueError(f"pattern start/end required for {rtype}")
            
        start_idx = len(ohlcv) - 1 + start
        end_idx = len(ohlcv) - 1 + end
        
        min_idx = max(0, min(start_idx, end_idx))
        max_idx = min(len(ohlcv)-1, max(start_idx, end_idx))
        
        slice_data = ohlcv[min_idx : max_idx+1]
        if not slice_data:
             raise ValueError("Invalid pattern range")
             
        if rtype == 'pattern_low':
            base_price = min(x[INDEX_LOW] for x in slice_data)
        else:
            base_price = max(x[INDEX_HIGH] for x in slice_data)
            
    elif rtype in ['swing_low', 'swing_high']:
        start = rule.get('swingStartBar')
        end = rule.get('swingEndBar')
        if start is None or end is None:
            raise ValueError(f"swing start/end required for {rtype}")
            
        start_idx = len(ohlcv) - 1 + start
        end_idx = len(ohlcv) - 1 + end
        
        min_idx = max(0, min(start_idx, end_idx))
        max_idx = min(len(ohlcv)-1, max(start_idx, end_idx))
        
        slice_data = ohlcv[min_idx : max_idx+1]
        if not slice_data:
             logger.warning(f"Empty slice_data for {rtype} in {symbol}. Range: {min_idx}:{max_idx+1}")
             raise ValueError(f"Invalid {rtype} range: no data found in the specified bar range [{start}, {end}]")

        if rtype == 'swing_low':
            base_price = min(x[INDEX_LOW] for x in slice_data)
        else:
            base_price = max(x[INDEX_HIGH] for x in slice_data)
            
    # Apply Offset
    offset_amount = 0.0
    if rule.get('offsetPercent') is not None:
        offset_amount = base_price * (rule.get('offsetPercent') / 100.0)
    elif rule.get('offset') is not None:
        offset_amount = rule.get('offset') * tick_size
        
    if is_buy:
        return base_price - offset_amount
    else:
        return base_price + offset_amount


def calculate_take_profit_price(
    rule: Dict[str, Any],
    ohlcv: List[List[float]],
    entry_price: float,
    stop_loss_price: float
) -> float:
    risk = abs(entry_price - stop_loss_price)
    rtype = rule.get('type')
    
    if rtype == 'risk_multiple':
        multiple = rule.get('riskMultiple', 1.5)
        if entry_price > stop_loss_price: # Buy
            return entry_price + (risk * multiple)
        else: # Sell
            return entry_price - (risk * multiple)
            
    elif rtype == 'measured_move':
        start = rule.get('measuredMoveBarStart')
        end = rule.get('measuredMoveBarEnd')
        if start is None or end is None:
             raise ValueError("measured move start/end required")
             
        start_idx = len(ohlcv) - 1 + start
        end_idx = len(ohlcv) - 1 + end
        
        min_idx = max(0, min(start_idx, end_idx))
        max_idx = min(len(ohlcv)-1, max(start_idx, end_idx))
        
        slice_data = ohlcv[min_idx : max_idx+1]
        if not slice_data:
             raise ValueError(f"Invalid measured move range: no data found in the specified bar range [{start}, {end}]")

        swing_high = max(x[INDEX_HIGH] for x in slice_data)
        swing_low = min(x[INDEX_LOW] for x in slice_data)
        impulse_height = swing_high - swing_low
        
        if entry_price > stop_loss_price: # Buy
            return entry_price + impulse_height
        else:
            return entry_price - impulse_height
            
    elif rtype == 'key_level':
        return rule.get('keyLevel', entry_price) # Fallback?
        
    return entry_price
