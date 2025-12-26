"""
配置管理系统

特性：
1. 环境变量验证
2. 类型转换
3. 默认值设置
4. 配置验证
"""

import os
from typing import Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


class ExchangeConfig(BaseModel):
    """交易所配置"""
    name: str = Field(default="bitget")
    api_key: str = Field(...)
    api_secret: str = Field(...)
    passphrase: Optional[str] = None
    sandbox: bool = Field(default=True)
    http_proxy: Optional[str] = None
    
    @validator('api_key', 'api_secret')
    def validate_credentials(cls, v):
        if not v or v == "your_api_key_here" or v == "your_api_secret_here":
            raise ValueError("Invalid API credentials. Please set in .env file")
        return v


class AIModelConfig(BaseModel):
    """AI模型配置"""
    modelscope_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    @validator('*', pre=True)
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class RiskConfig(BaseModel):
    """风险管理配置"""
    max_position_size_percent: float = Field(default=10.0, ge=1.0, le=100.0)
    default_leverage: int = Field(default=10, ge=1, le=125)
    max_daily_loss_percent: float = Field(default=2.0, ge=0.1, le=10.0)
    max_consecutive_losses: int = Field(default=3, ge=1, le=10)
    
    @validator('*', pre=True)
    def convert_float(cls, v):
        if isinstance(v, str):
            return float(v)
        return v


class TimeframeConfig(BaseModel):
    """时间周期配置"""
    primary: str = Field(default="1h")
    secondary: str = Field(default="15m")
    
    @validator('primary', 'secondary')
    def validate_timeframe(cls, v):
        valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        if v not in valid_timeframes:
            raise ValueError(f"Invalid timeframe: {v}. Must be one of {valid_timeframes}")
        return v


class NotificationConfig(BaseModel):
    """通知配置"""
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    smtp_server: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    alert_email: Optional[str] = None
    
    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)
    
    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_password and self.alert_email)


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = Field(default="INFO")
    structured: bool = Field(default=True)
    log_dir: str = Field(default="./logs")
    
    @validator('level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v


class SystemConfig(BaseModel):
    """系统配置"""
    trading_mode: str = Field(default="dry-run")
    checkpoint_dir: str = Field(default="./checkpoints")
    data_dir: str = Field(default="./data")
    
    @validator('trading_mode')
    def validate_trading_mode(cls, v):
        v = v.lower()
        if v not in ['dry-run', 'live']:
            raise ValueError(f"Invalid trading mode: {v}. Must be 'dry-run' or 'live'")
        return v


class Config(BaseModel):
    """完整系统配置"""
    exchange: ExchangeConfig
    ai: AIModelConfig
    risk: RiskConfig
    timeframe: TimeframeConfig
    notification: NotificationConfig
    logging: LoggingConfig
    system: SystemConfig
    
    # Langfuse
    langfuse_secret_key: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_host: str = Field(default="https://cloud.langfuse.com")
    
    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_secret_key and self.langfuse_public_key)
    
    def validate_for_production(self):
        """
        生产环境验证
        
        Raises:
            ValueError: 如果配置不满足生产要求
        """
        errors = []
        
        # 检查交易模式
        if self.system.trading_mode == "live":
            # 生产环境必须关闭沙盒
            # if self.exchange.sandbox:
            #     errors.append("Production mode requires sandbox=False")
            
            # 生产环境建议降低杠杆
            if self.risk.default_leverage > 20:
                errors.append("Warning: High leverage (>20x) in production mode")
            
            # 生产环境建议启用通知
            # if not self.notification.telegram_enabled and not self.notification.email_enabled:
            #     errors.append("Warning: No notification configured for production")
        
        # 检查API密钥
        try:
            self.exchange.validate_credentials(self.exchange.api_key)
        except ValueError as e:
            errors.append(str(e))
        
        if errors:
            raise ValueError("Production validation failed:\n" + "\n".join(f"- {e}" for e in errors))


def load_config(env_file: str = ".env") -> Config:
    """
    加载配置
    
    Args:
        env_file: 环境变量文件路径
        
    Returns:
        Config对象
        
    Raises:
        ValueError: 配置验证失败
    """
    # 加载环境变量
    if Path(env_file).exists():
        load_dotenv(env_file)
    else:
        print(f"Warning: {env_file} not found. Using environment variables.")    
    # 构建配置
    config = Config(
        exchange=ExchangeConfig(
            name=os.getenv("EXCHANGE_NAME", "bitget"),
            api_key=os.getenv("BITGET_API_KEY", ""),
            api_secret=os.getenv("BITGET_API_SECRET", ""),
            passphrase=os.getenv("BITGET_API_PASSPHRASE"),
            sandbox=os.getenv("BITGET_SANDBOX", "true").lower() == "true",
            http_proxy=os.getenv("BITGET_HTTP_PROXY")
        ),
        ai=AIModelConfig(
            modelscope_api_key=os.getenv("MODELSCOPE_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        ),
        risk=RiskConfig(
            max_position_size_percent=float(os.getenv("MAX_POSITION_SIZE_PERCENT", "10.0")),
            default_leverage=int(os.getenv("DEFAULT_LEVERAGE", "10")),
            max_daily_loss_percent=float(os.getenv("MAX_DAILY_LOSS_PERCENT", "2.0")),
            max_consecutive_losses=int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
        ),
        timeframe=TimeframeConfig(
            primary=os.getenv("PRIMARY_TIMEFRAME", "1h"),
            secondary=os.getenv("SECONDARY_TIMEFRAME", "15m")
        ),
        notification=NotificationConfig(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            alert_email=os.getenv("ALERT_EMAIL")
        ),
        logging=LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            structured=os.getenv("STRUCTURED_LOGGING", "true").lower() == "true",
            log_dir=os.getenv("LOG_DIR", "./logs")
        ),
        system=SystemConfig(
            trading_mode=os.getenv("TRADING_MODE", "dry-run"),
            checkpoint_dir=os.getenv("CHECKPOINT_DIR", "./checkpoints"),
            data_dir=os.getenv("DATA_DIR", "./data")
        ),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        langfuse_host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    )
    
    # 生产环境验证
    if config.system.trading_mode == "live":
        print("\n⚠️  Production mode detected. Validating configuration...")
        config.validate_for_production()
        print("✓ Configuration validated for production\n")
    
    return config


# 便捷函数
def get_config() -> Config:
    """获取全局配置"""
    return load_config()


if __name__ == "__main__":
    # 测试配置加载
    try:
        config = load_config()
        print("✓ Configuration loaded successfully")
        print(f"\nExchange: {config.exchange.name}")
        print(f"Trading Mode: {config.system.trading_mode}")
        print(f"Sandbox: {config.exchange.sandbox}")
        print(f"Primary Timeframe: {config.timeframe.primary}")
        print(f"Max Leverage: {config.risk.default_leverage}x")
        print(f"Telegram Enabled: {config.notification.telegram_enabled}")
        print(f"Langfuse Enabled: {config.langfuse_enabled}")
    except Exception as e:
        print(f"✗ Configuration error: {e}")
