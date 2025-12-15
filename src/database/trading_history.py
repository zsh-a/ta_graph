"""
Trading History Management
Migrated from Super-nof1.ai/lib/trading/account-information-and-performance.ts
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .models import ModelAccount, Trading, TradingLesson, ModelType, OperationType, SymbolType
from .session import get_session
from .account_manager import sync_model_account_from_exchange, ModelAccountInfo
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


def get_default_model(db: Optional[Session] = None) -> ModelType:
    """Get default model type from env or first active account"""
    should_close = False
    if db is None:
        db = get_session()
        should_close = True
    
    try:
        import os
        default_model_env = os.getenv("DEFAULT_MODEL")
        
        if default_model_env:
            try:
                model = ModelType[default_model_env]
                account = db.query(ModelAccount).filter_by(model=model, isActive=True).first()
                if account:
                    return model
            except KeyError:
                pass
        
        # Fallback: get first active account
        first_active = db.query(ModelAccount).filter_by(isActive=True).order_by("createdAt").first()
        
        if not first_active:
            raise ValueError("No active model account found. Please create a model account first.")
        
        return first_active.model
        
    finally:
        if should_close:
            db.close()


def convert_model_account_to_performance(
    model_account: ModelAccountInfo,
    initial_capital: Optional[float] = None
) -> AccountPerformance:
    """Convert ModelAccountInfo to AccountPerformance format"""
    
    # Convert positions to expected format
    positions = [{
        "symbol": pos.get("symbol"),
        "contracts": pos.get("size", 0),
        "entryPrice": pos.get("entryPrice", 0),
        "markPrice": pos.get("markPrice", 0),
        "unrealizedPnl": pos.get("pnl", 0),
        "leverage": pos.get("leverage", 1),
        "initialMargin": pos.get("margin", 0),
        "side": pos.get("side"),
        "notional": pos.get("size", 0) * pos.get("markPrice", 0),
    } for pos in model_account.positions]
    
    currentPositionsValue = sum(
        pos["initialMargin"] + pos["unrealizedPnl"] 
        for pos in positions
    )
    
    contractValue = sum(abs(pos["contracts"]) for pos in positions)
    
    totalAccountValue = model_account.totalEquity
    availableCash = model_account.availableBalance
    
    base_capital = initial_capital or model_account.currentBalance
    currentTotalReturn = (totalAccountValue - base_capital) / base_capital if base_capital > 0 else 0
    
    logger.info(f"💰 Account Value (Model: {model_account.model.value}):")
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
        openOrders=model_account.openOrders,
        sharpeRatio=model_account.sharpeRatio
    )


def get_account_performance(
    initial_capital: Optional[float] = None,
    model: Optional[ModelType] = None,
    db: Optional[Session] = None
) -> AccountPerformance:
    """
    Get account performance for a specific model
    
    Args:
        initial_capital: Optional initial capital for return calculation
        model: Optional model type (uses default if not provided)
        db: Database session
        
    Returns:
        AccountPerformance object
    """
    should_close = False
    if db is None:
        db = get_session()
        should_close = True
    
    try:
        target_model = model or get_default_model(db)
        logger.info(f"🔄 Fetching account info for model: {target_model.value}")
        
        model_account = sync_model_account_from_exchange(target_model, db)
        logger.info(f"✅ Account info fetched for {target_model.value}")
        
        return convert_model_account_to_performance(model_account, initial_capital)
        
    finally:
        if should_close:
            db.close()


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
