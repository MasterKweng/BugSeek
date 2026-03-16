import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

# 根据环境变量加载对应的配置文件
app_env = os.getenv("APP_ENV", "dev")
env_file = f".env.{app_env}"
load_dotenv(env_file)


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "BugSeek"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    # 环境配置
    ENVIRONMENT: str = "development"  # development, staging, production

    # 使用 model_config 替代 Config 类（Pydantic v2）
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # 忽略额外的字段
    )

    # ========== Feature Flags ==========
    
    # V2.0 场景功能开关
    SCENARIO_V2_ENABLED: bool = False
    SCENARIO_V2_ROLLOUT_PERCENTAGE: int = 0  # 0-100，灰度发布百分比
    SCENARIO_V2_WHITELIST_PROJECTS: str = ""  # 逗号分隔的项目ID列表，如 "1,2,3"
    
    # 意图工作台开关
    INTENT_WORKBENCH_ENABLED: bool = False
    INTENT_WORKBENCH_WHITELIST_PROJECTS: str = ""
    
    # JIT 字段映射开关
    JIT_MAPPING_ENABLED: bool = False
    
    # 报告 RCA 开关
    RCA_IN_REPORT_ENABLED: bool = False
    
    # CI/CD 集成开关
    CI_CD_INTEGRATION_ENABLED: bool = True

    # 数据库配置
    DATABASE_URL: str = "postgresql://bugseek:bugseek@localhost:5432/bugseek"

    # Redis 配置（用于 Celery 异步任务队列）
    REDIS_URL: str = "redis://127.0.0.1:6380/0"

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

    # Data Impact Engine 配置
    DATA_IMPACT_ENABLED: bool = True
    DATA_IMPACT_ASYNC: bool = False
    DATA_IMPACT_DB_ALIAS: str = "primary"
    DATA_IMPACT_MAX_TABLES: int = 20
    DATA_IMPACT_ROW_LIMIT: int = 200
    DATA_IMPACT_CONFIDENCE_THRESHOLD: float = 0.7
    DATA_IMPACT_TRACE_MODE: str = "sqlalchemy"  # sqlalchemy | pg_log | pg_stat_statements
    DATA_IMPACT_PG_LOG_PATH: str = ""
    DATA_IMPACT_PG_LOG_MAX_BYTES: int = 5_000_000
    DATA_IMPACT_PG_LOG_DBNAME: str = ""
    DATA_IMPACT_PG_LOG_USER: str = ""
    DATA_IMPACT_ASSERTIONS_ENABLED: bool = False
    DATA_IMPACT_ASSERTIONS_MODE: str = "rule"  # rule | ai | hybrid
    DATA_IMPACT_SNAPSHOT_MODE: str = "full"  # full | incremental

    def get_scenario_v2_whitelist_projects(self) -> List[int]:
        """获取 V2.0 场景白名单项目ID列表"""
        if not self.SCENARIO_V2_WHITELIST_PROJECTS:
            return []
        return [int(pid.strip()) for pid in self.SCENARIO_V2_WHITELIST_PROJECTS.split(",")]

    def get_intent_workbench_whitelist_projects(self) -> List[int]:
        """获取意图工作台白名单项目ID列表"""
        if not self.INTENT_WORKBENCH_WHITELIST_PROJECTS:
            return []
        return [int(pid.strip()) for pid in self.INTENT_WORKBENCH_WHITELIST_PROJECTS.split(",")]

    def is_project_in_scenario_v2_whitelist(self, project_id: int) -> bool:
        """检查项目是否在 V2.0 场景白名单中"""
        return project_id in self.get_scenario_v2_whitelist_projects()

    def is_project_in_intent_workbench_whitelist(self, project_id: int) -> bool:
        """检查项目是否在意图工作台白名单中"""
        return project_id in self.get_intent_workbench_whitelist_projects()

    def is_user_in_scenario_v2_rollout(self, user_id: int) -> bool:
        """检查用户是否在 V2.0 场景灰度范围内"""
        if self.SCENARIO_V2_ROLLOUT_PERCENTAGE == 0:
            return False
        if self.SCENARIO_V2_ROLLOUT_PERCENTAGE == 100:
            return True
        # 使用用户ID的最后两位数字作为随机种子
        return (user_id % 100) < self.SCENARIO_V2_ROLLOUT_PERCENTAGE


# 创建 settings 实例（环境变量已在 main.py 和 celery_config.py 中通过 load_dotenv 加载）
settings = Settings()
