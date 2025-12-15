"""
Exchange Client Module
Ported from Super-nof1.ai/lib/trading/exchange-client.ts
Provides unified interface for exchange operations using CCXT
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
import ccxt
from dotenv import load_dotenv

from ..logger import get_logger

load_dotenv()
logger = get_logger(__name__)


def normalize_symbol(symbol: str, exchange_id: str = "bitget") -> str:
    """
    Normalize trading symbol for exchange-specific format
    
    Args:
        symbol: Symbol like "BTC/USDT" or "BTC/USDT:USDT"
        exchange_id: Exchange name (bitget, binance, etc.)
        
    Returns:
        Normalized symbol for the exchange
        
    Examples:
        >>> normalize_symbol("BTC/USDT", "bitget")
        'BTC/USDT:USDT'
        >>> normalize_symbol("BTC/USDT:USDT", "bitget")
        'BTC/USDT:USDT'
        >>> normalize_symbol("ETH/USDT", "bitget")
        'ETH/USDT:USDT'
    """
    if exchange_id == "bitget":
        # Bitget futures require :USDT suffix
        if ":USDT" not in symbol and "/USDT" in symbol:
            return f"{symbol}:USDT"
    
    return symbol



@dataclass
class Balance:
    """Account balance information"""
    total: float
    free: float
    used: float
    upnl: float  # Unrealized PnL


@dataclass
class Position:
    """Position information"""
    symbol: str
    side: str  # "long" or "short"
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: float
    margin_type: str  # "isolated" or "cross"


@dataclass
class OrderResult:
    """Order execution result"""
    id: str
    symbol: str
    side: str  # "buy" or "sell"
    price: float
    amount: float
    status: str
    filled: float
    remaining: float


class ExchangeClient(ABC):
    """Abstract base class for exchange clients"""
    
    @abstractmethod
    def get_account_info(self) -> Balance:
        """Get account balance information"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get all active positions"""
        pass
    
    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        order_type: str,  # "market", "limit", "stop_market", etc.
        amount: float,
        price: float | None = None,
        reduce_only: bool = False,
        leverage: int | None = None,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
        params: Dict[str, Any] | None = None
    ) -> OrderResult:
        """Place an order"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> None:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def set_leverage(self, symbol: str, leverage: int) -> None:
        """Set leverage for a symbol"""
        pass
    
    @abstractmethod
    def fetch_ticker(self, symbol: str) -> Dict[str, float]:
        """Fetch ticker data (last price, mark price)"""
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: str | None = None) -> List[OrderResult]:
        """Get open orders"""
        pass


class CCXTExchangeClient(ExchangeClient):
    """
    Exchange client implementation using CCXT
    Supports: Bitget, Binance
    """
    
    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        password: str | None = None,
        sandbox: bool = False,
        proxy_url: str | None = None
    ):
        """
        Initialize CCXT exchange client
        
        Args:
            exchange_id: Exchange name (e.g., "bitget", "binance")
            api_key: API key
            api_secret: API secret
            password: API passphrase (required for Bitget)
            sandbox: Use sandbox/testnet mode
            proxy_url: HTTP proxy URL
        """
        self.exchange_id = exchange_id
        
        # Get exchange class from ccxt
        exchange_class = getattr(ccxt, exchange_id, None)
        if not exchange_class:
            raise ValueError(f"Exchange {exchange_id} not supported by ccxt")
        
        # Configure exchange
        config: Dict[str, Any] = {
            'apiKey': api_key,
            'secret': api_secret,
            'password': password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Default to futures/swap
            },
        }
        
        if sandbox:
            config['sandbox'] = True
        
        if proxy_url:
            config['httpsProxy'] = proxy_url
        
        self.exchange = exchange_class(config)
        logger.info(f"✓ Initialized {exchange_id} client ({'SANDBOX' if sandbox else 'LIVE'})")
    
    def get_account_info(self) -> Balance:
        """Get account balance information"""
        try:
            balance = self.exchange.fetch_balance()
            
            # Normalize balance structure (USDT usually)
            usdt_balance = balance.get('USDT', balance.get('total', {}))
            
            return Balance(
                total=usdt_balance.get('total', 0.0),
                free=usdt_balance.get('free', 0.0),
                used=usdt_balance.get('used', 0.0),
                upnl=0.0  # Will be calculated from positions if needed
            )
        except Exception as e:
            logger.error(f"Failed to fetch account info: {e}")
            raise
    
    def get_positions(self) -> List[Position]:
        """Get all active positions"""
        try:
            positions = self.exchange.fetch_positions()
            
            active_positions = []
            for p in positions:
                # Filter positions with non-zero contracts
                if p.get('contracts') and abs(p['contracts']) > 0:
                    active_positions.append(Position(
                        symbol=p['symbol'],
                        side='short' if p.get('side') == 'short' else 'long',
                        size=abs(p.get('contracts', 0)),
                        entry_price=p.get('entryPrice', 0.0),
                        mark_price=p.get('markPrice', 0.0),
                        unrealized_pnl=p.get('unrealizedPnl', 0.0),
                        leverage=p.get('leverage', 1.0),
                        margin_type=p.get('marginMode', 'isolated')
                    ))
            
            return active_positions
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            raise
    
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
        reduce_only: bool = False,
        leverage: int | None = None,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
        params: Dict[str, Any] | None = None
    ) -> OrderResult:
        """Place an order"""
        try:
            # Normalize symbol format for exchange
            symbol = normalize_symbol(symbol, self.exchange_id)
            # Set leverage if provided
            if leverage:
                try:
                    self.set_leverage(symbol, leverage)
                except Exception as e:
                    logger.warning(f"Failed to set leverage to {leverage}: {e}")
            
            # Prepare params
            ccxt_params = params or {}
            if reduce_only:
                ccxt_params['reduceOnly'] = True
            
            # Add SL/TP to params
            if stop_loss_price:
                ccxt_params['stopLoss'] = {'triggerPrice': stop_loss_price}
            if take_profit_price:
                ccxt_params['takeProfit'] = {'triggerPrice': take_profit_price}
            
            # Place order
            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=ccxt_params
            )
            
            logger.info(f"✅ Order placed: {order['id']} | {side.upper()} {amount} {symbol} @ {price or 'MARKET'}")
            
            return OrderResult(
                id=order['id'],
                symbol=order['symbol'],
                side=order['side'],
                price=order.get('price') or order.get('average', 0.0),
                amount=order['amount'],
                status=order['status'],
                filled=order.get('filled', 0.0),
                remaining=order.get('remaining', 0.0)
            )
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> None:
        """Cancel an order"""
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Order canceled: {order_id}")
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise
    
    def set_leverage(self, symbol: str, leverage: int) -> None:
        """Set leverage for a symbol"""
        try:
            self.exchange.set_leverage(leverage, symbol)
            logger.info(f"✅ Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            # Some exchanges might not support this or already be at the leverage
            logger.warning(f"Could not set leverage for {symbol}: {e}")
    
    def fetch_ticker(self, symbol: str) -> Dict[str, float]:
        """Fetch ticker data"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            
            # Try to get mark price from info, fallback to last
            mark = ticker.get('last', 0.0)
            if ticker.get('info') and ticker['info'].get('markPrice'):
                mark = float(ticker['info']['markPrice'])
            
            return {
                'last': ticker.get('last', 0.0),
                'mark': mark
            }
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {symbol}: {e}")
            raise
    
    def get_open_orders(self, symbol: str | None = None) -> List[OrderResult]:
        """Get open orders"""
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            
            return [
                OrderResult(
                    id=order['id'],
                    symbol=order['symbol'],
                    side=order['side'],
                    price=order.get('price') or order.get('average', 0.0),
                    amount=order['amount'],
                    status=order['status'],
                    filled=order.get('filled', 0.0),
                    remaining=order.get('remaining', 0.0)
                )
                for order in orders
            ]
        except Exception as e:
            logger.error(f"Failed to fetch open orders: {e}")
            raise


