from typing import TypedDict, List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# --- Pydantic Models for State Data ---
# (These mirror the structure but are used within the TypedDict)

class MarketData(BaseModel):
    symbol: str = Field(description="Trading symbol, e.g., BTC/USDT")
    timeframe: str = Field(description="Timeframe, e.g., 1h")
    ohlcv: List[List[float]] = Field(description="Raw OHLCV data")
    current_price: float = Field(description="Current close price")
    ema20: Optional[float] = Field(default=None, description="Current EMA20 value")
    bar_data_table: str = Field(description="Formatted text table of recent bars for LLM")
    chart_image_path: Optional[str] = Field(default=None, description="Path to the chart image")

class Analysis(BaseModel):
    summary: str = Field(description="Summary of market condition")
    trend: str = Field(description="Market trend: BULLISH, BEARISH, or SIDEWAYS")
    key_levels: Dict[str, float] = Field(default_factory=dict, description="Key support and resistance levels")
    signal: str = Field(description="Trading signal: BUY, SELL, or HOLD")
    confidence: str = Field(default="medium", description="Confidence level")
    market_structure: str = Field(default="unknown", description="Market structure")

# --- Main Graph State ---

class AgentState(TypedDict):
    # Core Data
    symbol: str
    primary_timeframe: str
    
    # Market Data
    market_data: Optional[MarketData]  # Using Pydantic model for structured access
    market_states: List[Dict[str, Any]] # List of all market states (for multi-symbol support)
    
    # Account & History
    account_info: Optional[Dict[str, Any]] # Balance, PnL, Open Orders, etc.
    recent_trades_summary: Optional[str] # Text summary of recent trades
    
    # Analysis & Decision
    market_analysis: Optional[Dict[str, Any]] # Output from Analysis Node
    decisions: Optional[List[Dict[str, Any]]] # Output from Strategy Node (List of Decision objects)
    
    # Execution
    execution_results: Optional[List[Dict[str, Any]]] # Result of trade execution
    
    # Messages (for chat/debug history)
    messages: List[Dict[str, Any]]
