"""
Unified error handling decorators for LangGraph nodes.

Provides:
- Retryable vs non-retryable error classification
- Exponential backoff retry logic
- Automatic fallback to safe states
- Error tracking in agent state
"""
import functools
import time
from typing import Any, Callable, Optional, Type, Union
from ..logger import get_logger

logger = get_logger(__name__)


# =========================================================================
# Error Classes
# =========================================================================

class NodeError(Exception):
    """Base class for node execution errors."""
    retryable: bool = True
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}


class APIError(NodeError):
    """
    API call errors (typically retryable).
    
    Examples: Network timeout, rate limits, temporary unavailability.
    """
    retryable = True


class ValidationError(NodeError):
    """
    Data validation errors (not retryable).
    
    Examples: Missing required fields, invalid schema, type mismatches.
    """
    retryable = False


class ConfigurationError(NodeError):
    """
    Configuration/setup errors (not retryable).
    
    Examples: Missing API keys, invalid model names.
    """
    retryable = False


class DataError(NodeError):
    """
    Data-related errors (sometimes retryable).
    
    Examples: Empty market data, stale prices.
    """
    retryable = True  # May be resolved by refetching


# =========================================================================
# Decorator
# =========================================================================

def with_error_handling(
    max_retries: int = 2,
    retry_delay: float = 1.0,
    exponential_backoff: bool = True,
    fallback_fn: Optional[Callable] = None,
    error_state_key: str = "errors",
    retryable_exceptions: tuple = (APIError, DataError, ConnectionError, TimeoutError),
):
    """
    Unified error handling decorator for LangGraph nodes.
    
    Provides retry logic with exponential backoff and automatic fallback
    to safe states when all retries are exhausted.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 2)
        retry_delay: Base delay between retries in seconds (default: 1.0)
        exponential_backoff: Whether to use exponential backoff (default: True)
        fallback_fn: Optional function to call when all retries fail.
                     Should accept (state, *args, **kwargs) and return dict.
        error_state_key: State key for recording errors (default: "errors")
        retryable_exceptions: Tuple of exception types that trigger retries
    
    Usage:
        @with_error_handling(max_retries=2, fallback_fn=my_fallback)
        def my_node(state: AgentState) -> dict:
            # Node implementation
            return {"result": value}
    
    Returns:
        Decorated function with error handling
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(state: dict, *args, **kwargs) -> dict:
            last_error: Optional[Exception] = None
            func_name = func.__name__
            
            for attempt in range(max_retries + 1):
                try:
                    return func(state, *args, **kwargs)
                    
                except NodeError as e:
                    last_error = e
                    
                    if not e.retryable:
                        logger.error(f"[{func_name}] Non-retryable error: {e}")
                        break
                    
                    if attempt >= max_retries:
                        logger.error(f"[{func_name}] Max retries ({max_retries}) exceeded: {e}")
                        break
                    
                    delay = retry_delay * (2 ** attempt if exponential_backoff else 1)
                    logger.warning(
                        f"[{func_name}] Retry {attempt + 1}/{max_retries} "
                        f"after {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                    
                except retryable_exceptions as e:
                    last_error = e
                    
                    if attempt >= max_retries:
                        logger.error(f"[{func_name}] Max retries ({max_retries}) exceeded: {e}")
                        break
                    
                    delay = retry_delay * (2 ** attempt if exponential_backoff else 1)
                    logger.warning(
                        f"[{func_name}] Retrying ({attempt + 1}/{max_retries}) "
                        f"after {delay:.1f}s: {type(e).__name__}: {e}"
                    )
                    time.sleep(delay)
                    
                except Exception as e:
                    # Non-retryable unexpected error
                    last_error = e
                    logger.error(f"[{func_name}] Unexpected error: {type(e).__name__}: {e}")
                    break
            
            # All retries exhausted - use fallback or return error state
            logger.error(
                f"[{func_name}] Failed after {max_retries + 1} attempts. "
                f"Last error: {last_error}"
            )
            
            if fallback_fn:
                logger.warning(f"[{func_name}] Using fallback function")
                try:
                    return fallback_fn(state, *args, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"[{func_name}] Fallback also failed: {fallback_error}")
                    last_error = fallback_error
            
            # Return error state for graph to handle
            current_errors = list(state.get(error_state_key, []) or [])
            error_entry = {
                "node": func_name,
                "error": str(last_error),
                "error_type": type(last_error).__name__,
            }
            
            return {
                error_state_key: current_errors + [str(last_error)],
                "last_error": error_entry,
            }
        
        return wrapper
    return decorator


# =========================================================================
# Utility Functions
# =========================================================================

def create_safe_hold_state(
    state: dict,
    reason: str,
    node_name: str = "unknown"
) -> dict:
    """
    Create a safe Hold state when node execution fails.
    
    Use this in fallback functions to return a consistent safe state.
    
    Args:
        state: Current agent state
        reason: Reason for the hold decision
        node_name: Name of the failing node
    
    Returns:
        Dict with Hold decision
    """
    from ..nodes.brooks_analyzer import create_hold_decision
    
    symbol = state.get("symbol", "BTC")
    brooks_analysis = state.get("brooks_analysis")
    
    return {
        "decisions": [create_hold_decision(
            symbol=symbol,
            wait_reason=f"[{node_name}] {reason}",
            brooks_analysis=brooks_analysis
        )],
        "warnings": state.get("warnings", []) + [f"Fallback triggered: {reason}"]
    }
