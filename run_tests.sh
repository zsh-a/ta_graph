#!/bin/bash
# Run all position management tests

export PYTHONPATH=/home/zs/workspace/ta_graph

echo "=========================================="
echo "Running Unit Tests"
echo "=========================================="

echo ""
echo "1. Testing Order Monitor..."
uv run pytest tests/nodes/test_order_monitor.py -v

echo ""
echo "2. Testing Position Sync..."
uv run pytest tests/nodes/test_position_sync.py -v

echo ""
echo "3. Testing Follow-through Analyzer..."
uv run pytest tests/nodes/test_followthrough_analyzer.py -v

echo ""
echo "4. Testing Risk Manager..."
uv run pytest tests/nodes/test_risk_manager.py -v

echo ""
echo "5. Testing Safety Modules..."
uv run pytest tests/safety/test_safety_modules.py -v

echo ""
echo "6. Testing Heartbeat Monitor..."
uv run pytest tests/monitoring/test_heartbeat.py -v

echo ""
echo "=========================================="
echo "Running Integration Tests"
echo "=========================================="

echo ""
echo "7. Testing Complete Workflow..."
uv run pytest tests/integration/test_workflow.py -v

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="

# Run all tests with coverage
uv run pytest tests/ -v --cov=src/nodes --cov=src/safety --cov=src/monitoring --cov-report=term-missing
