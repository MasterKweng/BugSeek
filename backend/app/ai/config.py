"""AI service configuration helpers."""

import os
from typing import Dict, Any


def _get_openai_config() -> Dict[str, Any]:
    return {
        "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        "api_key": os.getenv("OPENAI_API_KEY"),
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "supports_structured_output": os.getenv("OPENAI_SUPPORTS_STRUCTURED_OUTPUT", "false").lower() == "true",
    }


def _get_aliyun_config() -> Dict[str, Any]:
    return {
        "model": os.getenv("ALIYUN_MODEL", "qwen-turbo"),
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "supports_structured_output": os.getenv("ALIYUN_SUPPORTS_STRUCTURED_OUTPUT", "false").lower() == "true",
    }


AI_CONFIG = {
    "default_provider": os.getenv("AI_PROVIDER", "openai"),
    "api_key": os.getenv("AI_API_KEY"),
    "models": {
        "openai": _get_openai_config(),
        "aliyun": _get_aliyun_config(),
    },
}
