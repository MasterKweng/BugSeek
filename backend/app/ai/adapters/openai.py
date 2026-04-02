"""OpenAI-compatible model adapter."""

from typing import Any, Dict
import logging
import os

from .base import BaseModelAdapter

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseModelAdapter):
    """Adapter for OpenAI-compatible chat completion APIs."""

    def __init__(self, api_key: str = None, model: str = None, base_url: str = None):
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
        except ImportError as exc:
            raise ImportError("Please install openai: pip install openai") from exc

        self.usage_stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    async def complete(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Call an OpenAI-compatible chat completion endpoint."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=120.0,
            )

            result = self._extract_text_result(response)
            tokens_used = getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
            finish_reason = None
            if getattr(response, "choices", None):
                finish_reason = getattr(response.choices[0], "finish_reason", None)

            self.usage_stats["total_requests"] += 1
            self.usage_stats["total_tokens"] += tokens_used
            self.usage_stats["total_cost"] += self._calculate_cost(tokens_used)

            logger.info(
                "OpenAI call succeeded: model=%s, tokens=%s, finish_reason=%s, content_length=%s",
                self.model,
                tokens_used,
                finish_reason,
                len(result),
            )

            return {
                "result": result,
                "tokens_used": tokens_used,
                "model": self.model,
                "finish_reason": finish_reason,
            }

        except Exception as exc:
            logger.error("OpenAI call failed: %s", str(exc))
            return {
                "result": None,
                "error": str(exc),
            }

    def _extract_text_result(self, response: Any) -> str:
        """Extract plain text from the first chat completion choice."""
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""

        message = getattr(choices[0], "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                else:
                    text = getattr(item, "text", None)
                if text:
                    parts.append(text)
            return "".join(parts)

        return ""

    def _calculate_cost(self, tokens: int) -> float:
        """Estimate cost in USD."""
        pricing = {
            "gpt-4": 0.03 / 1000,
            "gpt-3.5-turbo": 0.002 / 1000,
        }
        return tokens * pricing.get(self.model, 0.01 / 1000)

    async def get_usage_stats(self) -> Dict[str, Any]:
        """Return usage statistics."""
        return self.usage_stats
