"""
Account Manager - Model account management and synchronization
Migrated from Super-nof1.ai/lib/trading/model-account-manager.ts
"""

import os
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .models import ModelAccount, ModelType, Trading, ModelPerformanceSnapshot
from .session import get_db
from ..logger import get_logger

load_dotenv()
logger = get_logger(__name__)

# Import exchange client (to be created)
# from ..trading.exchange_client import get_exchange_client

class ModelAccountInfo:
    """Model account information structure"""
    def __init__(
        self,
        id: str,
        model: ModelType,
        name: str,
        currentBalance: float,
        availableBalance: float,
        totalEquity: float,
        unrealizedPnl: float,
        margin: float,
        positions: List[Dict],
        openOrders: List[Dict],
        totalTrades: int,
        winningTrades: int,
        losingTrades: int,
        totalPnL: float,
        totalPnLPercentage: float,
        winRate: float,
        maxDrawdown: float,
        sharpeRatio: float,
        isActive: bool
    ):
        self.id = id
        self.model = model
        self.name = name
        self.currentBalance = currentBalance
        self.availableBalance = availableBalance
        self.totalEquity = totalEquity
        self.unrealizedPnl = unrealizedPnl
        self.margin = margin
        self.positions = positions
        self.openOrders = openOrders
        self.totalTrades = totalTrades
        self.winningTrades = winningTrades
        self.losingTrades = losingTrades
        self.totalPnL = totalPnL
        self.totalPnLPercentage = totalPnLPercentage
        self.winRate = winRate
        self.maxDrawdown = maxDrawdown
        self.sharpeRatio = sharpeRatio
        self.isActive = isActive


