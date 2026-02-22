"""
Unified symbol normalization utility.

Provides a single, consistent normalize_symbol function used across the codebase.
"""


def normalize_symbol(symbol: str) -> str:
    """
    Normalize a trading symbol to its base currency.

    Strips exchange-specific suffixes like '/USDT', ':USDT', etc.

    Examples:
        'BTC/USDT'       -> 'BTC'
        'BTC/USDT:USDT'  -> 'BTC'
        'ETH'            -> 'ETH'
        'SOL/USDT:USDT'  -> 'SOL'

    Args:
        symbol: Raw trading symbol string

    Returns:
        Base currency string (e.g. 'BTC', 'ETH')
    """
    return symbol.split('/')[0].split(':')[0]
