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

from ..trading.exchange_client import get_client, ExchangeClient
from ..utils.event_bus import get_event_bus

logger = get_logger(__name__)
bus = get_event_bus()


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


def execute_buy_order(
    client: ExchangeClient,
    symbol: str,
    amount: float,
    entry_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    leverage: int = 20
) -> TradeResult:
    """
    Execute a buy (LONG) order using unified client
    
    Args:
        client: ExchangeClient instance
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
        # Place order using unified client
        order_type = "limit" if entry_price else "market"
        
        order = client.place_order(
            symbol=symbol,
            side="buy",
            order_type=order_type,
            amount=amount,
            price=entry_price,
            leverage=leverage,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit
        )
        
        logger.info(f"✅ Buy order executed: {order.id}")
        logger.info(f"   Price: {order.price}, Filled: {order.filled}")
        
        return TradeResult(
            success=True,
            order_id=order.id,
            executed_price=order.price,
            executed_amount=order.filled
        )
        
    except Exception as e:
        logger.error(f"Buy order failed: {e}")
        return TradeResult(success=False, error=str(e))


def execute_sell_order(
    client: ExchangeClient,
    symbol: str,
    amount: float,
    entry_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    leverage: int = 20
) -> TradeResult:
    """
    Execute a sell (SHORT) order using unified client
    """
    try:
        order_type = "limit" if entry_price else "market"
        
        order = client.place_order(
            symbol=symbol,
            side="sell",
            order_type=order_type,
            amount=amount,
            price=entry_price,
            leverage=leverage,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit
        )
        
        logger.info(f"✅ Sell order executed: {order.id}")
        
        return TradeResult(
            success=True,
            order_id=order.id,
            executed_price=order.price,
            executed_amount=order.filled
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
            
            logger.info(f"✅ Trade saved to database: {trade.id}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to save trade to database: {e}")

@observe()
def execute_trade(state: AgentState) -> dict:
    """Execute Trade"""
    bus.emit_sync("node_start", {"node": "execution"})
    logger.info("🚀 Executing Trades...")
    execution_plans = state.get("execution_results", [])
    decisions = state.get("decisions", [])
    warnings = list(state.get("warnings", []))  # Get existing warnings or empty list
    
    # Track execution metadata
    execution_metadata = {
        "decisions_received": len(decisions),
        "plans_received": len(execution_plans),
        "trades_executed": 0
    }
    
    # CRITICAL: Check if decisions were made but no execution plans created
    if decisions and len([d for d in decisions if d.get("operation") != "Hold"]) > 0 and not execution_plans:
        error_msg = (
            f"🚨 CRITICAL: {len(decisions)} trade decision(s) made but NO execution plans created. "
            f"This indicates a failure in the risk assessment or execution planning stage."
        )
        logger.critical(error_msg)
        warnings.append(error_msg)
    
    if not execution_plans:
        logger.info("No execution plans to process.")
        return {
            "execution_results": [],
            "execution_metadata": execution_metadata,
            "warnings": warnings
        }
    
    results = []
    trading_mode = os.getenv("TRADING_MODE", "dry-run").lower()
    is_live = trading_mode == "live"
    
    # Initialize exchange client if in live mode
    client = None
    if is_live:
        try:
            exchange_name = os.getenv("EXCHANGE_NAME", "bitget")
            client = get_client(exchange_name)
            logger.info(f"✓ Connected to {exchange_name} exchange")
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
        if is_live and client:
            # Real execution
            try:
                if side == "LONG":
                    result = execute_buy_order(
                        client=client,
                        symbol=symbol,
                        amount=amount,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        leverage=leverage
                    )
                elif side == "SHORT":
                    result = execute_sell_order(
                        client=client,
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
                    execution_metadata["trades_executed"] += 1
                
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
            execution_metadata["trades_executed"] += 1
        
        results.append(plan)
    
    filled_count = len([r for r in results if r.get('execution_status') == 'FILLED'])
    logger.info(f"\n✅ Execution complete: {filled_count} filled")
    logger.info(f"📊 Metadata: {execution_metadata}")
    
    return {
        "execution_results": results,
        "execution_metadata": execution_metadata,
        "warnings": warnings
    }
