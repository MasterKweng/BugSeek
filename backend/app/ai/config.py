"""AI 服务配置"""
import os

AI_CONFIG = {
    # 默认提供商
    "default_provider": os.getenv("AI_PROVIDER", "openai"),

    # API 密钥
    "api_key": os.getenv("AI_API_KEY"),

    # 模型配置
    "models": {
        "openai": {
            "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        },
        "aliyun": {
            "model": os.getenv("ALIYUN_MODEL", "qwen-turbo"),
            "api_key": os.getenv("DASHSCOPE_API_KEY")
        }
    }
}

# Qwen/Qwen2.5-Coder-7B-Instruct 配置说明
#
# 方法1: 使用本地 vLLM 部署（推荐）
# 1. 安装 vLLM: pip install vllm
# 2. 启动服务: vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --port 8000
# 3. 配置 .env:
#    AI_PROVIDER=openai
#    OPENAI_API_KEY=empty
#    OPENAI_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
#    OPENAI_BASE_URL=http://localhost:8000/v1
#
# 方法2: 使用 Ollama 部署
# 1. 安装 Ollama: https://ollama.com
# 2. 拉取模型: ollama pull qwen2.5-coder:7b
# 3. 启动服务: ollama serve
# 4. 配置 .env:
#    AI_PROVIDER=openai
#    OPENAI_API_KEY=ollama
#    OPENAI_MODEL=qwen2.5-coder:7b
#    OPENAI_BASE_URL=http://localhost:11434/v1
#
# 方法3: 使用云服务（如通义千问、阿里云百炼等）
# 1. 获取 API Key
# 2. 配置 .env:
#    AI_PROVIDER=openai
#    OPENAI_API_KEY=your-api-key
#    OPENAI_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
#    OPENAI_BASE_URL=https://your-provider-endpoint/v1