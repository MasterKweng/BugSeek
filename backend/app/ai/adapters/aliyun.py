"""阿里通义千问模型适配器"""
from typing import Dict, Any
from .base import BaseModelAdapter
import logging

logger = logging.getLogger(__name__)


class AliyunAdapter(BaseModelAdapter):
    """阿里通义千问模型适配器"""
    
    def __init__(self, api_key: str = None, model: str = None):
        from app.ai.config import AI_CONFIG
        import os
        
        config = AI_CONFIG["models"]["aliyun"]
        self.api_key = api_key or config.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
        self.model = model or config.get("model") or "qwen-turbo"
        
        if not self.api_key:
            raise ValueError("Aliyun API key is required")
        
        try:
            import dashscope
            dashscope.api_key = self.api_key
        except ImportError:
            raise ImportError("Please install dashscope: pip install dashscope")
        
        # 使用统计
        self.usage_stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0
        }
    
    async def complete(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """调用阿里通义模型"""
        try:
            import dashscope
            import asyncio
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # dashscope 是同步的，需要在线程池中运行
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: dashscope.Generation.call(
                    model=self.model,
                    messages=messages,
                    result_format='message'
                )
            )
            
            if response.status_code == 200:
                result = response.output.choices[0]['message']['content']
                tokens_used = response.usage.total_tokens
                
                # 更新统计
                self.usage_stats["total_requests"] += 1
                self.usage_stats["total_tokens"] += tokens_used
                self.usage_stats["total_cost"] += self._calculate_cost(tokens_used)
                
                logger.info(f"Aliyun 调用成功: model={self.model}, tokens={tokens_used}")
                
                return {
                    "result": result,
                    "tokens_used": tokens_used,
                    "model": self.model
                }
            else:
                logger.error(f"Aliyun 调用失败: {response.message}")
                return {
                    "result": None,
                    "error": response.message
                }
                
        except Exception as e:
            logger.error(f"Aliyun 调用失败: {str(e)}")
            return {
                "result": None,
                "error": str(e)
            }
    
    def _calculate_cost(self, tokens: int) -> float:
        """计算成本（人民币）"""
        pricing = {
            "qwen-turbo": 0.0008 / 1000,
            "qwen-plus": 0.004 / 1000
        }
        return tokens * pricing.get(self.model, 0.001 / 1000)
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return self.usage_stats