# Singleton client management
_clients: dict[str, ExchangeClient] = {}


def get_client(exchange_id: str = "bitget") -> ExchangeClient:
    """
    Get or create exchange client (singleton pattern)
    
    Args:
        exchange_id: Exchange name ("bitget" or "binance")
        
    Returns:
        ExchangeClient instance
        
    Environment variables required:
        - BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE
        - BITGET_SANDBOX (optional, default: true)
        - Or BINANCE_API_KEY, BINANCE_API_SECRET
    """
    if exchange_id in _clients:
        return _clients[exchange_id]
    
    # Get configuration from environment
    if exchange_id == "bitget":
        api_key = os.getenv("BITGET_API_KEY")
        api_secret = os.getenv("BITGET_API_SECRET")
        password = os.getenv("BITGET_PASSPHRASE")
        sandbox = os.getenv("BITGET_SANDBOX", "true").lower() == "true"
        proxy_url = os.getenv("BITGET_HTTP_PROXY") or os.getenv("HTTPS_PROXY")
        
        if not api_key or not api_secret:
            raise ValueError("Bitget API credentials not configured. Set BITGET_API_KEY and BITGET_API_SECRET")
        
        client = CCXTExchangeClient(
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            password=password,
            sandbox=sandbox,
            proxy_url=proxy_url
        )
    elif exchange_id == "binance":
        is_dry_run = os.getenv("TRADING_MODE", "dry-run") != "live"
        
        if is_dry_run:
            api_key = os.getenv("BINANCE_TESTNET_API_KEY")
            api_secret = os.getenv("BINANCE_TESTNET_API_SECRET")
        else:
            api_key = os.getenv("BINANCE_LIVE_API_KEY")
            api_secret = os.getenv("BINANCE_LIVE_API_SECRET")
        
        proxy_url = os.getenv("BINANCE_HTTP_PROXY") or os.getenv("HTTPS_PROXY")
        
        if not api_key or not api_secret:
            raise ValueError("Binance API credentials not configured")
        
        client = CCXTExchangeClient(
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            sandbox=is_dry_run,
            proxy_url=proxy_url
        )
    else:
        raise ValueError(f"Unknown exchange: {exchange_id}")
    
    _clients[exchange_id] = client
    return client


if __name__ == "__main__":
    client = get_client("bitget")
    print(client.get_account_info())
    print(client.get_open_orders())
    print(client.place_order("BTC/USDT", "buy", "limit", 0.001, 20000))