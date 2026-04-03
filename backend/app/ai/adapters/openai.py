"""OpenAI-compatible model adapter."""

from typing import Any, Dict, Type
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
                # max_tokens=2000,
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

    async def complete_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_model: Type[Any],
    ) -> Dict[str, Any]:
        """Call a structured-output path and return a validated object payload."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            instructor_client = self._build_instructor_client()
            if instructor_client is not None:
                payload = await instructor_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_model=response_model,
                    temperature=0.2,
                    timeout=120.0,
                )
                result = self._structured_to_dict(payload)
                logger.info("Structured call succeeded via Instructor: model=%s", self.model)
                return {
                    "result": result,
                    "model": self.model,
                    "provider": "instructor",
                }

            if not hasattr(self.client, "beta") or not hasattr(self.client.beta.chat.completions, "parse"):
                return {
                    "result": None,
                    "error": "Structured output is not supported by the current OpenAI client",
                }

            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=response_model,
                temperature=0.2,
                timeout=120.0,
            )
            choices = getattr(response, "choices", None) or []
            if not choices:
                return {
                    "result": None,
                    "error": "Structured output returned no choices",
                }

            message = getattr(choices[0], "message", None)
            parsed = getattr(message, "parsed", None) if message is not None else None
            if parsed is None:
                refusal = getattr(message, "refusal", None) if message is not None else None
                return {
                    "result": None,
                    "error": f"Structured output returned no parsed payload: {refusal or 'unknown reason'}",
                }

            tokens_used = getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
            finish_reason = getattr(choices[0], "finish_reason", None)

            self.usage_stats["total_requests"] += 1
            self.usage_stats["total_tokens"] += tokens_used
            self.usage_stats["total_cost"] += self._calculate_cost(tokens_used)

            logger.info(
                "Structured call succeeded: model=%s, tokens=%s, finish_reason=%s",
                self.model,
                tokens_used,
                finish_reason,
            )
            return {
                "result": self._structured_to_dict(parsed),
                "tokens_used": tokens_used,
                "model": self.model,
                "finish_reason": finish_reason,
                "provider": "openai_parse",
            }
        except Exception as exc:
            logger.warning("Structured call failed and will fall back to text mode: %s", str(exc))
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

    def _build_instructor_client(self) -> Any:
        """Build an Instructor client when the dependency is installed."""
        try:
            import instructor
        except ImportError:
            return None

        return instructor.from_openai(self.client)

    def _structured_to_dict(self, payload: Any) -> Dict[str, Any]:
        """Normalize a structured payload into a plain dict."""
        if hasattr(payload, "model_dump"):
            return payload.model_dump(exclude_none=True)
        if isinstance(payload, dict):
            return payload
        raise TypeError(f"Unsupported structured payload type: {type(payload).__name__}")

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
