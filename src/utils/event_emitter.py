"""
Event emitter utilities for workflow tracing.
Provides standardized event emission with run_id tracking.
"""

from typing import Any
from .event_bus import get_event_bus

# Global run_id context for current workflow execution
_current_run_id: str | None = None


def set_current_run_id(run_id: str | None) -> None:
    """Set the current run_id for this workflow tick."""
    global _current_run_id
    _current_run_id = run_id


def get_current_run_id() -> str | None:
    """Get the current run_id for this workflow tick."""
    return _current_run_id


def emit_node_event(
    event_type: str,
    node: str,
    data: dict[str, Any] | None = None,
    message: str | None = None
) -> None:
    """
    Emit a node event with automatic run_id injection.
    
    Args:
        event_type: Type of event (e.g., 'node_start', 'analysis_complete')
        node: Name of the node emitting the event
        data: Additional event data
        message: Optional human-readable message
    """
    bus = get_event_bus()
    
    event_data: dict[str, Any] = {
        "node": node,
    }
    
    # Inject run_id if available
    if _current_run_id:
        event_data["run_id"] = _current_run_id
    
    # Merge additional data
    if data:
        event_data.update(data)
    
    # Add message to data if provided
    if message:
        event_data["message"] = message
    
    bus.emit_sync(event_type, event_data)
