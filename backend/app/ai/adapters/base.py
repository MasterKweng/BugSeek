"""模型适配器基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseModelAdapter(ABC):
    """模型适配器基类"""
    
    @abstractmethod
    async def complete(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """
        调用模型完成任务
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            
        Returns:
            Dict: 包含 result 和元数据
        """
        pass
    
    @abstractmethod
    async def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        pass