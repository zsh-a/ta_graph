"""
Tests for heartbeat monitor
"""

import pytest
import time
from src.monitoring.heartbeat import HeartbeatMonitor


class TestHeartbeatMonitor:
    """Test heartbeat monitoring"""
    
    def test_initialization(self):
        """Should initialize with correct settings"""
        monitor = HeartbeatMonitor(interval_seconds=30, timeout_seconds=120)
        
        assert monitor.interval == 30
        assert monitor.timeout == 120
        assert monitor.running is False
    
    def test_start_and_stop(self):
        """Should start and stop monitoring"""
        monitor = HeartbeatMonitor(interval_seconds=1)
        
        monitor.start()
        assert monitor.running is True
        assert monitor.thread is not None
        
        monitor.stop()
        assert monitor.running is False
    
    def test_record_heartbeat(self):
        """Should record heartbeat"""
        monitor = HeartbeatMonitor()
        
        initial_count = monitor.heartbeat_count
        monitor.beat()
        
        assert monitor.heartbeat_count == initial_count + 1
        assert time.time() - monitor.last_heartbeat < 1
    
    def test_get_status(self):
        """Should return status information"""
        monitor = HeartbeatMonitor()
        monitor.beat()
        
        status = monitor.get_status()
        
        assert "running" in status
        assert "heartbeat_count" in status
        assert "is_healthy" in status
        assert status["heartbeat_count"] == 1
        assert status["is_healthy"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
