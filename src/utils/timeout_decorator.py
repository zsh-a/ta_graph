"""
Timeout decorator for LangGraph nodes.
Provides timeout protection with optional fallback functions.
"""
import functools
import signal
from typing import Any, Callable, Optional
from ..logger import get_logger

logger = get_logger(__name__)


class TimeoutError(Exception):
    """Raised when operation exceeds time limit"""
    pass


def with_timeout(
    timeout_seconds: int,
    fallback_fn: Optional[Callable] = None,
    operation_name: str = "operation"
):
    """
    Decorator to add timeout protection to synchronous functions.
    
    Args:
        timeout_seconds: Maximum execution time in seconds
        fallback_fn: Optional fallback function called if timeout occurs
        operation_name: Name for logging purposes
        
    Usage:
        @with_timeout(timeout_seconds=120, operation_name="Brooks Analysis")
        def my_function(state):
            # Long-running operation
            return result
    
    Note:
        Uses SIGALRM which only works on Unix systems.
        For Docker containers running Linux, this works as expected.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def timeout_handler(signum, frame):
                raise TimeoutError(f"{operation_name} exceeded {timeout_seconds}s timeout")
            
            # Set up signal handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            
            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Cancel alarm
                return result
                
            except TimeoutError as e:
                signal.alarm(0)  # Cancel alarm
                logger.error(f"⏱️ TIMEOUT: {e}")
                
                if fallback_fn:
                    logger.warning(f"Using fallback for {operation_name}")
                    return fallback_fn(*args, **kwargs)
                else:
                    raise
                    
            except Exception as e:
                signal.alarm(0)  # Cancel alarm on any error
                raise
                
            finally:
                # Restore old handler
                signal.signal(signal.SIGALRM, old_handler)
                    
        return wrapper
    return decorator
