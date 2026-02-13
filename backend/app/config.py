from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "BugSeek"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # 数据库配置
    DATABASE_URL: str = "postgresql://bugseek:bugseek@localhost:5432/bugseek"

    # 数据库连接池配置（适配8核16线程+16GB内存）
    # 连接池大小：根据CPU核心数配置，每个核心2-3个连接
    DB_POOL_SIZE: int = 20
    # 溢出连接数：允许临时超出池大小的连接数
    DB_MAX_OVERFLOW: int = 30
    # 连接超时时间（秒）
    DB_POOL_TIMEOUT: int = 60
    # 连接回收时间（秒）：1小时后回收连接，避免长时间占用
    DB_POOL_RECYCLE: int = 3600
    # 连接预检查：每次获取连接前检查有效性
    DB_POOL_PRE_PING: bool = True
    # 连接池过期时间（秒）：空闲连接30秒后过期
    DB_POOL_EXPIRE: int = 30
    # 最大空闲连接数
    DB_MAX_IDLE: int = 10

    # JWT 配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时

    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    # 日志配置
    LOG_DIR: str = "./logs"
    LOG_LEVEL: str = "INFO"

    # AI 配置
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    OPENAI_BASE_URL: str = "https://api.siliconflow.cn/v1"

    # Hugging Face 配置
    HF_ENDPOINT: str = "https://hf-mirror.com"  # 国内镜像加速

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()