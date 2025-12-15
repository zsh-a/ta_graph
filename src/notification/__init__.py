"""
Notification module initialization
"""
from .alerts import send_alert, notify_trade_event

__all__ = ['send_alert', 'notify_trade_event']
