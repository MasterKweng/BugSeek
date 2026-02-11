"""
字段映射阶段常量定义

遵循后端代码规范：
- 使用枚举代替魔法值
- 全链路 TraceID 贯穿
- 清晰的命名和注释
"""
from enum import IntEnum
from typing import Dict, Tuple


class Stage(IntEnum):
    """
    字段映射任务阶段枚举
    
    阶段编号说明：
    0: 未开始
    1: 字段提取 - 从所有API定义中提取字段并去重
    2: 规则评分 - 使用规则引擎对字段进行数据库匹配评分
    3: 智能筛选 - 根据规则评分结果对字段进行优先级分类
    4: AI优化 - 使用AI服务对筛选出的字段进行智能推荐优化
    5: 结果合并 - 合并规则候选和AI候选，生成最终建议列表
    """
    NOT_STARTED = 0
    FIELD_EXTRACTION = 1
    RULE_SCORING = 2
    INTELLIGENT_SCREENING = 3
    AI_OPTIMIZATION = 4
    RESULT_MERGE = 5


class StageStatus:
    """
    阶段状态常量
    
    使用字符串常量而不是枚举，便于序列化和存储
    """
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageConfig:
    """
    阶段配置信息
    
    包含每个阶段的名称、描述和进度范围
    遵循后端代码规范：使用常量配置，避免魔法值
    """
    
    # 阶段名称配置
    NAMES: Dict[int, str] = {
        Stage.NOT_STARTED: "未开始",
        Stage.FIELD_EXTRACTION: "字段提取",
        Stage.RULE_SCORING: "规则评分",
        Stage.INTELLIGENT_SCREENING: "智能筛选",
        Stage.AI_OPTIMIZATION: "AI优化",
        Stage.RESULT_MERGE: "结果合并"
    }
    
    # 阶段描述配置
    DESCRIPTIONS: Dict[int, str] = {
        Stage.NOT_STARTED: "任务尚未开始",
        Stage.FIELD_EXTRACTION: "从所有API定义中提取字段并去重",
        Stage.RULE_SCORING: "使用规则引擎对字段进行数据库匹配评分",
        Stage.INTELLIGENT_SCREENING: "根据规则评分结果对字段进行优先级分类",
        Stage.AI_OPTIMIZATION: "使用AI服务对筛选出的字段进行智能推荐优化",
        Stage.RESULT_MERGE: "合并规则候选和AI候选，生成最终建议列表"
    }
    
    # 进度范围配置 (起始百分比, 结束百分比)
    PROGRESS_RANGES: Dict[int, Tuple[int, int]] = {
        Stage.NOT_STARTED: (0, 0),
        Stage.FIELD_EXTRACTION: (0, 10),
        Stage.RULE_SCORING: (15, 35),
        Stage.INTELLIGENT_SCREENING: (40, 40),
        Stage.AI_OPTIMIZATION: (45, 95),
        Stage.RESULT_MERGE: (98, 100)
    }
    
    # AI 调用配置
    AI_MAX_RETRIES = 3  # AI调用最大重试次数
    AI_RETRY_DELAY = 2  # AI调用重试延迟（秒）
    AI_TIMEOUT = 60  # AI调用超时时间（秒）
    
    # 批处理配置
    BATCH_SIZE = 100  # 批处理每批处理字段数
    MAX_AI_BATCH_SIZE = 10  # AI批量调用每批处理字段数


class StageResultKey:
    """
    阶段结果存储键名常量
    
    用于从 stage_results JSONB 字段中存储和检索数据
    遵循后端代码规范：避免魔法字符串，使用常量定义
    """
    NAME = "name"
    STATUS = "status"
    PROGRESS = "progress"
    COMPLETED_AT = "completed_at"
    DATA = "data"
    
    # 阶段键名
    STAGE1 = "stage1"
    STAGE2 = "stage2"
    STAGE3 = "stage3"
    STAGE4 = "stage4"
    STAGE5 = "stage5"


def get_stage_name(stage_num: int) -> str:
    """
    获取阶段名称
    
    Args:
        stage_num: 阶段编号
        
    Returns:
        阶段名称
    """
    return StageConfig.NAMES.get(stage_num, "未知阶段")


def get_stage_description(stage_num: int) -> str:
    """
    获取阶段描述
    
    Args:
        stage_num: 阶段编号
        
    Returns:
        阶段描述
    """
    return StageConfig.DESCRIPTIONS.get(stage_num, "无描述")


def get_progress_range(stage_num: int) -> Tuple[int, int]:
    """
    获取阶段进度范围
    
    Args:
        stage_num: 阶段编号
        
    Returns:
        (起始百分比, 结束百分比)
    """
    return StageConfig.PROGRESS_RANGES.get(stage_num, (0, 0))


def get_stage_result_key(stage_num: int) -> str:
    """
    获取阶段结果存储键名
    
    Args:
        stage_num: 阶段编号
        
    Returns:
        阶段结果键名 (如 "stage1", "stage2" 等)
    """
    return f"stage{stage_num}"