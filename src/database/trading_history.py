"""
Trading History Management
Migrated from Super-nof1.ai/lib/trading/account-information-and-performance.ts
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .models import Trading, TradingLesson, OperationType, SymbolType
from .session import get_session
from .account_manager import get_account_manager, AccountInfo
from ..logger import get_logger

logger = get_logger(__name__)


class AccountPerformance:
    """Account performance data structure"""
    def __init__(
        self,
        currentPositionsValue: float,
        contractValue: float,
        totalCashValue: float,
        availableCash: float,
        currentTotalReturn: float,
        positions: List[Dict],
        openOrders: List[Dict],
        sharpeRatio: float
    ):
        self.currentPositionsValue = currentPositionsValue
        self.contractValue = contractValue
        self.totalCashValue = totalCashValue
        self.availableCash = availableCash
        self.currentTotalReturn = currentTotalReturn
        self.positions = positions
        self.openOrders = openOrders
        self.sharpeRatio = sharpeRatio


def convert_account_info_to_performance(
    account_info: AccountInfo,
    initial_capital: Optional[float] = None
) -> AccountPerformance:
    """Convert AccountInfo to AccountPerformance format"""
    
    # Convert positions to expected format
    positions = [{
        "symbol": pos.get("symbol"),
        "contracts": pos.get("size", 0),
        "entryPrice": pos.get("entry_price", 0),
        "markPrice": pos.get("mark_price", 0),
        "unrealizedPnl": pos.get("unrealized_pnl", 0),
        "leverage": pos.get("leverage", 1),
        "initialMargin": pos.get("used_margin", 0),
        "side": pos.get("side"),
        "notional": pos.get("size", 0) * pos.get("mark_price", 0),
    } for pos in account_info.positions]
    
    currentPositionsValue = sum(
        pos["initialMargin"] + pos["unrealizedPnl"] 
        for pos in positions
    )
    
    contractValue = sum(abs(pos["contracts"]) for pos in positions)
    
    totalAccountValue = account_info.total_balance
    availableCash = account_info.available_balance
    
    base_capital = initial_capital or account_info.total_balance
    currentTotalReturn = (totalAccountValue - base_capital) / base_capital if base_capital > 0 else 0
    
    logger.info(f"💰 Account Value (Model: Qwen):")
    logger.info(f"   Total Equity: ${totalAccountValue:.2f}")
    logger.info(f"   Available: ${availableCash:.2f}")
    logger.info(f"   Return: {currentTotalReturn*100:.2f}%")
    logger.info(f"   Positions: {len(positions)}")
    
    return AccountPerformance(
        currentPositionsValue=currentPositionsValue,
        contractValue=contractValue,
        totalCashValue=totalAccountValue,
        availableCash=availableCash,
        currentTotalReturn=currentTotalReturn,
        positions=positions,
        openOrders=account_info.open_orders,
        sharpeRatio=0.0  # TODO: Calculate from trade history
    )


def get_account_performance(
    initial_capital: Optional[float] = None,
    model: Optional[str] = None,  # Kept for backward compatibility but not used
    db: Optional[Session] = None
) -> AccountPerformance:
    """
    Get account performance
    
    Args:
        initial_capital: Optional initial capital for return calculation
        model: Deprecated, kept for backward compatibility
        db: Database session (not used with new account manager)
        
    Returns:
        AccountPerformance object
    """
    logger.info(f"🔄 Fetching account info for model: Qwen")
    
    account_manager = get_account_manager()
    account_info = account_manager.get_account_info()
    
    logger.info(f"✅ Account info fetched for Qwen")
    
    return convert_account_info_to_performance(account_info, initial_capital)


def get_recent_trades(limit: int = 10, db: Optional[Session] = None) -> List[Dict]:
    """Get recent trading records"""
    should_close = False
    if db is None:
        db = get_session()
        should_close = True
    
    try:
        trades = db.query(Trading).order_by(desc(Trading.createdAt)).limit(limit).all()
        
        return [{
            "symbol": trade.symbol.value,
            "operation": trade.operation.value,
            "pricing": trade.pricing,
            "amount": trade.amount,
            "riskAmount": trade.riskAmount,
            "createdAt": trade.createdAt.isoformat()
        } for trade in trades]
        
    finally:
        if should_close:
            db.close()


def get_recent_trades_raw(limit: int = 10, db: Optional[Session] = None) -> List[Dict]:
    """
    Get recent trades with preference for completed trades (lessons)
    """
    should_close = False
    if db is None:
        db = get_session()
        should_close = True
    
    try:
        # Fetch recent lessons
        lessons = db.query(TradingLesson).order_by(desc(TradingLesson.createdAt)).limit(limit).all()
        
        if len(lessons) >= 5:
            return [{
                "symbol": lesson.symbol.value,
                "operation": lesson.decision,
                "outcome": lesson.outcome,
                "pnl": lesson.pnl,
                "pnlPercentage": lesson.pnlPercentage,
                "createdAt": lesson.createdAt.isoformat(),
                "type": "completed",
                "exitReason": lesson.exitReason
            } for lesson in lessons]
        
        # Mix with recent trades
        trades = db.query(Trading).order_by(desc(Trading.createdAt)).limit(limit).all()
        
        combined = []
        for lesson in lessons:
            combined.append({
                "symbol": lesson.symbol.value,
                "operation": lesson.decision,
                "outcome": lesson.outcome,
                "pnl": lesson.pnl,
                "pnlPercentage": lesson.pnlPercentage,
                "createdAt": lesson.createdAt.isoformat(),
                "type": "completed",
                "exitReason": lesson.exitReason
            })
        
        for trade in trades:
            combined.append({
                "symbol": trade.symbol.value,
                "operation": trade.operation.value,
                "pricing": trade.pricing,
                "amount": trade.amount,
                "riskAmount": trade.riskAmount,
                "createdAt": trade.createdAt.isoformat(),
                "type": "open_or_recent"
            })
        
        # Sort and limit
        combined.sort(key=lambda x: x["createdAt"], reverse=True)
        return combined[:limit]
        
    finally:
        if should_close:
            db.close()


def create_trading_record(
    symbol: SymbolType,
    operation: OperationType,
    amount: Optional[int] = None,
    pricing: Optional[int] = None,
    risk_amount: Optional[float] = None,
    prediction: Optional[Dict] = None,
    model_account_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Trading:
    """Create a new trading record"""
    should_close = False
    if db is None:
        db = get_session()
        should_close = True
    
    try:
        trade = Trading(
            symbol=symbol,
            operation=operation,
            amount=amount,
            pricing=pricing,
            riskAmount=risk_amount,
            prediction=prediction,
            modelAccountId=model_account_id,
            chatId=chat_id
        )
        
        db.add(trade)
        db.commit()
        db.refresh(trade)
        
        logger.info(f"✓ Created trading record: {operation.value} {symbol.value}")
        return trade
        
    finally:
        if should_close:
            db.close()


def format_account_performance(performance: AccountPerformance) -> str:
    """Format account performance as text"""
    total_unrealized_pnl = sum(pos["unrealizedPnl"] for pos in performance.positions)
    
    output = f"""Current Total Return: {performance.currentTotalReturn*100:.2f}%
