"""
Persistence Manager
Centralizes database operations for the trading workflow.
"""

from typing import Any, Union, Optional, cast
from datetime import datetime, timezone
import json
from uuid import uuid4

from sqlalchemy.orm import Session
from .models import (
    WorkflowRun, MarketObservation, AIAnalysis, 
    TradingDecision, ExecutionRecord, OperationType, SymbolType, ModelType, Chat
)
from .session import get_session
from ..logger import get_logger

logger = get_logger(__name__)

class PersistenceManager:
    """
    Manager for persisting trading workflow data.
    """
    
    def __init__(self, db: Session | None = None):
        self._db = db
        self._should_close = False
        if self._db is None:
            self._db = get_session()
            self._should_close = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._should_close and self._db:
            try:
                if exc_type is None:
                    # Flush changes to database and commit
                    # logger.info(f"PersistenceManager.__exit__: Flushing session (new={len(self._db.new)}, dirty={len(self._db.dirty)}, deleted={len(self._db.deleted)})")
                    self._db.flush()
                    # logger.info(f"PersistenceManager.__exit__: Committing session")
                    self._db.commit()
                    # logger.info(f"PersistenceManager.__exit__: Commit successful")
                else:
                    # Rollback on exception
                    # logger.warning(f"PersistenceManager.__exit__: Rolling back due to exception: {exc_type}")
                    self._db.rollback()
            finally:
                # logger.info(f"PersistenceManager.__exit__: Closing session")
                self._db.close()

    def create_run(
        self, 
        thread_id: str, 
        symbol: str, 
        timeframe: str, 
        status: str
    ) -> WorkflowRun:
        """Create a new workflow run record."""
        run = WorkflowRun(
            threadId=thread_id,
            symbol=symbol,
            timeframe=timeframe,
            status=status
        )
        self._db.add(run)
        self._db.commit()
        self._db.refresh(run)
        return run

    def update_run_status(self, run_id: str, status: str):
        """Update the status of an existing run."""
        run = self._db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if run:
            run.status = status
            self._db.commit()

    def record_observation(
        self, 
        run_id: str, 
        price: float, 
        bar_data: list[dict], 
        indicators: dict | None = None
    ) -> MarketObservation:
        """Record market state at a specific point in time."""
        observation = MarketObservation(
            runId=run_id,
            price=price,
            barData=bar_data,
            indicators=indicators or {}
        )
        self._db.add(observation)
        self._db.commit()
        self._db.refresh(observation)
        return observation

    def record_analysis(
        self,
        run_id: str,
        node_name: str,
        content: Any,
        model_provider: str | None = None,
        model_name: str | None = None,
        raw_response: Any | None = None,
        reasoning: str | None = None,
        prompt: str | None = None,
        token_usage: dict | None = None,
        latency_ms: float | None = None
    ) -> AIAnalysis:
        """Record analysis result from a node."""
        analysis = AIAnalysis(
            runId=run_id,
            nodeName=node_name,
            modelProvider=model_provider,
            modelName=model_name,
            content=content,
            rawResponse=raw_response,
            reasoning=reasoning,
            prompt=prompt,
            tokenUsage=token_usage,
            latencyMs=latency_ms
        )
        self._db.add(analysis)
        self._db.commit()
        self._db.refresh(analysis)
        return analysis

    def record_chat(
        self,
        model: str | ModelType,
        reasoning: str,
        user_prompt: str,
        chat_content: str = "<no chat>"
    ) -> Chat:
        """Record chat for legacy table support."""
        if isinstance(model, str):
            model = ModelType[model] if model in ModelType.__members__ else ModelType.Deepseek
            
        chat_record = Chat(
            model=model,
            chat=chat_content,
            reasoning=reasoning,
            userPrompt=user_prompt
        )
        self._db.add(chat_record)
        self._db.commit()
        self._db.refresh(chat_record)
        return chat_record

    def record_decision(
        self,
        run_id: str,
        operation: Union[str, OperationType],
        symbol: Union[str, SymbolType],
        rationale: str,
        probability_score: float = 0.0,
        wait_reason: str | None = None,
        entry_rules: dict | None = None,
        stop_loss_rules: dict | None = None,
        take_profit_rules: dict | None = None,
        prediction: dict | None = None
    ) -> TradingDecision:
        """Record a trading decision."""
        # Map string to Enum if needed
        if isinstance(operation, str):
            operation = OperationType[operation] if operation in OperationType.__members__ else OperationType.Hold
        
        if isinstance(symbol, str):
            # Try to handle symbol string like 'BTC/USDT' or 'BTC'
            symbol_core = symbol.split('/')[0] if '/' in symbol else symbol
            symbol = SymbolType[symbol_core] if symbol_core in SymbolType.__members__ else SymbolType.BTC

        decision = TradingDecision(
            runId=run_id,
            operation=operation,
            symbol=symbol,
            rationale=rationale,
            probabilityScore=probability_score,
            waitReason=wait_reason,
            entryRules=entry_rules,
            stopLossRules=stop_loss_rules,
            takeProfitRules=take_profit_rules,
            prediction=prediction
        )
        self._db.add(decision)
        self._db.commit()
        self._db.refresh(decision)
        return decision

    def record_execution(
        self,
        run_id: str,
        decision_id: str | None,
        symbol: str,
        side: str,
        order_id: str | None = None,
        status: str = "PENDING",
        executed_price: float | None = None,
        executed_amount: float | None = None,
        error: str | None = None,
        metadata: dict | None = None
    ) -> ExecutionRecord:
        """Record trade execution result."""
        execution = ExecutionRecord(
            runId=run_id,
            decisionId=decision_id,
            symbol=symbol,
            side=side,
            orderId=order_id,
            status=status,
            executedPrice=executed_price,
            executedAmount=executed_amount,
            error=error,
            additionalData=metadata or {}
        )
        self._db.add(execution)
        self._db.commit()
        self._db.refresh(execution)
        return execution

    def get_latest_run(self, thread_id: str) -> Optional[WorkflowRun]:
        """Get the most recent run for a thread."""
        return self._db.query(WorkflowRun)\
            .filter(WorkflowRun.threadId == thread_id)\
            .order_by(WorkflowRun.createdAt.desc())\
            .first()

    def get_recent_logs(self, limit: int = 50) -> list[dict]:
        """
        Fetch recent executions, decisions, and chats to convert into standard log format.
        Used for dashboard history rehydration.
        Ensures all timestamps are ISO 8601 with UTC offset for correct frontend filtering.
        """
        if self._db is None:
            return []

        logs = []
        
        def to_iso(dt: datetime) -> str:
            """Ensure datetime is timezone-aware (UTC) before ISO format."""
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()

        # 1. Fetch Executions
        # Note: Using createdAt as the canonical timestamp (ExecutionRecord uses createdAt, not timestamp)
        executions = self._db.query(ExecutionRecord).order_by(ExecutionRecord.createdAt.desc()).limit(limit).all()
        for exc in executions:
            logs.append({
                "type": "execution",
                "timestamp": to_iso(exc.createdAt),
                "node": "execution",
                "message": f"Execution: {exc.side} {exc.symbol} ({exc.status})",
                "data": {
                    "side": exc.side,
                    "symbol": exc.symbol,
                    "status": exc.status,
                    "price": exc.executedPrice,
                    "amount": exc.executedAmount,
                    "order_id": exc.orderId
                }
            })
            
        # 2. Fetch Decisions (Strategy)
        decisions = self._db.query(TradingDecision).order_by(TradingDecision.createdAt.desc()).limit(limit).all()
        for dec in decisions:
            logs.append({
                "type": "decision",
                "timestamp": to_iso(dec.createdAt),
                "node": "strategy",
                "message": f"Strategy generated: {dec.operation}",
                "data": {
                    "operation": dec.operation.value if hasattr(dec.operation, 'value') else dec.operation,
                    "symbol": dec.symbol.value if hasattr(dec.symbol, 'value') else dec.symbol,
                    "probability_score": dec.probabilityScore,
                    "rationale": dec.rationale
                }
            })
            
        # 3. Fetch Chats (LLM Logs)
        chats = self._db.query(Chat).order_by(Chat.createdAt.desc()).limit(limit).all()
        for chat in chats:
            logs.append({
                "type": "llm_log",
                "timestamp": to_iso(chat.createdAt),
                "node": "llm",
                "message": f"LLM Interaction ({chat.model.name if hasattr(chat.model, 'name') else chat.model})",
                "data": {
                    "model": chat.model.value if hasattr(chat.model, 'value') else str(chat.model),
                    "prompt": chat.userPrompt,
                    "response": chat.chat,
                    "reasoning": chat.reasoning
                }
            })

        # Sort by timestamp (string comparison of ISO dates works for same timezone, but object sort is safer if we parsed back,
        # but here we sort string. ISO UTC strings sort correctly.)
        logs.sort(key=lambda x: x["timestamp"])
        return logs
    
    def store_dashboard_event(self, event: dict):
        """Store a dashboard event for log persistence."""
        from .models import DashboardEvent
        
        db_event = DashboardEvent(
            type=event.get('type'),
            node=event.get('data', {}).get('node') if isinstance(event.get('data'), dict) else None,
            message=event.get('message'),
            data=event.get('data'),
            timestamp=datetime.fromisoformat(event['timestamp']) if 'timestamp' in event and isinstance(event['timestamp'], str) else datetime.now(timezone.utc)
        )
        self._db.add(db_event)
        # Note: commit is handled by context manager __exit__
    
    def get_recent_dashboard_events(self, limit: int = 100) -> list[dict]:
        """Get recent dashboard events for log rehydration."""
        from .models import DashboardEvent
        
        if self._db is None:
            return []
        
        def to_iso(dt: datetime) -> str:
            """Ensure datetime is timezone-aware (UTC) before ISO format."""
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        
        events = self._db.query(DashboardEvent)\
            .order_by(DashboardEvent.timestamp.desc())\
            .limit(limit)\
            .all()
        
        result = [{
            'type': e.type,
            'timestamp': to_iso(e.timestamp),
            'data': e.data if e.data else {},
            'message': e.message
        } for e in reversed(events)]  # Reverse to get chronological order
        
        return result

    def get_runs(
        self, 
        start_date: datetime | None = None, 
        end_date: datetime | None = None, 
        symbol: str | None = None,
        limit: int = 100
    ) -> list[dict]:
        """Fetch historical workflow runs with filtering."""
        query = self._db.query(WorkflowRun)
        
        if start_date:
            query = query.filter(WorkflowRun.createdAt >= start_date)
        if end_date:
            query = query.filter(WorkflowRun.createdAt <= end_date)
        if symbol:
            query = query.filter(WorkflowRun.symbol == symbol)
            
        runs = query.order_by(WorkflowRun.createdAt.desc()).limit(limit).all()
        
        return [
            {
                "id": run.id,
                "thread_id": run.threadId,
                "symbol": run.symbol,
                "timeframe": run.timeframe,
                "status": run.status,
                "created_at": run.createdAt.isoformat() if run.createdAt.tzinfo else run.createdAt.replace(tzinfo=timezone.utc).isoformat()
            }
            for run in runs
        ]

    def get_run_details(self, run_id: str) -> dict:
        """Fetch all related data for a single workflow run."""
        run = self._db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if not run:
            return {}
            
        def to_iso(dt: datetime) -> str:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()

        # Fetch all related records
        observations = self._db.query(MarketObservation).filter(MarketObservation.runId == run_id).all()
        analyses = self._db.query(AIAnalysis).filter(AIAnalysis.runId == run_id).all()
        decisions = self._db.query(TradingDecision).filter(TradingDecision.runId == run_id).all()
        executions = self._db.query(ExecutionRecord).filter(ExecutionRecord.runId == run_id).all()
        
        return {
            "id": run.id,
            "thread_id": run.threadId,
            "symbol": run.symbol,
            "timeframe": run.timeframe,
            "status": run.status,
            "created_at": to_iso(run.createdAt),
            "observations": [
                {
                    "price": obs.price,
                    "bar_data": obs.barData,
                    "indicators": obs.indicators,
                    "timestamp": to_iso(obs.timestamp)
                } for obs in observations
            ],
            "analyses": [
                {
                    "node_name": ana.nodeName,
                    "content": ana.content,
                    "reasoning": ana.reasoning,
                    "prompt": ana.prompt,
                    "timestamp": to_iso(ana.createdAt)
                } for ana in analyses
            ],
            "decisions": [
                {
                    "operation": dec.operation.value if hasattr(dec.operation, 'value') else dec.operation,
                    "symbol": dec.symbol.value if hasattr(dec.symbol, 'value') else dec.symbol,
                    "rationale": dec.rationale,
                    "probability_score": dec.probabilityScore,
                    "wait_reason": dec.waitReason,
                    "entry_rules": dec.entryRules,
                    "stop_loss_rules": dec.stopLossRules,
                    "take_profit_rules": dec.takeProfitRules,
                    "timestamp": to_iso(dec.createdAt)
                } for dec in decisions
            ],
            "executions": [
                {
                    "side": exc.side,
                    "symbol": exc.symbol,
                    "status": exc.status,
                    "executed_price": exc.executedPrice,
                    "executed_amount": exc.executedAmount,
                    "error": exc.error,
                    "timestamp": to_iso(exc.createdAt)
                } for exc in executions
            ]
        }

# Helper function to get manager
def get_persistence_manager(db: Session | None = None) -> PersistenceManager:
    return PersistenceManager(db)
