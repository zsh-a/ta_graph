from typing import List, Dict, Any, Optional
import os
from langfuse import observe
from ..state import AgentState
from ..logger import get_logger
from ..utils.price_calculator import calculate_entry_price, calculate_stop_loss_price, calculate_take_profit_price

logger = get_logger(__name__)

class RiskConfig:
    def __init__(self):
        mode = os.getenv("TRADING_MODE", "dry-run").lower()
        self.trading_mode = "live" if mode == "live" else "dry-run"
        self.max_position_size_usdt = float(os.getenv("MAX_POSITION_SIZE_USDT", 5000))
        self.max_leverage = float(os.getenv("MAX_LEVERAGE", 20))
        self.daily_loss_limit_percent = float(os.getenv("DAILY_LOSS_LIMIT_PERCENT", 2.0))
        # Default fallback risk if not specified in decision
        self.default_risk_percent = 1.0

@observe()
def assess_risk(state: AgentState) -> dict:
    """
    Risk Node:
    - Validates decisions
    - Calculates exact prices
    - Calculates position sizing
    - Checks account-level risk limits
    - Integrates with database for real account info
    """
    logger.info("Assessing Risk...")
    decisions = state.get("decisions", [])
    if not decisions:
        logger.info("No decisions to process.")
        return {"execution_results": []}

    market_states = { m['symbol']: m for m in state.get("market_states", [])}
    
    # Get real account info from database if available
    try:
        from ..database.trading_history import get_account_performance
        from ..database import get_session
        
        db = get_session()
        try:
            performance = get_account_performance(db=db)
            available_cash = performance.availableCash
            total_equity = performance.totalCashValue
            logger.info(f"💰 Account: ${available_cash:.2f} available / ${total_equity:.2f} total")
        except Exception as e:
            logger.warning(f"Could not fetch account from DB: {e}, using state defaults")
            available_cash = state.get("account_info", {}).get("available_cash", 1000.0)
            total_equity = available_cash
        finally:
            db.close()
    except Exception as e:
        # Fallback to state if database not available
        logger.warning(f"Database not available: {e}")
        available_cash = state.get("account_info", {}).get("available_cash", 1000.0)
        total_equity = available_cash
    
    # Mock daily pnl (should come from account info)
    daily_pnl_percent = state.get("account_info", {}).get("daily_pnl_percent", 0.0)

    config = RiskConfig()
    execution_plans = []

    for decision in decisions:
        op = decision.get("operation")
        symbol = decision.get("symbol")
        
        if op == "Hold":
            logger.info(f"Decision for {symbol}: HOLD")
            # We can still add it to execution results to log it
            execution_plans.append({
                "symbol": symbol,
                "operation": "Hold",
                "reason": decision.get("wait_reason", "Hold strategy")
            })
            continue
            
        # Get Market Data (OHLCV)
        m_state = market_states.get(symbol) # Or match by symbol name if partial
        # Symbols might mismatch (BTC vs BTC/USDT), handled loosely here or needs mapping
        # Assuming exact match or first available for now if simple
        if not m_state:
             # Try finding "BTC/USDT" for "BTC"
             key = next((k for k in market_states if symbol in k), None)
             if key: m_state = market_states[key]
        
        if not m_state:
            logger.error(f"Market data not found for {symbol}")
            continue
            
        ohlcv = m_state['ohlcv']
        current_price = m_state['current_price']
        
        # Extract Rules
        if op == "Buy":
             rules = decision.get("buy")
             is_buy = True
        elif op == "Sell":
             rules = decision.get("sell")
             is_buy = False
        else:
            continue
            
        if not rules:
            logger.warning(f"No rules provided for {op} {symbol}")
            continue

        try:
            # 1. Calculate Prices
            entry_price = calculate_entry_price(rules['entryPriceRule'], ohlcv, current_price, symbol)
            stop_loss = calculate_stop_loss_price(rules['stopLossPriceRule'], ohlcv, entry_price, is_buy, symbol)
            take_profit = calculate_take_profit_price(rules['takeProfitPriceRule'], ohlcv, entry_price, stop_loss)
            
            # Validation
            if is_buy and stop_loss >= entry_price:
                 logger.warning(f"Invalid Buy SL: {stop_loss} >= {entry_price}")
                 continue
            if not is_buy and stop_loss <= entry_price:
                 logger.warning(f"Invalid Sell SL: {stop_loss} <= {entry_price}")
            
            # 2. Calculate Position Size based on Risk Percent
            # riskPercent is the percentage of equity to risk on this trade
            risk_percent = rules.get("riskPercent", config.default_risk_percent) / 100.0
            risk_amount_usd = total_equity * risk_percent  # Risk in USD
            
            # Distance from entry to stop loss (in USD per unit)
            price_risk_per_unit = abs(entry_price - stop_loss)
            
            # How many units can we buy/sell?
            max_amount_by_risk = risk_amount_usd / price_risk_per_unit if price_risk_per_unit > 0 else 0
            
            # Maximum notional value allowed
            max_notional = config.max_position_size_usdt
            max_amount_by_size = max_notional / entry_price if entry_price > 0 else 0
            
            # Use the smaller of risk-based or size-based
            amount = min(max_amount_by_risk, max_amount_by_size)
            
            logger.info(f"   Risk: {risk_percent*100:.1f}% of ${total_equity:.2f} = ${risk_amount_usd:.2f}")
            logger.info(f"   Price Risk: ${price_risk_per_unit:.2f} per unit")
            logger.info(f"   Amount: {amount:.4f} (risk-based: {max_amount_by_risk:.4f}, size-cap: {max_amount_by_size:.4f})")
            
            # 3. Risk Checks
            leverage = config.max_leverage  # Fixed leverage
            position_value_usdt = amount * entry_price
            required_margin = position_value_usdt / leverage
            
            # Balance Check
            if required_margin > available_cash:
                # Resize to max available
                amount = (available_cash * 0.95 * leverage) / entry_price
                position_value_usdt = amount * entry_price
                required_margin = position_value_usdt / leverage
                logger.warning(f"Insufficient funds, resizing to: {amount:.4f} units")
                
            # Max Position Size Check  
            if position_value_usdt > config.max_position_size_usdt:
                amount = config.max_position_size_usdt / entry_price
                position_value_usdt = config.max_position_size_usdt
                logger.warning(f"Position size capped at ${config.max_position_size_usdt}")
            
            #
            # Daily Loss Check
            if daily_pnl_percent <= -config.daily_loss_limit_percent:
                logger.error("Daily loss limit reached. BLOCKING trade.")
                execution_plans.append({
                    "symbol": symbol,
                    "operation": "Hold",
                    "reason": "Risk Control: Daily Loss Limit"
                })
                continue
                
            # Approved: Create execution plan
            trading_symbol = f"{symbol}/USDT:USDT" if symbol not in m_state.get('symbol', '') else symbol
            
            execution_plans.append({
                "status": "APPROVED",
                "symbol": symbol,
                "trading_symbol": trading_symbol,
                "operation": op,
                "side": "LONG" if is_buy else "SHORT",
                "amount": amount,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "leverage": leverage,
                "risk_amount": risk_amount_usd,
                "required_margin": required_margin,
                "reason": decision.get("rationale", "AI-generated trade"),
                "prediction": decision.get("prediction")
            })
            
            logger.info(f"✅ {op} {symbol}: Amount={amount:.4f}, Entry=${entry_price:.2f}, SL=${stop_loss:.2f}, TP=${take_profit:.2f}")
            continue
            
        except Exception as e:
            logger.error(f"Error calculating details for {symbol}: {e}")
            continue

    return {"execution_results": execution_plans}