def get_or_create_model_account(
    model: ModelType,
    name: str,
    api_key: str,
    api_secret: str,
    passphrase: Optional[str] = None,
    db: Optional[Session] = None
) -> ModelAccount:
    """
    Get or create model account with exchange API credentials
    
    Args:
        model: Model type enum
        name: Display name for the model
        api_key: Exchange API key
        api_secret: Exchange API secret
        passphrase: Exchange passphrase (if required)
        db: Database session (optional)
        
    Returns:
        ModelAccount instance
    """
    should_close = False
    if db is None:
        db = get_session()
        should_close = True
    
    try:
        # Check if account exists
        account = db.query(ModelAccount).filter_by(model=model).first()
        
        if not account:
            # Create new account
            account = ModelAccount(
                model=model,
                name=name,
                bitgetApiKey=api_key,
                bitgetApiSecret=api_secret,
                bitgetPassphrase=passphrase,
                initialCapital=0.0,
                currentBalance=0.0,
                availableBalance=0.0,
                isActive=True
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            logger.info(f"✓ Created new model account: {model.value}")
        else:
            # Update API credentials if changed
            updated = False
            if account.bitgetApiKey != api_key:
                account.bitgetApiKey = api_key
                updated = True
            if account.bitgetApiSecret != api_secret:
                account.bitgetApiSecret = api_secret
                updated = True
            if account.bitgetPassphrase != passphrase:
                account.bitgetPassphrase = passphrase
                updated = True
            
            if updated:
                db.commit()
                logger.info(f"✓ Updated model account credentials: {model.value}")
        
        return account
        
    finally:
        if should_close:
            db.close()


def sync_model_account_from_exchange(
    model: ModelType,
    db: Optional[Session] = None
) -> ModelAccountInfo:
    """
    Sync account data from exchange API
    
    Args:
        model: Model type to sync
        db: Database session (optional)
        
    Returns:
        ModelAccountInfo with current data
    """
    should_close = False
    if db is None:
        from .session import get_session
        db = get_session()
        should_close = True
    
    try:
        account = db.query(ModelAccount).filter_by(model=model).first()
        
        if not account:
            raise ValueError(f"Model account not found for {model.value}")
        
        # TODO: Implement exchange API sync using ccxt
        # For now, return mock data
        logger.warning(f"Exchange sync not yet implemented for {model.value}, returning mock data")
        
        # Mock balance data
        balance = {
            "total": account.currentBalance or 10000.0,
            "free": account.availableBalance or 9000.0,
            "used": 1000.0,
            "upnl": 0.0
        }
        
        positions = []
        openOrders = []
        
        # Calculate initial capital if not set
        if account.initialCapital == 0:
            account.initialCapital = balance["total"]
            db.commit()
        
        # Calculate performance
        totalPnL = balance["total"] - account.initialCapital
        totalPnLPercentage = (totalPnL / account.initialCapital * 100) if account.initialCapital > 0 else 0
        
        # Update account
        account.currentBalance = balance["total"]
        account.availableBalance = balance["free"]
        account.totalPnL = totalPnL
        account.totalPnLPercentage = totalPnLPercentage
        db.commit()
        
        # Calculate win rate
        total_trades = account.totalTrades
        win_rate = (account.winningTrades / total_trades * 100) if total_trades > 0 else 0
        
        return ModelAccountInfo(
            id=account.id,
            model=account.model,
            name=account.name,
            currentBalance=balance["total"],
            availableBalance=balance["free"],
            totalEquity=balance["total"],
            unrealizedPnl=balance["upnl"],
            margin=balance["used"],
            positions=positions,
            openOrders=openOrders,
            totalTrades=account.totalTrades,
            winningTrades=account.winningTrades,
            losingTrades=account.losingTrades,
            totalPnL=totalPnL,
            totalPnLPercentage=totalPnLPercentage,
            winRate=win_rate,
            maxDrawdown=account.maxDrawdown,
            sharpeRatio=account.sharpeRatio,
            isActive=account.isActive
        )
        
    finally:
        if should_close:
            db.close()


def get_all_model_accounts(db: Optional[Session] = None) -> List[ModelAccountInfo]:
    """Get all active model accounts"""
    should_close = False
    if db is None:
        from .session import get_session
        db = get_session()
        should_close = True
    
    try:
        accounts = db.query(ModelAccount).filter_by(isActive=True).all()
        return [sync_model_account_from_exchange(acc.model, db) for acc in accounts]
    finally:
        if should_close:
            db.close()


def update_model_trade_stats(
    model: ModelType,
    is_win: Optional[bool] = None,
    pnl: Optional[float] = None,
    db: Optional[Session] = None
) -> None:
    """Update trade statistics for a model account"""
    should_close = False
    if db is None:
        from .session import get_session
        db = get_session()
        should_close = True
    
    try:
        account = db.query(ModelAccount).filter_by(model=model).first()
        if not account:
            return
        
        account.totalTrades += 1
        
        if is_win is not None:
            if is_win:
                account.winningTrades += 1
            else:
                account.losingTrades += 1
        
        db.commit()
        logger.info(f"✓ Updated trade stats for {model.value}")
        
    finally:
        if should_close:
            db.close()


def create_performance_snapshot(
    model: ModelType,
    db: Optional[Session] = None
) -> None:
    """Create performance snapshot for historical tracking"""
    should_close = False
    if db is None:
        from .session import get_session
        db = get_session()
        should_close = True
    
    try:
        account_info = sync_model_account_from_exchange(model, db)
        account = db.query(ModelAccount).filter_by(model=model).first()
        
        if not account:
            return
        
        snapshot = ModelPerformanceSnapshot(
            modelAccountId=account.id,
            balance=account_info.currentBalance,
            totalPnL=account_info.totalPnL,
            totalPnLPercentage=account_info.totalPnLPercentage,
            totalTrades=account_info.totalTrades,
            winRate=account_info.winRate,
            sharpeRatio=account_info.sharpeRatio,
            maxDrawdown=account_info.maxDrawdown,
            openPositions=len(account_info.positions)
        )
        
        db.add(snapshot)
        db.commit()
        logger.info(f"✓ Created performance snapshot for {model.value}")
        
    finally:
        if should_close:
            db.close()
