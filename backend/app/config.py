from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "BugSeek"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # 数据库配置
    DATABASE_URL: str = "postgresql://bugseek:bugseek@localhost:5432/bugseek"

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

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()