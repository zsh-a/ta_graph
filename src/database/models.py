"""
Database models for ta_graph
SQLAlchemy ORM models migrated from Super-nof1.ai Prisma schema
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from uuid import uuid4
import enum

Base = declarative_base()

# Enums
class OperationType(str, enum.Enum):
    Buy = "Buy"
    Sell = "Sell"
    Hold = "Hold"

class SymbolType(str, enum.Enum):
    BTC = "BTC"
    ETH = "ETH"
    BNB = "BNB"
    SOL = "SOL"
    DOGE = "DOGE"
    ADA = "ADA"
    DOT = "DOT"
    MATIC = "MATIC"
    AVAX = "AVAX"
    LINK = "LINK"

class ModelType(str, enum.Enum):
    Deepseek = "Deepseek"
    DeepseekThinking = "DeepseekThinking"
    Qwen = "Qwen"
    Doubao = "Doubao"
    QwenVLSFT = "QwenVLSFT"

# Models

class ModelAccount(Base):
    """
    Model Account: Real exchange account for each AI model with independent API credentials
    """
    __tablename__ = "ModelAccount"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    model = Column(SQLEnum(ModelType), unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    
    # Exchange API credentials (should be encrypted in production)
    bitgetApiKey = Column(String, nullable=False)
    bitgetApiSecret = Column(String, nullable=False)
    bitgetPassphrase = Column(String, nullable=True)
    
    # Account tracking (synced from exchange API)
    initialCapital = Column(Float, default=0.0)
    currentBalance = Column(Float, default=0.0)
    availableBalance = Column(Float, default=0.0)
    
    # Performance metrics
    totalTrades = Column(Integer, default=0)
    winningTrades = Column(Integer, default=0)
    losingTrades = Column(Integer, default=0)
    totalPnL = Column(Float, default=0.0)
    totalPnLPercentage = Column(Float, default=0.0)
    
    # Risk metrics
    maxDrawdown = Column(Float, default=0.0)
    sharpeRatio = Column(Float, default=0.0)
    
    # Status
    isActive = Column(Boolean, default=True, index=True)
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    tradings = relationship("Trading", back_populates="modelAccount", cascade="all, delete-orphan")
    performanceSnapshots = relationship("ModelPerformanceSnapshot", back_populates="modelAccount", cascade="all, delete-orphan")


class Chat(Base):
    """
    AI Chat/Reasoning records
    """
    __tablename__ = "Chat"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    model = Column(SQLEnum(ModelType), default=ModelType.Deepseek)
    chat = Column(String, default="<no chat>")
    reasoning = Column(String, nullable=False)
    userPrompt = Column(String, nullable=False)
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    tradings = relationship("Trading", back_populates="chat", cascade="all, delete-orphan")


class Trading(Base):
    """
    Trading records - decisions and executions
    """
    __tablename__ = "Trading"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    symbol = Column(SQLEnum(SymbolType), nullable=False)
    operation = Column(SQLEnum(OperationType), nullable=False)
    amount = Column(Integer, nullable=True)
    pricing = Column(Integer, nullable=True)
    stopLoss = Column(Integer, nullable=True)
    takeProfit = Column(Integer, nullable=True)
    
    # Actual monetary risk taken on this trade
    riskAmount = Column(Float, nullable=True)
    
    # K-line prediction data (JSON format)
    prediction = Column(JSON, nullable=True)
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    chatId = Column(String, ForeignKey("Chat.id", ondelete="CASCADE"), nullable=True)
    modelAccountId = Column(String, ForeignKey("ModelAccount.id", ondelete="CASCADE"), nullable=True)
    
    # Relationships
    chat = relationship("Chat", back_populates="tradings")
    modelAccount = relationship("ModelAccount", back_populates="tradings")
    lessons = relationship("TradingLesson", back_populates="trade", cascade="all, delete-orphan")


class TradingLesson(Base):
    """
    Trading lessons - learning feedback from completed trades
    """
    __tablename__ = "TradingLesson"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    tradeId = Column(String, ForeignKey("Trading.id", ondelete="CASCADE"), nullable=False)
    
    symbol = Column(SQLEnum(SymbolType), nullable=False, index=True)
    decision = Column(String, nullable=False)  # Buy/Sell/Hold
    outcome = Column(String, nullable=False, index=True)  # profit/loss/pending
    pnl = Column(Float, nullable=False)  # Profit/Loss amount
    pnlPercentage = Column(Float, nullable=False)  # Profit/Loss percentage
    lessonText = Column(String, nullable=False)  # Lesson learned
    exitReason = Column(String, nullable=False)  # Why trade was closed
    
    # Context data for learning
    marketConditions = Column(JSON, nullable=True)
    indicatorsAtEntry = Column(JSON, nullable=True)
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    trade = relationship("Trading", back_populates="lessons")


class ModelPerformanceSnapshot(Base):
    """
    Model Performance Snapshot - track performance over time
    """
    __tablename__ = "ModelPerformanceSnapshot"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    modelAccountId = Column(String, ForeignKey("ModelAccount.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Snapshot metrics
    balance = Column(Float, nullable=False)
    totalPnL = Column(Float, nullable=False)
    totalPnLPercentage = Column(Float, nullable=False)
    totalTrades = Column(Integer, nullable=False)
    winRate = Column(Float, nullable=False)
    sharpeRatio = Column(Float, nullable=False)
    maxDrawdown = Column(Float, nullable=False)
    openPositions = Column(Integer, default=0)
    
    snapshotDate = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    modelAccount = relationship("ModelAccount", back_populates="performanceSnapshots")


class Metrics(Base):
    """
    General metrics tracking (optional)
    """
    __tablename__ = "Metrics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False)
    model = Column(SQLEnum(ModelType), nullable=False)
    metrics = Column(JSON, nullable=False)
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
# Production-Grade Persistence Models

class WorkflowRun(Base):
    """
    Master record for each LangGraph tick/workflow execution.
    """
    __tablename__ = "WorkflowRun"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    threadId = Column(String, index=True)  # Link to LangGraph thread_id
    symbol = Column(String, nullable=False, index=True)
    timeframe = Column(String, nullable=False)
    status = Column(String, nullable=False)  # 'hunting', 'managing', etc.
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    observations = relationship("MarketObservation", back_populates="run", cascade="all, delete-orphan")
    analyses = relationship("AIAnalysis", back_populates="run", cascade="all, delete-orphan")
    decisions = relationship("TradingDecision", back_populates="run", cascade="all, delete-orphan")
    executions = relationship("ExecutionRecord", back_populates="run", cascade="all, delete-orphan")


class MarketObservation(Base):
    """
    Detailed market state at the time of the workflow run.
    """
    __tablename__ = "MarketObservation"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    runId = Column(String, ForeignKey("WorkflowRun.id", ondelete="CASCADE"), nullable=False, index=True)
    
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    price = Column(Float)
    barData = Column(JSON)  # Current and recent OHLCV
    indicators = Column(JSON)  # EMA, RSI, etc.
    
    # Relationships
    run = relationship("WorkflowRun", back_populates="observations")


class AIAnalysis(Base):
    """
    Structured analysis from AI agents (market analysis, Brooks analysis, etc.)
    """
    __tablename__ = "AIAnalysis"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    runId = Column(String, ForeignKey("WorkflowRun.id", ondelete="CASCADE"), nullable=False, index=True)
    
    nodeName = Column(String, nullable=False, index=True)  # e.g., 'brooks_analyzer'
    modelProvider = Column(String)  # e.g., 'OpenAI', 'ModelScope'
    modelName = Column(String)  # e.g., 'gpt-4o', 'qwen-max'
    
    content = Column(JSON, nullable=False)  # The structured analysis result
    rawResponse = Column(JSON)  # Original LLM output if available
    reasoning = Column(String)  # Thinking process / Chain of thought
    prompt = Column(String)  # User prompt sent to LLM
    
    tokenUsage = Column(JSON)  # Prompt, completion, total tokens
    latencyMs = Column(Float)
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    run = relationship("WorkflowRun", back_populates="analyses")


class TradingDecision(Base):
    """
    Detailed trading decision including rationale and rules.
    """
    __tablename__ = "TradingDecision"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    runId = Column(String, ForeignKey("WorkflowRun.id", ondelete="CASCADE"), nullable=False, index=True)
    
    operation = Column(SQLEnum(OperationType), nullable=False)
    symbol = Column(SQLEnum(SymbolType), nullable=False)
    
    # Decision details
    rationale = Column(String)
    probabilityScore = Column(Float)
    waitReason = Column(String)
    
    # Captured from Pydantic models in strategy node
    entryRules = Column(JSON)
    stopLossRules = Column(JSON)
    takeProfitRules = Column(JSON)
    prediction = Column(JSON)
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    run = relationship("WorkflowRun", back_populates="decisions")
    executions = relationship("ExecutionRecord", back_populates="decision")


class ExecutionRecord(Base):
    """
    Link to actual exchange orders and fill details.
    """
    __tablename__ = "ExecutionRecord"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    runId = Column(String, ForeignKey("WorkflowRun.id", ondelete="CASCADE"), nullable=False, index=True)
    decisionId = Column(String, ForeignKey("TradingDecision.id", ondelete="CASCADE"), index=True)
    
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)  # BUY/SELL
    orderId = Column(String, index=True)
    clientOrderId = Column(String)
    
    status = Column(String)  # OPEN, FILLED, CANCELED, FAILED
    executedPrice = Column(Float)
    executedAmount = Column(Float)
    fee = Column(Float)
    error = Column(String)
    
    additionalData = Column(JSON)  # Any extra execution context
    
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    run = relationship("WorkflowRun", back_populates="executions")
    decision = relationship("TradingDecision", back_populates="executions")


class DashboardEvent(Base):
    """
    Dashboard events for frontend log persistence.
    Stores all events that should be displayed in the AI Execution Log.
    """
    __tablename__ = "dashboard_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    type = Column(String, nullable=False, index=True)  # e.g., 'node_start', 'analysis_complete', etc.
    node = Column(String, nullable=True, index=True)  # Which node emitted this event
    message = Column(String, nullable=True)  # Human-readable message
    data = Column(JSON, nullable=True)  # Event payload
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    
    __table_args__ = (
        Index('idx_dashboard_event_timestamp_type', 'timestamp', 'type'),
    )