Available Cash: ${performance.availableCash:.2f}
Current Account Value: ${performance.totalCashValue:.2f}
Sharpe Ratio: {performance.sharpeRatio:.2f}
Unrealized PnL: ${total_unrealized_pnl:.2f}
Positions Value: ${performance.currentPositionsValue:.2f}

## CURRENT POSITION INFORMATION

Total Active Positions: {len(performance.positions)}
"""
    
    if performance.positions:
        output += "\nDetailed Position Breakdown:\n"
        for i, pos in enumerate(performance.positions, 1):
            output += f"""
Position {i}:
  symbol: {pos['symbol']}
  quantity: {pos['contracts']}
  entry_price: ${pos['entryPrice']:.4f}
  current_price: ${pos['markPrice']:.4f}
  unrealized_pnl: ${pos['unrealizedPnl']:.4f}
  leverage: {pos['leverage']}x
  side: {pos['side']}
"""
    
    output += "\n## OPEN ORDERS\n"
    if performance.openOrders:
        output += f"Total Open Orders: {len(performance.openOrders)}\n"
        for i, order in enumerate(performance.openOrders, 1):
            output += f"""
Order {i}:
  symbol: {order.get('symbol')}
  side: {order.get('side')}
  type: {order.get('type')}
  price: {order.get('price')}
  amount: {order.get('amount')}
