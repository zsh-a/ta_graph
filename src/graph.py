"""
Enhanced LangGraph with Brooks Analysis and HITL
Integrates all optimization components into the trading workflow.
"""

from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph as CompiledGraph
from langgraph.checkpoint.sqlite import SqliteSaver
import os

from .state import AgentState
from .nodes.market_data import fetch_market_data
from .nodes.brooks_analyzer import brooks_analyzer
from .nodes.strategy_enhanced import generate_strategy
from .nodes.risk import assess_risk
from .nodes.execution import execute_trade
from .logger import get_logger

logger = get_logger(__name__)


# ========== Analysis Subgraph (Singleton) ==========

_analysis_subgraph: Optional[CompiledGraph] = None


def get_analysis_subgraph() -> CompiledGraph:
    """
    获取编译好的 Analysis Subgraph（单例模式）
    
    使用 LangGraph Subgraph 模式，避免每次调用时重新创建图。
    当 parent graph 和 subgraph 共享 state keys 时，
    可以直接将 compiled subgraph 传入 add_node()。
    
    Returns:
        编译好的 Analysis Graph
    """
    global _analysis_subgraph
    
    if _analysis_subgraph is None:
        logger.info("Creating Analysis Subgraph (singleton)...")
        
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("market_data", fetch_market_data)
        workflow.add_node("brooks_analyzer", brooks_analyzer)
        workflow.add_node("strategy", generate_strategy)
        workflow.add_node("risk", assess_risk)
        workflow.add_node("execution", execute_trade)
        
        # Define flow: linear pipeline
        workflow.set_entry_point("market_data")
        workflow.add_edge("market_data", "brooks_analyzer")
        workflow.add_edge("brooks_analyzer", "strategy")
        workflow.add_edge("strategy", "risk")
        workflow.add_edge("risk", "execution")
        workflow.add_edge("execution", END)
        
        # Compile without checkpointer - parent graph handles persistence
        _analysis_subgraph = workflow.compile()
        
        logger.info("✓ Analysis Subgraph created")
    
    return _analysis_subgraph

def create_graph(enable_checkpointing: bool = True, enable_hitl: bool = False):
    """
    Create the enhanced trading graph with Brooks analysis.
    
    Args:
        enable_checkpointing: Enable state persistence
        enable_hitl: Enable Human-in-the-Loop approval (pauses at execution)
        
    Returns:
        Compiled graph
    """
    logger.info("Creating enhanced trading graph...")
    
    workflow = StateGraph(AgentState)
    
    # ========== Add Nodes ==========
    
    # 1. Market Data Node - Fetch OHLC and generate charts
    workflow.add_node("market_data", fetch_market_data)
    
    # 2. Brooks Analyzer Node - Al Brooks specific analysis (NEW)
    workflow.add_node("brooks_analyzer", brooks_analyzer)
    
    # 4. Strategy Node - Generate trading decisions
    workflow.add_node("strategy", generate_strategy)
    
    # 5. Risk Node - Validate and calculate exact prices
    workflow.add_node("risk", assess_risk)
    
    # 6. Execution Node - Execute trades
    workflow.add_node("execution", execute_trade)
    
    # ========== Define Flow ==========
    
    # Entry point
    workflow.set_entry_point("market_data")
    
    # Linear flow with Brooks analyzer before strategy
    workflow.add_edge("market_data", "brooks_analyzer")
    workflow.add_edge("brooks_analyzer", "strategy")
    workflow.add_edge("strategy", "risk")
    workflow.add_edge("risk", "execution")
    workflow.add_edge("execution", END)
    
    # ========== Compile with Options ==========
    
    compile_kwargs = {}
    
    # Add checkpointing for context persistence
    if enable_checkpointing:
        checkpoint_dir = os.path.abspath("./checkpoints")
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)
        
        checkpoint_path = f"{checkpoint_dir}/trading.db"
            
        # Create SqliteSaver instance directly (not using from_conn_string which is a context manager)
        memory = SqliteSaver.from_conn_string(checkpoint_path).__enter__()
        compile_kwargs['checkpointer'] = memory
        logger.info(f"Checkpointing enabled: {checkpoint_path}")
    
    # Add HITL interrupt point
    if enable_hitl:
        compile_kwargs['interrupt_before'] = ["execution"]
        logger.info("HITL enabled: Will pause before execution for approval")
    
    app = workflow.compile(**compile_kwargs)
    
    logger.info("Graph created successfully")
    return app

def resume_graph_after_approval(app, config: dict):
    """
    Resume graph execution after human approval in HITL mode.
    
    Args:
        app: Compiled graph
        config: Graph config with thread_id
        
    Usage:
        # Initial run (will pause at execution)
        config = {"configurable": {"thread_id": "btc_session_1"}}
        result = app.invoke(initial_state, config=config)
        
        # After human approval, resume
        result = resume_graph_after_approval(app, config)
    """
    logger.info("Resuming graph after approval...")
    
    # Resume by invoking with None state (continues from checkpoint)
    result = app.invoke(None, config=config)
    
    return result
