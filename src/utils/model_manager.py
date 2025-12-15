"""
Model Manager - 统一的LLM模型管理
支持本地API (vllm/ollama) 和 ModelScope API 的便捷切换
"""

import os
from typing import Optional, Literal
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

ModelProvider = Literal["local", "modelscope", "openai"]

class ModelConfig:
    """模型配置类"""
    
    def __init__(
        self,
        provider: ModelProvider = "local",
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        timeout: int = 120
    ):
        self.provider = provider
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout
        
    @classmethod
    def from_env(cls, provider: Optional[ModelProvider] = None) -> "ModelConfig":
        """从环境变量加载配置"""
        # 优先使用传入的provider，否则从环境变量读取
        provider = provider or os.getenv("MODEL_PROVIDER", "local")
        
        if provider == "local":
            return cls(
                provider="local",
                model_name=os.getenv("LOCAL_MODEL_NAME", "Qwen/Qwen2-VL-7B-Instruct"),
                base_url=os.getenv("LOCAL_API_URL", "http://localhost:8080/v1"),
                api_key=os.getenv("LOCAL_API_KEY", "sk-xxx"),
                temperature=float(os.getenv("MODEL_TEMPERATURE", "0.1"))
            )
        elif provider == "modelscope":
            return cls(
                provider="modelscope",
                model_name=os.getenv("MODELSCOPE_MODEL_NAME", "qwen-vl-max"),
                base_url=os.getenv("MODELSCOPE_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                api_key=os.getenv("MODELSCOPE_API_KEY"),  # 必须设置
                temperature=float(os.getenv("MODEL_TEMPERATURE", "0.1"))
            )
        elif provider == "openai":
            return cls(
                provider="openai",
                model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
                base_url=None,  # OpenAI使用默认URL
                api_key=os.getenv("OPENAI_API_KEY"),
                temperature=float(os.getenv("MODEL_TEMPERATURE", "0.1"))
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "timeout": self.timeout
        }


class ModelManager:
    """模型管理器 - 提供统一的LLM实例"""
    
    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig.from_env()
        self._llm_cache = {}
        
    def get_llm(self, override_config: Optional[ModelConfig] = None) -> ChatOpenAI:
        """
        获取LLM实例
        
        Args:
            override_config: 可选的配置覆盖
            
        Returns:
            ChatOpenAI实例
        """
        config = override_config or self.config
        
        # 缓存key
        cache_key = f"{config.provider}_{config.model_name}"
        
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
        
        # 构建LLM参数
        llm_kwargs = {
            "model": config.model_name,
            "temperature": config.temperature,
            "timeout": config.timeout,
        }
        
        # 根据provider设置base_url和api_key
        if config.base_url:
            llm_kwargs["base_url"] = config.base_url
        if config.api_key:
            llm_kwargs["api_key"] = config.api_key
        else:
            # 如果没有api_key，使用占位符（本地API通常不需要真实key）
            llm_kwargs["api_key"] = "sk-placeholder"
            
        # 创建LLM实例
        llm = ChatOpenAI(**llm_kwargs)
        
        # 缓存
        self._llm_cache[cache_key] = llm
        
        return llm
    
    def switch_provider(self, provider: ModelProvider):
        """切换模型提供商"""
        self.config = ModelConfig.from_env(provider)
        print(f"✓ Switched to {provider} provider: {self.config.model_name}")
    
    def get_config(self) -> ModelConfig:
        """获取当前配置"""
        return self.config
    
    def display_config(self):
        """显示当前配置"""
        print(f"\n=== Model Configuration ===")
        print(f"Provider: {self.config.provider}")
        print(f"Model: {self.config.model_name}")
        print(f"Base URL: {self.config.base_url}")
        print(f"Temperature: {self.config.temperature}")
        print(f"===========================\n")


# 全局单例
_model_manager: Optional[ModelManager] = None

def get_model_manager() -> ModelManager:
    """获取全局模型管理器"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager

def get_llm(provider: Optional[ModelProvider] = None) -> ChatOpenAI:
    """
    快捷函数：获取LLM实例
    
    Args:
        provider: 可选的provider，如果提供则临时切换
        
    Example:
        # 使用默认配置
        llm = get_llm()
        
        # 临时使用modelscope
        llm = get_llm("modelscope")
    """
    manager = get_model_manager()
    
    if provider and provider != manager.config.provider:
        # 临时使用不同provider
        temp_config = ModelConfig.from_env(provider)
        return manager.get_llm(temp_config)
    
    return manager.get_llm()
