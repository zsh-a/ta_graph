"""
Enhanced Execution Node with Real Order Execution
Migrated from Super-nof1.ai/lib/trading/unified-trading.ts and lib/ai/run.ts
"""

from typing import Any
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
    success: bool
    order_id: str | None
    executed_price: float | None
    executed_amount: float | None
    error: str | None

    def __init__(self, success: bool, order_id: str | None = None, 
                 executed_price: float | None = None, 
                 executed_amount: float | None = None,
                 error: str | None = None):
        self.success = success
        self.order_id = order_id
        self.executed_price = executed_price
        self.executed_amount = executed_amount
        self.error = error


def execute_buy_order(
    client: ExchangeClient,
    symbol: str,
    amount: float,
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
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
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
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
    plan: dict[str, Any],
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
    execution_plans = state.get("execution_results") or []
    decisions = state.get("decisions") or []
    warnings_list = list(state.get("warnings") or [])  # Get existing warnings or empty list
    
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
        warnings_list.append(error_msg)
    
    if not execution_plans:
        logger.info("No execution plans to process.")
        return {
            "execution_results": [],
            "execution_metadata": execution_metadata,
            "warnings": warnings_list
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

        if not symbol or not amount or side is None:
            logger.warning(f"⚠️  Incomplete plan for {symbol}: symbol={symbol}, amount={amount}, side={side}")
            plan["execution_status"] = "FAILED"
            plan["error"] = "Incomplete execution plan"
            results.append(plan)
            continue
        
        # Proper typing for mypy/pyright
        symbol_val: str = str(symbol)
        amount_val: float = float(amount)
        side_val: str = str(side)
        entry_val: float | None = float(entry_price) if entry_price is not None else None
        sl_val: float | None = float(stop_loss) if stop_loss is not None else None
        tp_val: float | None = float(take_profit) if take_profit is not None else None
        lev_val: int = int(leverage)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 {side_val} {symbol_val}")
        logger.info(f"   Amount: {amount_val:.4f}")
        logger.info(f"   Entry: ${entry_val:.2f}" if entry_val else "   Entry: MARKET")
        logger.info(f"   Stop Loss: ${sl_val:.2f}" if sl_val else "   Stop Loss: NONE")
        logger.info(f"   Take Profit: ${tp_val:.2f}" if tp_val else "   Take Profit: NONE")
        logger.info(f"   Leverage: {lev_val}x")
        logger.info(f"   Mode: {'LIVE' if is_live else 'SIMULATION'}")
        logger.info(f"{'='*60}\n")
        
        # Execute based on mode
        if is_live and client:
            # Real execution
            try:
                if side_val.lower() == "buy":
                    result = execute_buy_order(
                        client=client,
                        symbol=symbol_val,
                        amount=amount_val,
                        entry_price=entry_val,
                        stop_loss=sl_val,
                        take_profit=tp_val,
                        leverage=lev_val
                    )
                else: # Assuming anything not "buy" is a "sell" for this context
                    result = execute_sell_order(
                        client=client,
                        symbol=symbol_val,
                        amount=amount_val,
                        entry_price=entry_val,
                        stop_loss=sl_val,
                        take_profit=tp_val,
                        leverage=lev_val
                    )
                
                # Update plan with results
                plan["execution_id"] = result.order_id
                plan["execution_status"] = "FILLED" if result.success else "FAILED"
                plan["executed_price"] = result.executed_price
                plan["executed_amount"] = result.executed_amount
                plan["error"] = result.error
                
                # Save to legacy database if successful
                if result.success:
                    save_trade_to_database(plan, result)
                    execution_metadata["trades_executed"] += 1
                    
                    # Emit execution event for frontend
                    bus.emit_sync("execution_complete", {
                        "node": "execution",
                        "trade": {
                            "symbol": symbol_val,
                            "side": side_val,
                            "amount": amount_val,
                            "price": result.executed_price,
                            "status": "FILLED",
                            "order_id": result.order_id,
                            "pnl": 0.0 # Initial PnL is 0
                        }
                    })

                # Production Persistence
                run_id = state.get("run_id")
                if run_id:
                    from ..database.persistence_manager import get_persistence_manager
                    try:
                        with get_persistence_manager() as pm:
                            pm.record_execution(
                                run_id=run_id,
                                decision_id=str(plan.get("id")) if plan.get("id") else None, # Retrieved from strategy node
                                symbol=symbol_val,
                                side=side_val,
                                order_id=result.order_id,
                                status=plan["execution_status"],
                                executed_price=result.executed_price,
                                executed_amount=result.executed_amount,
                                error=result.error
                            )
                    except Exception as persist_err:
                        logger.warning(f"⚠️  Failed to record execution persistence: {persist_err}")
                
            except Exception as e:
                logger.error(f"Execution error: {e}")
                plan["execution_status"] = "FAILED"
                plan["error"] = str(e)
        else:
            # Simulation mode
            logger.info("  [SIMULATION] Order placed successfully")
            plan["execution_id"] = f"sim_{symbol_val.replace('/', '_')}_{int(datetime.now().timestamp())}"
            plan["execution_status"] = "FILLED"
            plan["executed_price"] = entry_val
            plan["executed_amount"] = amount_val
            
            # Save to legacy database even in simulation
            result = TradeResult(
                success=True,
                order_id=str(plan["execution_id"]),
                executed_price=entry_val,
                executed_amount=amount_val
            )
            save_trade_to_database(plan, result)
            execution_metadata["trades_executed"] += 1

            # Production Persistence (Simulation)
            run_id = state.get("run_id")
            if run_id:
                from ..database.persistence_manager import get_persistence_manager
                try:
                    with get_persistence_manager() as pm:
                        pm.record_execution(
                            run_id=run_id,
                            decision_id=str(plan.get("id")) if plan.get("id") else None,
                            symbol=symbol_val,
                            side=side_val,
                            order_id=str(plan["execution_id"]),
                            status="FILLED",
                            executed_price=entry_val,
                            executed_amount=amount_val,
                            metadata={"mode": "SIMULATION"}
                        )
                except Exception as persist_err:
                    logger.warning(f"⚠️  Failed to record execution persistence (SIM): {persist_err}")
        
        results.append(plan)
    
    filled_count = len([r for r in results if r.get('execution_status') == 'FILLED'])
    logger.info(f"\n✅ Execution complete: {filled_count} filled")
    logger.info(f"📊 Metadata: {execution_metadata}")
    
    return {
        "execution_results": results,
        "execution_metadata": execution_metadata,
        "warnings": warnings_list
    }
