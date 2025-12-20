"""
Example: Running the Enhanced Al Brooks Trading System
Demonstrates all optimization features:
- Brooks-style chart rendering
- Brooks analyzer with validation
- Trade filters
- Human-in-the-Loop approval
- Dynamic prompts
- State persistence with checkpointing
"""

import asyncio
from src.graph import create_graph
from src.utils.timeframe_config import get_primary_timeframe
from src.logger import get_logger
from src.utils.trade_filters import get_trade_filter
from src.utils.notification_service import get_notification_service
from langfuse import observe

logger = get_logger(__name__)

@observe(name="Al brooks basic")
def main_basic():
    """
    Basic example: Run graph with Brooks analyzer (no HITL).
    Good for testing and backtesting.
    """
    print("=" * 80)
    print("Al Brooks Trading System - Basic Mode")
    print("=" * 80)
    
    # Create graph with checkpointing but no HITL
    app = create_graph(
        enable_checkpointing=False,  # Disabled by default - requires langgraph-checkpoint-sqlite
        enable_hitl=False
    )
    
    # Initial state
    initial_state = {
        "symbol": "BTC/USDT",
        "primary_timeframe": get_primary_timeframe(),
        "messages": [],
        "positions": {},
        "account_info": {
            "available_cash": 10000.0,
            "daily_pnl_percent": 0.0,
            "open_orders": []
        }
    }
    
    # Run with session ID for state persistence
    config = {"configurable": {"thread_id": "btc_session_basic"}}
    
    print("\n🚀 Running trading cycle...\n")
    result = app.invoke(initial_state, config=config)
    
    # Display results
    print_results(result)
    
    # Show filter status
    trade_filter = get_trade_filter()
    print("\n📊 Trade Filter Status:")
    print(trade_filter.get_status())

@observe(name="Al brooks hitl")
def main_with_hitl():
    """
    Advanced example: Run with Human-in-the-Loop approval.
    Graph will pause before execution for human approval.
    """
    print("=" * 80)
    print("Al Brooks Trading System - HITL Mode")
    print("=" * 80)
    
    # Create graph with HITL enabled
    app = create_graph(
        enable_checkpointing=False,
        enable_hitl=True
    )
    
    initial_state = {
        "symbol": "BTC/USDT",
        "primary_timeframe": get_primary_timeframe(),
        "messages": [],
        "positions": {},
        "account_info": {
            "available_cash": 10000.0,
            "daily_pnl_percent": 0.0,
            "open_orders": []
        }
    }
    
    config = {"configurable": {"thread_id": "btc_session_hitl"}}
    
    print("\n🚀 Running trading cycle (will pause for approval)...\n")
    
    # First invoke - will stop at execution node
    result = app.invoke(initial_state, config=config)
    
    print_results(result)
    
    # Check if there's a decision that needs approval
    decisions = result.get("decisions", [])
    if decisions and decisions[0].get("operation") != "Hold":
        print("\n⏸️  Graph paused before execution")
        print("   Human approval required!")
        print("\n   To approve: Set APPROVAL environment variable or use notification service")
        print("   To resume: Call app.invoke(None, config=config)")
        
        # In a real scenario, you would wait for human input
        # For demo, we'll simulate approval
        print("\n   [DEMO: Simulating approval...]")
        
        # Resume execution
        print("\n▶️  Resuming execution...")
        result = app.invoke({}, config=config)  # Pass empty dict, not None
        
        print_results(result)
    else:
        print("\n✅ Decision was Hold - no approval needed")

