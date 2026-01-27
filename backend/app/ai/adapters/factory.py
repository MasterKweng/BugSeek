"""模型适配器工厂"""
from typing import Dict, Any
from .base import BaseModelAdapter
from .openai import OpenAIAdapter
from .aliyun import AliyunAdapter
import logging

logger = logging.getLogger(__name__)


class ModelAdapterFactory:
    """模型适配器工厂"""
    
    _adapters: Dict[str, BaseModelAdapter] = {}
    
    @classmethod
    def create(cls, provider: str = None, **kwargs) -> BaseModelAdapter:
        """
        创建模型适配器实例
        
        Args:
            provider: 提供商名称 (openai, aliyun)
            **kwargs: 适配器初始化参数
            
        Returns:
            BaseModelAdapter: 适配器实例
        """
        from app.ai.config import AI_CONFIG
        
        if provider is None:
            provider = AI_CONFIG["default_provider"]
        
        provider = provider.lower()
        
        # 单例模式，避免重复创建
        if provider in cls._adapters:
            return cls._adapters[provider]
        
        adapters_map = {
            "openai": OpenAIAdapter,
            "aliyun": AliyunAdapter
        }
        
        adapter_class = adapters_map.get(provider)
        if not adapter_class:
            logger.warning(f"不支持的提供商: {provider}，使用默认 openai")
            adapter_class = OpenAIAdapter
            provider = "openai"
        
        adapter = adapter_class(**kwargs)
        cls._adapters[provider] = adapter
        
        logger.info(f"创建模型适配器: provider={provider}")
        return adapter
    
    @classmethod
    def clear_cache(cls):
        """清除适配器缓存"""
        cls._adapters.clear()