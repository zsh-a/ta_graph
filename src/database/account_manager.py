"""
Simplified Account Manager - Single trading account management
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .session import get_session
from ..logger import get_logger

load_dotenv()
logger = get_logger(__name__)


@dataclass
class AccountInfo:
    """Trading account information"""
    total_balance: float
    available_balance: float
    used_margin: float
    unrealized_pnl: float
    positions: List[Dict[str, Any]]
    open_orders: List[Dict[str, Any]]


class AccountManager:
    """
    Simplified account manager for a single trading account.
    Handles both real exchange API and mock data for dry-run mode.
    """
    
    def __init__(
        self,
        exchange_id: str = "bitget",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        sandbox: bool = True,
        use_mock: bool = False
    ):
        """
        Initialize account manager
        
        Args:
            exchange_id: Exchange name (default: bitget)
            api_key: Exchange API key (reads from env if not provided)
            api_secret: Exchange API secret (reads from env if not provided)
            passphrase: Exchange passphrase (reads from env if not provided)
            sandbox: Use sandbox/testnet mode
            use_mock: Force use of mock data (for dry-run)
        """
        self.exchange_id = exchange_id
        self.use_mock = use_mock
        self.sandbox = sandbox
        
        # Load credentials from env if not provided
        if not use_mock:
            self.api_key = api_key or os.getenv("BITGET_API_KEY")
            self.api_secret = api_secret or os.getenv("BITGET_API_SECRET")
            self.passphrase = passphrase or os.getenv("BITGET_PASSPHRASE")
            
            # Check if we have all required credentials
            if not all([self.api_key, self.api_secret, self.passphrase]):
                logger.warning("Missing exchange credentials, using mock data")
                self.use_mock = True
        
        # Initialize exchange client if not using mock
        self.client = None
        if not self.use_mock:
            try:
                from ..trading.exchange_client import CCXTExchangeClient
                
                self.client = CCXTExchangeClient(
                    exchange_id=self.exchange_id,
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    password=self.passphrase,
                    sandbox=self.sandbox
                )
                logger.info(f"✓ Exchange client initialized: {exchange_id} ({'SANDBOX' if sandbox else 'LIVE'})")
            except Exception as e:
                logger.error(f"Failed to initialize exchange client: {e}")
                logger.warning("Falling back to mock data")
                self.use_mock = True
        
        # Mock data for dry-run
        self.mock_balance = 10000.0
        self.mock_available = 10000.0
        self.mock_positions: List[Dict] = [
            {
                "symbol": "BTC/USDT",
                "side": "long",
                "size": 0.5,
                "entry_price": 65000.0,
                "mark_price": 65500.0,
                "unrealized_pnl": 250.0,
                "leverage": 10.0,
                "margin_type": "isolated",
                "stop_loss": 64000.0,
                "take_profit": 68000.0
            }
        ]
        self.mock_orders: List[Dict] = []
    
    def get_account_info(self) -> AccountInfo:
        """
        Get current account information
        
        Returns:
            AccountInfo with balance, positions, and orders
        """
        if self.use_mock:
            return AccountInfo(
                total_balance=self.mock_balance,
                available_balance=self.mock_available,
                used_margin=self.mock_balance - self.mock_available,
                unrealized_pnl=sum(p.get("unrealized_pnl", 0.0) for p in self.mock_positions),
                positions=self.mock_positions.copy(),
                open_orders=self.mock_orders.copy()
            )
        
        try:
            # Fetch from real exchange
            balance_info = self.client.get_account_info()
            positions_list = self.client.get_positions()
            orders_list = self.client.get_open_orders()

            positions = [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "mark_price": p.mark_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "leverage": p.leverage,
                    "margin_type": p.margin_type,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit
                }
                for p in positions_list
            ]
            
            # (Rest of get_account_info mapping remains but we override positions for now)
            orders = [
                {
                    "id": o.id,
                    "symbol": o.symbol,
                    "side": o.side,
                    "price": o.price,
                    "amount": o.amount,
                    "status": o.status,
                    "filled": o.filled,
                    "remaining": o.remaining
                }
                for o in orders_list
            ]
            
            logger.info(f"✅ Account synced: Balance=${balance_info.total:.2f}, Positions={len(positions)}, Orders={len(orders)}")
            
            return AccountInfo(
                total_balance=balance_info.total,
                available_balance=balance_info.free,
                used_margin=balance_info.used,
                unrealized_pnl=balance_info.upnl,
                positions=positions,
                open_orders=orders
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch account info: {e}")
            logger.warning("Falling back to mock data")
            
            # Return mock data on error
            return AccountInfo(
                total_balance=self.mock_balance,
                available_balance=self.mock_available,
                used_margin=self.mock_balance - self.mock_available,
                unrealized_pnl=0.0,
                positions=self.mock_positions.copy(),
                open_orders=self.mock_orders.copy()
            )
    
    def update_balance(self, new_balance: float, new_available: float):
        """
        Update mock balance (for dry-run simulation)
        
        Args:
            new_balance: New total balance
            new_available: New available balance
        """
        if self.use_mock:
            self.mock_balance = new_balance
            self.mock_available = new_available
            logger.info(f"💰 Mock balance updated: ${new_balance:.2f} (available: ${new_available:.2f})")
    
    def add_mock_position(self, position: Dict[str, Any]):
        """Add a mock position (for dry-run simulation)"""
        if self.use_mock:
            self.mock_positions.append(position)
            logger.info(f"📍 Mock position added: {position.get('symbol')} {position.get('side')}")
    
    def remove_mock_position(self, symbol: str):
        """Remove a mock position (for dry-run simulation)"""
        if self.use_mock:
            self.mock_positions = [p for p in self.mock_positions if p.get('symbol') != symbol]
            logger.info(f"📍 Mock position removed: {symbol}")
    
    def add_mock_order(self, order: Dict[str, Any]):
        """Add a mock order (for dry-run simulation)"""
        if self.use_mock:
            self.mock_orders.append(order)
            logger.info(f"📋 Mock order added: {order.get('id')}")
    
    def remove_mock_order(self, order_id: str):
        """Remove a mock order (for dry-run simulation)"""
        if self.use_mock:
            self.mock_orders = [o for o in self.mock_orders if o.get('id') != order_id]
            logger.info(f"📋 Mock order removed: {order_id}")


# Global singleton instance
_account_manager: Optional[AccountManager] = None


def get_account_manager(
    force_recreate: bool = False,
    **kwargs
) -> AccountManager:
    """
    Get or create singleton account manager instance
    
    Args:
        force_recreate: Force recreate the manager
        **kwargs: Arguments to pass to AccountManager constructor
        
    Returns:
        AccountManager instance
    """
    global _account_manager
    
    if _account_manager is None or force_recreate:
        # Determine if we should use mock based on trading mode
        trading_mode = os.getenv("TRADING_MODE", "dry-run")
        use_mock = kwargs.pop("use_mock", trading_mode != "live")
        
        _account_manager = AccountManager(use_mock=use_mock, **kwargs)
        logger.info(f"✓ Account manager created ({'MOCK' if use_mock else 'LIVE'} mode)")
    
    return _account_manager


def reset_account_manager():
    """Reset the singleton account manager (useful for testing)"""
    global _account_manager
    _account_manager = None
    logger.info("Account manager reset")
