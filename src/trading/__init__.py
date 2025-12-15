"""
Trading module - Exchange client integrations
"""
from .exchange_client import ExchangeClient, get_client, Balance, Position, OrderResult, normalize_symbol

__all__ = [
    'ExchangeClient',
    'get_client',
    'Balance',
    'Position',
    'OrderResult',
    'normalize_symbol',
]
