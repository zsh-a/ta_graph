"""
Enhanced Execution Node with Real Order Execution
Migrated from Super-nof1.ai/lib/trading/unified-trading.ts and lib/ai/run.ts
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import ccxt
from langfuse import observe

from ..state import AgentState
from ..logger import get_logger
from ..database import get_session, ModelType, OperationType, SymbolType
from ..database.trading_history import create_trading_record
from ..database.account_manager import update_model_trade_stats

logger = get_logger(__name__)

class TradeResult:
    """Trade execution result"""
    def __init__(self, success: bool, order_id: Optional[str] = None, 
                 executed_price: Optional[float] = None, 
                 executed_amount: Optional[float] = None,
                 error: Optional[str] = None):
        self.success = success
        self.order_id = order_id
        self.executed_price = executed_price
        self.executed_amount = executed_amount
        self.error = error

def get_exchange_client(exchange_name: str = "bitget") -> ccxt.Exchange:
    """
    Initialize exchange client with API credentials
    Supports: bitget, binance
    """
    api_key = os.getenv("EXCHANGE_API_KEY")
    secret = os.getenv("EXCHANGE_SECRET")
    passphrase = os.getenv("EXCHANGE_PASSPHRASE")  # For bitget
    
    if not api_key or not secret:
        raise ValueError("Exchange API credentials not configured")
    
    sandbox = os.getenv("TRADING_MODE", "dry-run").lower() != "live"
    
    if exchange_name == "bitget":
        exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': secret,
            'password': passphrase,
            'options': {'defaultType': 'swap'},  # Futures
            'sandbox': sandbox
        })
    elif exchange_name == "binance":
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'options': {'defaultType': 'future'},
            'sandbox': sandbox
        })
    else:
        raise ValueError(f"Unsupported exchange: {exchange_name}")
    
    return exchange

def execute_buy_order(
    exchange: ccxt.Exchange,
    symbol: str,
    amount: float,
    entry_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    leverage: int = 20
) -> TradeResult:
    """
    Execute a buy (LONG) order
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., BTC/USDT:USDT)
        amount: Amount in base currency
        entry_price: Entry price (None for market order)
        stop_loss: Stop loss price (optional)
        take_profit: Take profit price (optional)
        leverage: Leverage multiplier
        
    Returns:
        TradeResult with execution details
    """
    try:
        # Set leverage
        try:
            exchange.set_leverage(leverage, symbol)
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")
        
        # Place main order
        order_type = "limit" if entry_price else "market"
        order = exchange.create_order(
            symbol=symbol,
            type=order_type,
            side="buy",
            amount=amount,
            price=entry_price,
            params={'stopLoss': {'triggerPrice': stop_loss}} if stop_loss else {}
        )
        
        logger.info(f"✅ Buy order placed: {order['id']}")
        logger.info(f"   Price: {order.get('price', 'market')}, Amount: {order.get('filled', 0)}")
        
        # Set SL/TP if provided (some exchanges require separate orders)
        if stop_loss:
            try:
                # For Bitget, use stopLossPrice in params
                sl_order = exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side='sell',
                    amount=amount,
                    params={
                        'stopPrice': stop_loss,
                        'reduceOnly': True
                    }
                )
                logger.info(f"✅ Stop loss set at {stop_loss}")
            except Exception as e:
                logger.error(f"Failed to set stop loss: {e}")
        
        if take_profit:
            try:
                tp_order = exchange.create_order(
                    symbol=symbol,
                    type='limit',
                    side='sell',
                    amount=amount,
                    price=take_profit,
                    params={'reduceOnly': True}
                )
                logger.info(f"✅ Take profit set at {take_profit}")
            except Exception as e:
                logger.error(f"Failed to set take profit: {e}")
        
        return TradeResult(
            success=True,
            order_id=order['id'],
            executed_price=order.get('price') or order.get('average'),
            executed_amount=order.get('filled', amount)
        )
        
    except Exception as e:
        logger.error(f"Buy order failed: {e}")
        return TradeResult(success=False, error=str(e))

def execute_sell_order(
    exchange: ccxt.Exchange,
    symbol: str,
    amount: float,
    entry_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    leverage: int = 20
) -> TradeResult:
    """
    Execute a sell (SHORT) order
    """
    try:
        # Set leverage
        try:
            exchange.set_leverage(leverage, symbol)
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")
        
        # Place main order
        order_type = "limit" if entry_price else "market"
        order = exchange.create_order(
            symbol=symbol,
            type=order_type,
            side="sell",
            amount=amount,
            price=entry_price,
            params={'stopLoss': {'triggerPrice': stop_loss}} if stop_loss else {}
        )
        
        logger.info(f"✅ Sell order placed: {order['id']}")
        
        # Set SL/TP if provided
        if stop_loss:
            try:
                sl_order = exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side='buy',
                    amount=amount,
                    params={
                        'stopPrice': stop_loss,
                        'reduceOnly': True
                    }
                )
                logger.info(f"✅ Stop loss set at {stop_loss}")
            except Exception as e:
                logger.error(f"Failed to set stop loss: {e}")
        
        if take_profit:
            try:
                tp_order = exchange.create_order(
                    symbol=symbol,
                    type='limit',
                    side='buy',
                    amount=amount,
                    price=take_profit,
                    params={'reduceOnly': True}
                )
                logger.info(f"✅ Take profit set at {take_profit}")
            except Exception as e:
                logger.error(f"Failed to set take profit: {e}")
        
        return TradeResult(
            success=True,
            order_id=order['id'],
            executed_price=order.get('price') or order.get('average'),
            executed_amount=order.get('filled', amount)
        )
        
    except Exception as e:
        logger.error(f"Sell order failed: {e}")
        return TradeResult(success=False, error=str(e))

def save_trade_to_database(
    plan: Dict[str, Any],
    result: TradeResult,
    model_type: ModelType = ModelType.Qwen
) -> None:
    """Save successful trade to database"""
    try:
        # Map symbol string to SymbolType enum
        symbol_str = plan.get('symbol', 'BTC')
        symbol_enum = SymbolType[symbol_str] if hasattr(SymbolType, symbol_str) else SymbolType.BTC
        
        # Map operation to OperationType
        operation_str = plan.get('operation', 'Buy')
        operation_enum = OperationType[operation_str] if hasattr(OperationType, operation_str) else OperationType.Buy
        
        # Create trading record
        db = get_session()
        try:
            trade = create_trading_record(
                symbol=symbol_enum,
                operation=operation_enum,
                amount=int(result.executed_amount or plan.get('amount', 0)),
                pricing=int(result.executed_price or plan.get('entry_price', 0)),
                risk_amount=plan.get('risk_amount'),
                prediction=plan.get('prediction'),
                db=db
            )
            
            # Update trade stats
            update_model_trade_stats(
                model=model_type,
                db=db
            )
            
            logger.info(f"✅ Trade saved to database: {trade.id}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to save trade to database: {e}")

@observe()
def execute_trade(state: AgentState) -> dict:
    """
    Execute trades based on approved execution plans from risk node
    
    Supports:
    - Real execution via CCXT
    - Simulation mode
    - Order management (SL/TP)
    - Database persistence
    """
    logger.info("🚀 Executing Trades...")
    execution_plans = state.get("execution_results", [])
    
    if not execution_plans:
        logger.info("No execution plans to process.")
        return {"execution_results": []}
    
    results = []
    trading_mode = os.getenv("TRADING_MODE", "dry-run").lower()
    is_live = trading_mode == "live"
    
    # Initialize exchange if in live mode
    exchange = None
    if is_live:
        try:
            exchange_name = os.getenv("EXCHANGE_NAME", "bitget")
            exchange = get_exchange_client(exchange_name)
            logger.info(f"✓ Connected to {exchange_name} ({'LIVE' if not exchange.sandbox else 'SANDBOX'})")
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            logger.warning("Falling back to simulation mode")
            is_live = False
    
    for plan in execution_plans:
        # Skip non-approved plans
        if plan.get("status") != "APPROVED":
            logger.info(f"⏭️  Skipping {plan.get('symbol')}: {plan.get('reason', 'Not Approved')}")
            results.append(plan)
            continue
        
        operation = plan.get("operation")
        symbol = plan.get("trading_symbol")  # e.g., BTC/USDT
        side = plan.get("side")  # LONG/SHORT
        amount = plan.get("amount")
        entry_price = plan.get("entry_price")
        stop_loss = plan.get("stop_loss")
        take_profit = plan.get("take_profit")
        leverage = plan.get("leverage", 20)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 {side} {symbol}")
        logger.info(f"   Amount: {amount:.4f}")
        logger.info(f"   Entry: ${entry_price:.2f}")
        logger.info(f"   Stop Loss: ${stop_loss:.2f}")
        logger.info(f"   Take Profit: ${take_profit:.2f}")
        logger.info(f"   Leverage: {leverage}x")
        logger.info(f"   Mode: {'LIVE' if is_live else 'SIMULATION'}")
        logger.info(f"{'='*60}\n")
        
        # Execute based on mode
        if is_live and exchange:
            # Real execution
            try:
                if side == "LONG":
                    result = execute_buy_order(
                        exchange=exchange,
                        symbol=symbol,
                        amount=amount,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        leverage=leverage
                    )
                elif side == "SHORT":
                    result = execute_sell_order(
                        exchange=exchange,
                        symbol=symbol,
                        amount=amount,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        leverage=leverage
                    )
                else:
                    logger.error(f"Unknown side: {side}")
                    continue
                
                # Update plan with results
                plan["execution_id"] = result.order_id
                plan["execution_status"] = "FILLED" if result.success else "FAILED"
                plan["executed_price"] = result.executed_price
                plan["executed_amount"] = result.executed_amount
                plan["error"] = result.error
                
                # Save to database if successful
                if result.success:
                    save_trade_to_database(plan, result)
                
            except Exception as e:
                logger.error(f"Execution error: {e}")
                plan["execution_status"] = "FAILED"
                plan["error"] = str(e)
        else:
            # Simulation mode
            logger.info("  [SIMULATION] Order placed successfully")
            plan["execution_id"] = f"sim_{symbol.replace('/', '_')}_{int(datetime.now().timestamp())}"
            plan["execution_status"] = "FILLED"
            plan["executed_price"] = entry_price
            plan["executed_amount"] = amount
            
            # Save to database even in simulation
            result = TradeResult(
                success=True,
                order_id=plan["execution_id"],
                executed_price=entry_price,
                executed_amount=amount
            )
            save_trade_to_database(plan, result)
        
        results.append(plan)
    
    logger.info(f"\n✅ Execution complete: {len([r for r in results if r.get('execution_status') == 'FILLED'])} filled")
    return {"execution_results": results}
