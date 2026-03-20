"""Engine-local stage constants for field mapping workflows."""

from __future__ import annotations

from enum import IntEnum


class Stage(IntEnum):
    NOT_STARTED = 0
    FIELD_EXTRACTION = 1
    RULE_SCORING = 2
    INTELLIGENT_SCREENING = 3
    AI_OPTIMIZATION = 4
    RESULT_MERGE = 5


class StageStatus:
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


STAGE_NAMES = {
    Stage.NOT_STARTED: "未开始",
    Stage.FIELD_EXTRACTION: "字段提取",
    Stage.RULE_SCORING: "规则评分",
    Stage.INTELLIGENT_SCREENING: "智能筛选",
    Stage.AI_OPTIMIZATION: "AI优化",
    Stage.RESULT_MERGE: "结果合并",
}


def get_stage_name(stage_num: int) -> str:
    return STAGE_NAMES.get(stage_num, "未知阶段")


def get_stage_result_key(stage_num: int) -> str:
    return f"stage{stage_num}"
