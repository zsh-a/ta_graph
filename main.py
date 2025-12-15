from langfuse import observe
from src.graph import create_graph
from src.utils.timeframe_config import get_primary_timeframe
import json

@observe(name="Run Trading Agent")
def main():
    print("Starting VL Trading Agent (Migrated)...")
    app = create_graph()
    
    # 从配置获取时间周期
    primary_timeframe = get_primary_timeframe()
    
    # Initial state
    initial_state = {
        "symbol": "BTC/USDT",
        "primary_timeframe": primary_timeframe,
        "messages": [],
        "positions": {},
        "account_info": {
            "available_cash": 10000.0,
            "daily_pnl_percent": 0.0,
            "open_orders": []
        }
    }
    
    print(f"Running graph for {initial_state['symbol']}...")
    # Invoke the graph
    result = app.invoke(initial_state)
    
    print("\n=== Final State ===")
    
    if result.get("market_analysis"):
        print("\n--- Market Analysis ---")
        ma = result['market_analysis']
        print(f"Summary: {ma.get('summary')}")
        print(f"Trend: {ma.get('trend')}")
        print(f"Signal: {ma.get('signal')}")
        
    if result.get("decisions"):
        print("\n--- Decisions ---")
        for d in result['decisions']:
            print(f"Operation: {d.get('operation')}")
            print(f"Symbol: {d.get('symbol')}")
            print(f"Rationale: {d.get('rationale')}")
            if d.get('buy'):
                print(f"Buy Order: {d['buy']}")
            if d.get('sell'):
                print(f"Sell Order: {d['sell']}")
        
    if result.get("execution_results"):
        print("\n--- Execution Results ---")
        for ex in result['execution_results']:
            print(f"Result: {ex}")
            
    print("\nDone.")

if __name__ == "__main__":
    main()
