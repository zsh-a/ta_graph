"""
Database models for ta_graph
SQLAlchemy ORM models migrated from Super-nof1.ai Prisma schema
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
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
    
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    
    createdAt = Column(DateTime, default=datetime.utcnow, index=True)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    
    snapshotDate = Column(DateTime, default=datetime.utcnow, index=True)
    
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
    
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
