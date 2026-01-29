"""OpenAI 模型适配器"""
from typing import Dict, Any
from .base import BaseModelAdapter
import logging
import os

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseModelAdapter):
    """OpenAI 模型适配器"""

    def __init__(self, api_key: str = None, model: str = None, base_url: str = None):
        # 优先使用传入参数，其次使用环境变量
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")

        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        try:
            import openai
            if self.base_url:
                self.client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            else:
                self.client = openai.AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("Please install openai: pip install openai")

        # 使用统计
        self.usage_stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0
        }

    async def complete(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """调用 OpenAI 模型"""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # 设置超时时间为120秒
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=120.0
            )

            result = response.choices[0].message.content
            tokens_used = response.usage.total_tokens

            # 更新统计
            self.usage_stats["total_requests"] += 1
            self.usage_stats["total_tokens"] += tokens_used
            self.usage_stats["total_cost"] += self._calculate_cost(tokens_used)

            logger.info(f"OpenAI 调用成功: model={self.model}, tokens={tokens_used}")

            return {
                "result": result,
                "tokens_used": tokens_used,
                "model": self.model
            }

        except Exception as e:
            logger.error(f"OpenAI 调用失败: {str(e)}")
            return {
                "result": None,
                "error": str(e)
            }

    def _calculate_cost(self, tokens: int) -> float:
        """计算成本（美元）"""
        pricing = {
            "gpt-4": 0.03 / 1000,
            "gpt-3.5-turbo": 0.002 / 1000
        }
        return tokens * pricing.get(self.model, 0.01 / 1000)

    async def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return self.usage_stats