async def main_with_telegram():
    """
    Example: Run with Telegram notifications for HITL.
    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
    """
    print("=" * 80)
    print("Al Brooks Trading System - Telegram HITL Mode")
    print("=" * 80)
    
    # Get notification service
    notifier = get_notification_service()
    
    if notifier.platform != "telegram":
        print("\n⚠️  Warning: NOTIFICATION_PLATFORM is not set to 'telegram'")
        print("   Set in .env: NOTIFICATION_PLATFORM=telegram")
        print("   Also set: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return
    
    # Create graph
    app = create_graph(enable_checkpointing=True, enable_hitl=True)
    
    initial_state = {
        "symbol": "BTC/USDT",
        "primary_timeframe": get_primary_timeframe(),
        "messages": [],
        "positions": {},
        "account_info": {
            "available_cash": 10000.0,
            "daily_pnl_percent": 0.0,
            "open_orders": []
        }
    }
    
    config = {"configurable": {"thread_id": "btc_session_telegram"}}
    
    print("\n🚀 Running trading cycle with Telegram notifications...\n")
    
    result = app.invoke(initial_state, config=config)
    
    print_results(result)
    
    # If decision needs approval, request via Telegram
    decisions = result.get("decisions", [])
    if decisions and decisions[0].get("operation") != "Hold":
        decision = decisions[0]
        brooks_analysis = result.get("brooks_analysis")
        chart_path = result.get("chart_image_path")
        
        print("\n📱 Sending approval request to Telegram...")
        
        approved = await notifier.request_approval(
            decision=decision,
            chart_path=str(chart_path) if chart_path else "",
            brooks_analysis=brooks_analysis
        )
        
        if approved:
            print("\n✅ Trade approved via Telegram")
            print("▶️  Resuming execution...")
            
            final_result = app.invoke({}, config=config)  # Pass empty dict, not None
            print_results(final_result)
        else:
            print("\n❌ Trade rejected via Telegram")
            print("   No execution performed")

def print_results(result: dict):
    """Pretty print results"""
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    # Brooks Analysis
    if result.get("brooks_analysis"):
        ba = result["brooks_analysis"]
        print("\n📊 BROOKS ANALYSIS:")
        print(f"   Market Cycle: {ba.get('market_cycle', 'N/A')}")
        print(f"   Always In: {ba.get('always_in_direction', 'N/A').upper()}")
        print(f"   Signal Bar Quality: {ba.get('signal_bar', {}).get('quality_score', 0)}/10")
        print(f"   Setup Quality: {ba.get('setup_quality', 0)}/10")
        
        patterns = ba.get('detected_patterns', [])
        if patterns:
            print(f"   Patterns: {', '.join([p.get('pattern_type', 'Unknown') for p in patterns])}")
        
        # Validation
        if '_validation' in ba:
            validation = ba['_validation']
            if validation.get('warnings'):
                print(f"\n   ⚠️  Validation Warnings: {len(validation['warnings'])}")
                for warning in validation['warnings'][:2]:
                    print(f"      - {warning}")
    
    # Market Analysis
    if result.get("market_analysis"):
        ma = result["market_analysis"]
        print("\n📈 MARKET ANALYSIS:")
        print(f"   Summary: {ma.get('summary', 'N/A')}")
        print(f"   Trend: {ma.get('trend', 'N/A')}")
        print(f"   Signal: {ma.get('signal', 'N/A')}")
    
    # Decision
    if result.get("decisions"):
        decisions = result["decisions"]
        print("\n💰 DECISION:")
        for decision in decisions:
            operation = decision.get('operation', 'N/A')
            print(f"   Operation: {operation}")
            print(f"   Symbol: {decision.get('symbol', 'N/A')}")
            print(f"   Probability: {decision.get('probability_score', 0):.1f}%")
            
            if operation == "Hold":
                wait_reason = decision.get('wait_reason', 'No reason provided')
                print(f"   Wait Reason: {wait_reason}")
            else:
                print(f"   Rationale: {decision.get('rationale', 'N/A')}")
                
                if decision.get('buy'):
                    buy = decision['buy']
                    print(f"   Buy Order: {buy.get('orderType')} | Risk: {buy.get('riskPercent')}%")
                
                if decision.get('sell'):
                    sell = decision['sell']
                    print(f"   Sell Order: {sell.get('orderType')} | Risk: {sell.get('riskPercent')}%")
    
    # Execution
    if result.get("execution_results"):
        print("\n⚡ EXECUTION:")
        for ex_result in result["execution_results"]:
            print(f"   {ex_result}")
    
    # Chart
    if result.get("chart_image_path"):
        print(f"\n📸 Chart: {result['chart_image_path']}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "basic"
    
    if mode == "basic":
        main_basic()
    elif mode == "hitl":
        main_with_hitl()
    elif mode == "telegram":
        asyncio.run(main_with_telegram())
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python example_brooks_system.py [basic|hitl|telegram]")
        sys.exit(1)