"""
    else:
        output += "No open orders.\n"
    
    return output


def get_exchange_order_history(
    symbol: Optional[str] = None,
    start_date: Optional[datetime] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetch order history directly from exchange API
    """
    from ..trading.exchange_client import get_client
    
    client = get_client()
    since = int(start_date.timestamp() * 1000) if start_date else None
    
    orders = client.fetch_orders(symbol=symbol, since=since, limit=limit)
    
    # Calculate stats from exchange orders
    # Note: Exchange orders might not have PnL directly in fetch_orders for all exchanges.
    # CCXT's fetch_orders typically returns order status and filled/remaining.
    # We might need to fetch trades or look at 'profit' in order info if available.
    
    total_trades = len(orders)
    winning_trades = sum(1 for o in orders if o.status == 'closed' and o.filled > 0) # Placeholder logic
    losing_trades = 0
    total_pnl = 0.0
    
    # Try to extract more info if available in 'info' or similar (though OrderResult is simplified)
    # For now, providing a structured response consistent with local history
    
    return {
        "stats": {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_pnl": total_pnl,
            "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        },
        "orders": [{
            "id": o.id,
            "symbol": o.symbol,
            "operation": o.side.capitalize(),
            "pricing": o.price,
            "amount": o.amount,
            "status": o.status,
            "createdAt": o.order_placed_time.isoformat() if o.order_placed_time else None,
            "pnl": None, # Complex to get from single fetch_orders call
            "outcome": "closed" if o.status == 'closed' else "open"
        } for o in orders],
        "total": total_trades,
        "page": 1,
        "limit": limit
    }

def get_order_history(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    symbol: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    source: str = 'local',
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Get order history with statistics from specified source
    """
    if source == 'exchange':
        return get_exchange_order_history(symbol=symbol, start_date=start_date, limit=limit)
        
    should_close = False
    if db is None:
        db = get_session()
        should_close = True
    
    try:
        # Build query for Trading
        query = db.query(Trading)
        
        if start_date:
            query = query.filter(Trading.createdAt >= start_date)
        if end_date:
            query = query.filter(Trading.createdAt <= end_date)
        if symbol:
            try:
                sym_enum = SymbolType(symbol)
                query = query.filter(Trading.symbol == sym_enum)
            except ValueError:
                 pass

        total_count = query.count()
        trades = query.order_by(desc(Trading.createdAt)).limit(limit).offset(offset).all()
        
        stats_query = db.query(TradingLesson).join(Trading)
        if start_date:
            stats_query = stats_query.filter(Trading.createdAt >= start_date)
        if end_date:
            stats_query = stats_query.filter(Trading.createdAt <= end_date)
        if symbol:
            try:
                sym_enum = SymbolType(symbol)
                stats_query = stats_query.filter(Trading.symbol == sym_enum)
            except ValueError:
                pass
                
        lessons = stats_query.all()
        
        total_trades_count = len(lessons)
        winning_trades = sum(1 for l in lessons if l.pnl > 0)
        losing_trades = sum(1 for l in lessons if l.pnl <= 0)
        total_pnl = sum(l.pnl for l in lessons)
        win_rate = (winning_trades / total_trades_count * 100) if total_trades_count > 0 else 0.0
        
        return {
            "stats": {
                "total_trades": total_trades_count,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "total_pnl": total_pnl,
                "win_rate": win_rate
            },
            "orders": [{
                "id": str(trade.id),
                "symbol": trade.symbol.value,
                "operation": trade.operation.value,
                "pricing": trade.pricing,
                "amount": trade.amount,
                "riskAmount": trade.riskAmount,
                "createdAt": trade.createdAt.isoformat(),
                "pnl": next((l.pnl for l in trade.lessons), None),
                "outcome": next((l.outcome for l in trade.lessons), None)
            } for trade in trades],
            "total": total_count,
            "page": (offset // limit) + 1,
            "limit": limit
        }
        
    finally:
        if should_close:
            db.close()

