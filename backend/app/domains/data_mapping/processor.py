"""字段映射处理器（异步任务处理）"""
import asyncio
import concurrent.futures
import json
import logging
import re
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.platform.db.base import ApiDefinition, DbSchemaVersion, ApiFieldMapping, User, AsyncTask, FieldMappingTrace
from app.api.v1.field_mappings import (
    _extract_api_fields,
    _extract_field_descriptions,
    FieldMappingCandidate,
    FieldMappingSuggestion
)
from app.platform.vector.vector_index import get_vector_manager
from app.core.trace import get_trace_id
from app.ai.service import AIService
from app.domains.data_mapping.domain_inferer import DomainInferer
from app.domains.data_mapping.constants import (
    Stage,
    StageStatus,
    StageConfig,
    StageResultKey,
    SCHEMA_VERSION,
    get_stage_name,
    get_stage_result_key
)
from app.domains.data_mapping.exceptions import TaskCancelledException

logger = logging.getLogger(__name__)


def _normalize_confidence_value(value: Any, default: float = 0.5) -> float:
    """将置信度规范化到 [0.0, 1.0] 区间。"""
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = default
    return max(0.0, min(1.0, confidence))


def _normalize_confidence_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    规范化 AI 响应中的 confidence 字段：
    - 顶层缺失 confidence 时补默认 0.5
    - field_mappings[].candidates[] 缺失 confidence 时补默认 0.5
    """
    payload["confidence"] = _normalize_confidence_value(payload.get("confidence", 0.5))

    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        for cand in candidates:
            if isinstance(cand, dict):
                cand["confidence"] = _normalize_confidence_value(cand.get("confidence", 0.5))

    field_mappings = payload.get("field_mappings")
    if isinstance(field_mappings, list):
        for mapping in field_mappings:
            if not isinstance(mapping, dict):
                continue
            mapping_candidates = mapping.get("candidates")
            if isinstance(mapping_candidates, list):
                for cand in mapping_candidates:
                    if isinstance(cand, dict):
                        cand["confidence"] = _normalize_confidence_value(cand.get("confidence", 0.5))

    return payload


def parse_json_safely(text: str) -> Optional[Dict]:
    """
    安全解析 LLM 返回的 JSON
    
    支持多种格式:
    1. 标准 JSON: {"key": "value"}
    2. Markdown 代码块: ```json {...}```
    3. 带废话文本: Here is result: {...}
    4. 不完整 JSON 的尝试性解析
    
    Returns:
        解析后的字典，失败返回 None
    """
    if not text:
        return None
    
    # 1. 尝试直接解析
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return _normalize_confidence_fields(parsed)
        return parsed
    except json.JSONDecodeError:
        pass
    
    # 2. 提取 Markdown 代码块 ```json ... ```
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1).strip())
            if isinstance(parsed, dict):
                return _normalize_confidence_fields(parsed)
            return parsed
        except json.JSONDecodeError:
            pass
    
    # 3. 提取代码块 ``` ... ``` (无 json 标记)
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1).strip())
            if isinstance(parsed, dict):
                return _normalize_confidence_fields(parsed)
            return parsed
        except json.JSONDecodeError:
            pass
    
    # 4. 提取第一个 { ... } 对象
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return _normalize_confidence_fields(parsed)
            return parsed
        except json.JSONDecodeError:
            pass
    
    # 5. 提取第一个 [ ... ] 数组
    match = re.search(r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return _normalize_confidence_fields(parsed)
            return parsed
        except json.JSONDecodeError:
            pass
    
    logger.warning(f"[{get_trace_id()}] 无法解析 AI 返回结果: {text[:200]}...")
    return None


@dataclass
class FieldInfo:
    """字段信息"""
    field_name: str
    field_path: str
    source_type: str
    apis: List[Dict[str, Any]]
    total_count: int
    first_seen: str
    appears_in_multiple_apis: bool = False
    field_name_common: bool = False
    
    # 新增：字段描述相关字段
    field_description: Optional[str] = None  # 字段描述
    has_description: bool = False           # 是否有描述
    
    # 规则评分结果
    rule_candidates: List[FieldMappingCandidate] = None
    rule_top_score: float = 0.0
    
    # 筛选结果
    ai_priority: str = "none"
    screening_reasons: List[str] = None
    
    # AI结果
    ai_candidates: List[FieldMappingCandidate] = None

    # 合并结果
    final_candidates: List[FieldMappingCandidate] = None

    # 域约束（Step4）
    allowed_tables: Optional[List[str]] = None

    # 逻辑缓存键
    logical_cache_key: str = field(init=False, default="")


@dataclass
class AIRequest:
    """AI请求"""
    field_name: str
    field_path: str
    field_description: Optional[str]  # 字段描述
    rule_candidates: List[FieldMappingCandidate]
    api_context: Dict[str, Any]


@dataclass
class ScreeningResult:
    """筛选结果"""
    ai_priority: str
    reasons: List[str]
    action: str


@dataclass
class APIContext:
    """API上下文（用于兄弟节点查询，解决报错.md 问题3）"""
    definition_id: int
    method: str
    path: str
    all_fields: List[str]  # 该API的所有字段（用于兄弟节点查询）


def _extract_recursive(schema: dict, path: str = "") -> List[Tuple[str, dict]]:
    """
    递归提取所有字段路径（V2版本）

    解决报错.md 问题 #3：递归缺失

    Args:
        schema: JSON Schema
        path: 当前路径（前缀）

    Returns:
        [(field_path, field_schema), ...]
    """
    fields = []

    if not isinstance(schema, dict):
        return fields

    # 处理对象类型
    if schema.get('type') == 'object' and 'properties' in schema:
        for prop_name, prop_schema in schema['properties'].items():
            new_path = f"{path}.{prop_name}" if path else prop_name
            fields.extend(_extract_recursive(prop_schema, new_path))

    # 处理数组类型
    elif schema.get('type') == 'array' and 'items' in schema:
        # 数组索引标记为 []
        array_path = f"{path}[]" if path else "[]"
        fields.extend(_extract_recursive(schema['items'], array_path))

    # 处理基础类型（叶子节点）
    else:
        # 空路径时，不添加
        if path:
            fields.append((path, schema))

    return fields


class FieldMappingProcessor:
    """字段映射处理器"""
    
    def __init__(self, db: Session, task: AsyncTask):
        """
        初始化处理器
        
        Args:
            db: 数据库会话
            task: 异步任务
        """
        self.db = db
        self.task = task
        self.trace_id = get_trace_id()
        self.ai_service = AIService()

        # 配置
        self.max_workers = 4
        self.batch_size = 100

        # 重试配置
        self.max_ai_retries = 3
        self.ai_retry_delay = 2  # 秒
        self.ai_timeout = 30  # 秒
        self.semantic_conflict_min_score_gap = 0.08

        # 记录失败的字段
        self.failed_fields = set()
        self.retry_queue = []
        self._rule_scoring_debug: Dict[str, Any] = {}

        # 任务取消标志
        self._cancelled = False

        # V2优化：初始化词权重计算器（阶段3）
        from app.domains.data_mapping.scoring import TokenWeightCalculator
        self.token_weight_calc = TokenWeightCalculator()

        # BSK-SC-017: 支持场景子集（JIT 映射）
        # 从 task_params 中获取 definition_ids，如果提供则只处理这些接口
        params = self.task.task_params
        if not isinstance(params, dict):
            params = {}
        self.definition_ids = params.get('definition_ids')
        if isinstance(self.definition_ids, (list, tuple, set)):
            self.definition_ids = list(self.definition_ids)
        else:
            if self.definition_ids:
                logger.warning(
                    f"[{self.trace_id}] definition_ids 非列表类型，忽略: {type(self.definition_ids).__name__}"
                )
            self.definition_ids = None

        if self.definition_ids:
            logger.info(f"[{self.trace_id}] JIT 映射模式: 仅处理 {len(self.definition_ids)} 个接口")
        else:
            logger.info(f"[{self.trace_id}] 全局映射模式: 处理所有接口")
    
    def _refresh_db_connection(self):
        """
        刷新数据库连接，防止长任务期间连接超时（优化版）
        
        遵循后端代码规范：
        - 异常处理：捕获所有异常并记录
        - 详细日志：包含 TraceID
        - 智能刷新：根据任务进度决定刷新频率
        
        长时间运行的异步任务可能导致连接被数据库服务器关闭，
        定期刷新可以避免连接超时错误
        
        优化策略：
        - 任务前期（progress < 30%）：每 5 分钟刷新一次
        - 任务中期（30% <= progress < 70%）：每 3 分钟刷新一次
        - 任务后期（progress >= 70%）：每 2 分钟刷新一次
        """
        try:
            # 刷新任务对象以获取最新状态
            self.db.refresh(self.task)
            
            # 根据任务进度调整刷新频率（通过日志记录提示）
            progress = self.task.progress or 0
            if progress < 30:
                logger.debug(f"[{self.trace_id}] 数据库连接已刷新 (任务进度: {progress}%)")
            elif progress < 70:
                logger.info(f"[{self.trace_id}] 数据库连接已刷新 (任务进度: {progress}%)")
            else:
                logger.warning(f"[{self.trace_id}] 数据库连接已刷新 (任务进度: {progress}%)")
                
        except Exception as e:
            logger.warning(f"[{self.trace_id}] 刷新数据库连接失败: {str(e)}")
            # 尝试重新连接
            try:
                self.db.rollback()
                self.db.refresh(self.task)
                logger.info(f"[{self.trace_id}] 数据库连接已重新连接")
            except Exception as retry_error:
                logger.error(f"[{self.trace_id}] 重新连接失败: {str(retry_error)}")
                # 如果刷新失败，标记任务为失败状态
                self.task.status = "failed"
                self.task.error_message = f"数据库连接失败: {str(retry_error)}"
                self.db.commit()
                raise TaskCancelledException("数据库连接失败")
    
    def _commit_with_retry(self, max_retries: int = 3):
        """
        带重试的事务提交
        
        Args:
            max_retries: 最大重试次数
        
        Raises:
            Exception: 重试失败后抛出原始异常
        """
        for attempt in range(max_retries):
            try:
                self.db.commit()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"[{self.trace_id}] 提交失败，尝试重试 ({attempt + 1}/{max_retries}): {str(e)}"
                    )
                    self.db.rollback()
                    import time
                    time.sleep(0.5 * (attempt + 1))  # 指数退避
                else:
                    logger.error(f"[{self.trace_id}] 提交失败，已达最大重试次数: {str(e)}")
                    self.db.rollback()
                    raise
    
    def _check_cancelled(self) -> bool:
        """
        检查任务是否被取消
        
        Returns:
            是否被取消
        """
        # 刷新任务状态
        self.db.refresh(self.task)
        if self.task.status == "cancelled":
            self._cancelled = True
            logger.info(f"[{self.trace_id}] 任务已被取消")
        return self._cancelled
    
    def _raise_if_cancelled(self):
        """
        如果任务被取消则抛出异常
        """
        if self._check_cancelled():
            raise TaskCancelledException("任务已被取消")
    
    def _save_stage_result(
        self,
        stage_num: int,
        stage_data: Dict[str, Any],
        status: str = StageStatus.COMPLETED
    ) -> None:
        """
        保存阶段结果到数据库（阶段化保存核心方法）
        
        遵循后端代码规范：
        - 使用预编译SQL（ORM自动处理）
        - 事务范围最小化（仅更新单条记录）
        - 详细的日志记录（包含TraceID）
        - 异常处理和回滚
        - 使用 update 语句避免 JSON 字段被覆盖
        
        Args:
            stage_num: 阶段编号 (1-5)
            stage_data: 阶段结果数据
            status: 阶段状态 (not_started/running/completed/failed/skipped)
        
        Raises:
            Exception: 数据库操作失败时抛出异常
        """
        try:
            from sqlalchemy import update
            
            stage_key = get_stage_result_key(stage_num)
            
            # 获取当前的 stage_results
            current_results = self.task.stage_results or {}
            
            # 构建阶段结果数据结构
            current_results[stage_key] = {
                StageResultKey.NAME: get_stage_name(stage_num),
                StageResultKey.STATUS: status,
                StageResultKey.PROGRESS: 100 if status == StageStatus.COMPLETED else 0,
                StageResultKey.COMPLETED_AT: datetime.now().isoformat() if status == StageStatus.COMPLETED else None,
                StageResultKey.DATA: stage_data
            }
            
            # 使用 update 语句更新 stage_results，避免覆盖整个 JSON 字段
            stmt = (
                update(AsyncTask)
                .where(AsyncTask.id == self.task.id)
                .values(
                    stage_results=current_results,
                    current_stage=stage_num
                )
            )
            self.db.execute(stmt)
            self.db.commit()
            
            # 刷新任务对象以获取最新状态
            self.db.refresh(self.task)
            
            logger.info(
                f"[{self.trace_id}] 阶段{stage_num}结果已保存: "
                f"status={status}, data_keys={list(stage_data.keys()) if stage_data else []}"
            )
            
        except Exception as e:
            # 回滚事务
            self.db.rollback()
            logger.error(
                f"[{self.trace_id}] 保存阶段{stage_num}结果失败: {str(e)}",
                exc_info=True
            )
            raise
    
    def _load_stage_result(self, stage_num: int) -> Any:
        """
        从数据库加载阶段结果（断点续传核心方法）
        
        遵循后端代码规范：
        - 数据类型校验
        - 异常处理和详细日志
        - 空值防御（NPE防护）
        
        Args:
            stage_num: 阶段编号 (1-5)
        
        Returns:
            阶段结果数据
        
        Raises:
            ValueError: 阶段结果不存在或未完成时抛出异常
        """
        try:
            stage_key = get_stage_result_key(stage_num)
            
            # 检查 stage_results 字段是否存在
            if not self.task.stage_results:
                logger.warning(f"[{self.trace_id}] 任务没有 stage_results 字段")
                raise ValueError(f"阶段{stage_num}结果不存在：任务未初始化阶段结果")
            
            # 检查指定阶段的结果是否存在
            stage_result = self.task.stage_results.get(stage_key)
            if not stage_result:
                logger.warning(f"[{self.trace_id}] 阶段{stage_num}结果不存在于 stage_results 中")
                raise ValueError(f"阶段{stage_num}结果不存在：尚未执行该阶段")
            
            # 检查阶段状态
            stage_status = stage_result.get(StageResultKey.STATUS)
            if stage_status != StageStatus.COMPLETED:
                logger.warning(
                    f"[{self.trace_id}] 阶段{stage_num}状态为 {stage_status}，无法加载结果"
                )
                raise ValueError(f"阶段{stage_num}未完成：当前状态为 {stage_status}")
            
            # 提取并返回阶段数据
            stage_data = stage_result.get(StageResultKey.DATA)
            logger.info(
                f"[{self.trace_id}] 从数据库加载阶段{stage_num}结果: "
                f"data_keys={list(stage_data.keys()) if stage_data else []}"
            )
            
            return stage_data
            
        except ValueError:
            # 重新抛出业务异常
            raise
        except Exception as e:
            # 处理其他异常
            logger.error(
                f"[{self.trace_id}] 加载阶段{stage_num}结果失败: {str(e)}",
                exc_info=True
            )
            raise ValueError(f"加载阶段{stage_num}结果失败: {str(e)}")
    
    def _clear_stage_results_from(self, stage_num: int) -> None:
        """
        清除指定阶段及后续阶段的结果（用于重试）
        
        Args:
            stage_num: 起始阶段编号，将清除该阶段及之后的所有阶段结果
        """
        try:
            if not self.task.stage_results:
                return
            
            # 清除当前及后续阶段的结果
            cleared_stages = []
            for i in range(stage_num, Stage.RESULT_MERGE + 1):
                stage_key = get_stage_result_key(i)
                if stage_key in self.task.stage_results:
                    del self.task.stage_results[stage_key]
                    cleared_stages.append(i)
            
            # 更新当前阶段
            self.task.current_stage = max(0, stage_num - 1)
            
            self.db.commit()
            
            logger.info(
                f"[{self.trace_id}] 已清除阶段结果: {cleared_stages}"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"[{self.trace_id}] 清除阶段结果失败: {str(e)}",
                exc_info=True
            )
            raise
    
    async def process(self) -> Dict[str, Any]:
        """
        处理字段映射建议任务（支持断点续传）
        
        遵循后端代码规范：
        - 阶段化保存：每个阶段完成后立即保存结果
        - 断点续传：从 current_stage 继续执行
        - 异常处理：确保失败时保存状态
        - 详细日志：包含 TraceID 贯穿全链路
        
        Returns:
            处理结果
        """
        try:
            params = self.task.task_params
            project_id = params.get('project_id')
            version_id = params.get('version_id')
            
            # 获取当前阶段（断点续传），确保是整数类型
            current_stage = int(self.task.current_stage or Stage.NOT_STARTED)
            
            logger.info(
                f"[{self.trace_id}] 开始处理字段映射任务: "
                f"project_id={project_id}, version_id={version_id}, "
                f"current_stage={current_stage}"
            )
            
            # 检查是否被取消
            self._raise_if_cancelled()
            
            # 初始化阶段列表
            stages = [
                {"name": get_stage_name(Stage.FIELD_EXTRACTION), "status": "pending", "progress": 0},
                {"name": get_stage_name(Stage.RULE_SCORING), "status": "pending", "progress": 0},
                {"name": get_stage_name(Stage.INTELLIGENT_SCREENING), "status": "pending", "progress": 0},
                {"name": get_stage_name(Stage.AI_OPTIMIZATION), "status": "pending", "progress": 0},
                {"name": get_stage_name(Stage.RESULT_MERGE), "status": "pending", "progress": 0}
            ]
            
            # 阶段1: 字段提取和去重
            if current_stage < Stage.FIELD_EXTRACTION:
                self._raise_if_cancelled()
                self._update_stage_progress(stages, 0, "running", 10)
                self._update_progress(10, "正在提取字段...")
                field_registry = await self._extract_and_deduplicate_fields(
                    project_id, version_id,
                    include_paths=params.get('include_paths', True),
                    include_query=params.get('include_query', True),
                    include_body=params.get('include_body', True)
                )
                self._update_stage_progress(stages, 0, "completed", 100)
                
                # 保存阶段1结果
                self._save_stage_result(
                    Stage.FIELD_EXTRACTION,
                    {
                        "total_fields": len(field_registry),
                        "unique_fields": len(field_registry),
                        "field_count_by_type": self._count_by_type(field_registry)
                    }
                )
            else:
                # 从数据库加载阶段1结果（断点续传）
                logger.info(f"[{self.trace_id}] 从数据库加载阶段1结果（断点续传）")
                field_registry = self._load_stage_result(Stage.FIELD_EXTRACTION)
            
            # 更新初步统计信息
            self._update_statistics({"total_fields": len(field_registry)})
            
            # 阶段2: 规则评分
            if current_stage < Stage.RULE_SCORING:
                self._raise_if_cancelled()
                self._update_stage_progress(stages, 1, "running", 0)
                self._update_progress(15, "正在进行规则评分...")
                db_schema = self._get_db_schema(project_id, version_id)
                field_description_map = {
                    info.field_path: info.field_description or ''
                    for info in field_registry.values()
                    if info.field_description is not None
                }
                rule_results = await self._batch_rule_scoring(
                    field_registry, db_schema, stages, field_description_map
                )
                self._update_stage_progress(stages, 1, "completed", 100)
                
                # 保存阶段2结果
                self._save_stage_result(
                    Stage.RULE_SCORING,
                    {
                        "processed_fields": len(rule_results),
                        "success_fields": len([r for r in rule_results.values() if r]),
                        "failed_fields": len([r for r in rule_results.values() if not r]),
                        "avg_score": self._calculate_avg_score(rule_results),
                        "non_empty_cache_keys": self._rule_scoring_debug.get("non_empty_cache_keys", 0),
                        "total_cache_keys": self._rule_scoring_debug.get("total_cache_keys", 0),
                        "non_empty_ratio": self._rule_scoring_debug.get("non_empty_ratio", 0.0),
                        "sample_empty_cache_keys": self._rule_scoring_debug.get("sample_empty_cache_keys", [])
                    }
                )
            else:
                # 从数据库加载阶段2结果（断点续传）
                logger.info(f"[{self.trace_id}] 从数据库加载阶段2结果（断点续传）")
                rule_results = self._load_stage_result(Stage.RULE_SCORING)
            
            # 阶段3: 智能筛选
            if current_stage < Stage.INTELLIGENT_SCREENING:
                self._raise_if_cancelled()
                self._update_stage_progress(stages, 2, "running", 50)
                self._update_progress(40, "正在进行智能筛选...")
                categories = self._intelligent_screening(field_registry, rule_results)
                self._update_stage_progress(stages, 2, "completed", 100)
                
                # 保存阶段3结果
                self._save_stage_result(
                    Stage.INTELLIGENT_SCREENING,
                    {
                        "auto_confirm": len(categories.get('auto_confirm', [])),
                        "ai_high": len(categories.get('ai_high', [])),
                        "ai_medium": len(categories.get('ai_medium', [])),
                        "ai_low": len(categories.get('ai_low', []))
                    }
                )
            else:
                # 从数据库加载阶段3结果（断点续传）
                logger.info(f"[{self.trace_id}] 从数据库加载阶段3结果（断点续传）")
                categories = self._load_stage_result(Stage.INTELLIGENT_SCREENING)
            
            # 更新分类统计
            self._update_statistics({
                "auto_confirmed": len(categories.get('auto_confirm', [])),
                "ai_high": len(categories.get('ai_high', [])),
                "ai_medium": len(categories.get('ai_medium', [])),
                "ai_low": len(categories.get('ai_low', []))
            })
            
            # 阶段4: AI调用
            if current_stage < Stage.AI_OPTIMIZATION:
                self._raise_if_cancelled()
                if params.get('use_ai', True):
                    self._update_stage_progress(stages, 3, "running", 0)
                    self._update_progress(45, "正在进行AI优化...")
                    ai_results = await self._priority_ai_calling(
                        field_registry, categories, stages, db_schema
                    )
                    self._update_stage_progress(stages, 3, "completed", 100)
                    
                    # 保存阶段4结果
                    self._save_stage_result(
                        Stage.AI_OPTIMIZATION,
                        {
                            "ai_optimized_fields": len(ai_results),
                            "ai_failed_fields": len(self.failed_fields)
                        }
                    )
                else:
                    ai_results = {}
                    self._update_stage_progress(stages, 3, "completed", 100)
                    
                    # 保存阶段4结果（跳过）
                    self._save_stage_result(
                        Stage.AI_OPTIMIZATION,
                        {
                            "ai_optimized_fields": 0,
                            "ai_failed_fields": 0,
                            "skipped": True
                        },
                        status=StageStatus.SKIPPED
                    )
            else:
                # 从数据库加载阶段4结果（断点续传）
                logger.info(f"[{self.trace_id}] 从数据库加载阶段4结果（断点续传）")
                ai_results = self._load_stage_result(Stage.AI_OPTIMIZATION)
            
            # 阶段5: 结果合并
            if current_stage < Stage.RESULT_MERGE:
                self._raise_if_cancelled()
                self._update_stage_progress(stages, 4, "running", 50)
                self._update_progress(98, "正在合并结果...")
                suggestions = self._merge_results(field_registry, ai_results, db_schema)
                self._update_stage_progress(stages, 4, "completed", 100)
                
                # 保存阶段5结果
                self._save_stage_result(
                    Stage.RESULT_MERGE,
                    {
                        "total_suggestions": len(suggestions),
                        "unique_fields_covered": len(field_registry)
                    }
                )
            else:
                # 从数据库加载阶段5结果（断点续传）
                logger.info(f"[{self.trace_id}] 从数据库加载阶段5结果（断点续传）")
                suggestions = self._load_stage_result(Stage.RESULT_MERGE)
            
            # 完成任务
            self._update_progress(100, "处理完成")
            
            # 最终统计信息
            statistics = self._calculate_statistics(field_registry, categories)
            self._update_statistics(statistics)
            
            result = {
                "status": "success",
                "success": True,
                "total": len(suggestions),
                "statistics": statistics,
                "suggestions": [s.model_dump() for s in suggestions]
            }
            
            logger.info(f"[{self.trace_id}] 字段映射任务处理完成: "
                       f"total={result['total']}")
            
            return result
            
        except TaskCancelledException as e:
            logger.info(f"[{self.trace_id}] 任务被取消: {str(e)}")
            self._update_progress(self.task.progress, "任务已取消")
            raise
        except Exception as e:
            logger.error(f"[{self.trace_id}] 字段映射任务处理失败: {str(e)}")
            raise
    
    def _update_stage_progress(
        self,
        stages: List[Dict[str, Any]],
        stage_index: int,
        status: str,
        progress: int
    ):
        """
        更新单个阶段的进度
        
        Args:
            stages: 阶段列表
            stage_index: 阶段索引
            status: 阶段状态
            progress: 阶段进度
        """
        if stage_index < len(stages):
            stages[stage_index]["status"] = status
            stages[stage_index]["progress"] = progress
            self.task.stages = stages
            self.db.commit()
    
    def _update_statistics(self, statistics: Dict[str, Any]):
        """
        更新任务统计信息

        Args:
            statistics: 统计信息
        """
        try:
            from sqlalchemy import update

            # 获取当前统计信息
            current_stats = self.task.statistics or {}

            # 合并统计信息
            current_stats.update(statistics)

            # 使用 update 语句更新，避免 JSON 字段被覆盖
            stmt = (
                update(AsyncTask)
                .where(AsyncTask.id == self.task.id)
                .values(statistics=current_stats)
            )
            self.db.execute(stmt)
            self.db.commit()
            self.db.refresh(self.task)
        except Exception as e:
            logger.error(f"[{self.trace_id}] 更新统计信息失败: {str(e)}", exc_info=True)
            raise
    
    def _update_progress(self, progress: int, message: str):
        """更新任务进度（实时）"""
        self.task.progress = max(0, min(100, progress))
        self.task.progress_message = message
        self.task.updated_at = datetime.now()
        self.db.commit()
        logger.debug(f"[{self.trace_id}] 进度更新: {progress}% - {message}")
    
    def _update_realtime_progress(
        self,
        progress: int,
        message: str,
        current_count: int = None,
        total_count: int = None
    ):
        """
        更新实时进度（包含当前处理数量）
        
        Args:
            progress: 进度百分比
            message: 进度消息
            current_count: 当前已处理数量
            total_count: 总数量
        """
        self.task.progress = max(0, min(100, progress))
        self.task.progress_message = message
        
        # 更新统计信息中的处理数量
        if current_count is not None and total_count is not None:
            if not self.task.statistics:
                self.task.statistics = {}
            self.task.statistics["processed"] = current_count
            self.task.statistics["total"] = total_count
            self.task.statistics["remaining"] = total_count - current_count
            self.task.statistics["completion_rate"] = round(current_count / total_count * 100, 1) if total_count > 0 else 0
        
        self.task.updated_at = datetime.now()
        self.db.commit()
        logger.debug(f"[{self.trace_id}] 实时进度: {progress}% - {message} ({current_count}/{total_count})")
    
    async def _extract_and_deduplicate_fields(
        self,
        project_id: int,
        version_id: int,
        include_paths: bool,
        include_query: bool,
        include_body: bool
    ) -> Dict[str, FieldInfo]:
        """
        提取字段并进行全局去重

        BSK-SC-017: 支持场景子集（JIT 映射）
        - 如果 self.definition_ids 存在，只处理指定的接口定义
        - 否则处理所有接口定义（全局映射模式）

        Returns:
            字段注册表: {field_name: FieldInfo}
        """
        logger.info(f"[{self.trace_id}] 开始提取字段: "
                   f"project_id={project_id}, version_id={version_id}")
        
        field_registry: Dict[str, FieldInfo] = {}
        logical_occurrences: Dict[str, int] = {}
        common_names = {'data', 'info', 'result', 'content', 'item'}
        
        # BSK-SC-017: 支持 JIT 映射，根据 definition_ids 过滤
        if self.definition_ids:
            # JIT 映射模式：只处理指定的接口定义
            logger.info(f"[{self.trace_id}] JIT 映射模式: 查询 {len(self.definition_ids)} 个指定接口")
            definitions = self.db.query(ApiDefinition).filter(
                ApiDefinition.project_id == project_id,
                ApiDefinition.id.in_(self.definition_ids)
            ).all()
        else:
            # 全局映射模式：处理所有接口定义
            logger.info(f"[{self.trace_id}] 全局映射模式: 查询所有接口")
            definitions = self.db.query(ApiDefinition).filter(
                ApiDefinition.project_id == project_id
            ).all()
        
        db_schema = self._get_db_schema(project_id, version_id)
        domain_inferer = DomainInferer(db_schema)
        
        logger.info(f"[{self.trace_id}] 找到 {len(definitions)} 个API定义")
        
        # 遍历所有API定义，提取字段实例（按 definition + field_path 建索引）
        for definition in definitions:
            api_fields = _extract_api_fields(
                definition, include_paths, include_query, include_body
            )
            allowed_tables = domain_inferer.infer(
                api_path=definition.path,
                fields=[field.split('.')[-1] for field in api_fields]
            )
            if not allowed_tables:
                # 兼容两种格式：列表格式 [{"name": "table1", ...}, ...] 和字典格式 {"table1": {...}, ...}
                tables_data = db_schema.get("tables")
                if isinstance(tables_data, list):
                    allowed_tables = [table.get("name", "") for table in tables_data if isinstance(table, dict) and table.get("name")]
                elif isinstance(tables_data, dict):
                    allowed_tables = list(tables_data.keys())
                else:
                    allowed_tables = []
                logger.warning(
                    f"[{self.trace_id}] 域推断为空，降级全库搜索: {definition.method} {definition.path}"
                )
            
            # 提取字段描述
            field_descriptions = _extract_field_descriptions(definition)
            
            for field_path in api_fields:
                source_type, field_name = self._parse_field_path(field_path)
                logical_key = self._build_logical_cache_key(source_type, field_name)
                instance_key = f"{definition.id}:{field_path}"
                logical_occurrences[logical_key] = logical_occurrences.get(logical_key, 0) + 1
                
                # 获取字段描述
                field_description = field_descriptions.get(field_path, '')

                field_info = FieldInfo(
                    field_name=field_name,
                    field_path=field_path,
                    field_description=field_description if field_description else None,
                    has_description=bool(field_description and field_description.strip()),
                    source_type=source_type,
                    apis=[{
                        'definition_id': definition.id,
                        'method': definition.method,
                        'path': definition.path,
                        'field_path': field_path
                    }],
                    total_count=logical_occurrences[logical_key],
                    first_seen=f"{definition.method} {definition.path}",
                    appears_in_multiple_apis=False,
                    field_name_common=field_name in common_names,
                    allowed_tables=allowed_tables
                )
                field_info.logical_cache_key = logical_key
                field_registry[instance_key] = field_info

        # 基于逻辑键回填统计
        for field_info in field_registry.values():
            usage_count = logical_occurrences.get(field_info.logical_cache_key, 0)
            field_info.total_count = usage_count
            field_info.appears_in_multiple_apis = usage_count >= 3

        total_fields = len(field_registry)
        unique_fields = len(logical_occurrences)
        
        logger.info(f"[{self.trace_id}] 字段提取完成: 原始{total_fields}个, "
                   f"去重后{unique_fields}个唯一字段")
        
        return field_registry

    async def _extract_and_deduplicate_fields_v2(
        self,
        project_id: int,
        version_id: int,
        include_paths: bool = True,
        include_query: bool = True,
        include_body: bool = True
    ) -> Dict[str, FieldInfo]:
        """
        V2版本的字段提取和去重（基于图谱和并发控制）

        解决报错.md 问题：
        - #1 批次重心：按API分组处理
        - #13 并发打爆：使用Semaphore控制并发

        Args:
            project_id: 项目ID
            version_id: 版本ID
            include_paths: 是否包含路径参数
            include_query: 是否包含Query参数
            include_body: 是否包含Body字段

        Returns:
            字段注册表: {field_path: FieldInfo}
        """
        logger.info(f"[{self.trace_id}] 开始V2版本字段提取: "
                   f"project_id={project_id}, version_id={version_id}")

        field_registry: Dict[str, FieldInfo] = {}
        logical_occurrences: Dict[str, int] = {}
        common_names = {'data', 'info', 'result', 'content', 'item'}

        # 1. 获取所有API定义
        definitions = self.db.query(ApiDefinition).filter(
            ApiDefinition.project_id == project_id
        ).all()

        logger.info(f"[{self.trace_id}] 找到 {len(definitions)} 个API定义")

        # 2. 构建外键图（阶段2核心功能）
        from app.domains.data_mapping.graph_builder import ForeignKeyGraph
        graph = ForeignKeyGraph(self.db)
        db_schema = self._get_db_schema(project_id, version_id)
        domain_inferer = DomainInferer(db_schema)
        graph.build(db_schema)

        # 3. 并发控制（解决 #13）
        semaphore = asyncio.Semaphore(4)  # 限制为CPU核心数的一半

        # 4. 按API分组处理（解决 #1 批次重心）
        tasks = []
        for definition in definitions:
            task = self._process_api_with_semaphore(definition, semaphore, graph, db_schema)
            tasks.append(task)

        # 5. 并发执行
        logger.info(f"[{self.trace_id}] 开始并发处理 {len(tasks)} 个API...")
        results = await asyncio.gather(*tasks)

        # 6. 合并结果
        for definition, candidates_map in zip(definitions, results):
            api_fields_for_domain = _extract_api_fields(
                definition, include_paths, include_query, include_body
            )
            allowed_tables = domain_inferer.infer(
                api_path=definition.path,
                fields=[field.split('.')[-1] for field in api_fields_for_domain]
            )
            if not allowed_tables:
                # 兼容两种格式：列表格式 [{"name": "table1", ...}, ...] 和字典格式 {"table1": {...}, ...}
                tables_data = db_schema.get("tables")
                if isinstance(tables_data, list):
                    allowed_tables = [table.get("name", "") for table in tables_data if isinstance(table, dict) and table.get("name")]
                elif isinstance(tables_data, dict):
                    allowed_tables = list(tables_data.keys())
                else:
                    allowed_tables = []

            # 提取字段描述
            from app.api.v1.field_mappings import _extract_field_descriptions
            field_descriptions = _extract_field_descriptions(definition)

            for field_path in candidates_map.keys():
                source_type, field_name = self._parse_field_path(field_path)
                logical_key = self._build_logical_cache_key(source_type, field_name)
                instance_key = f"{definition.id}:{field_path}"
                logical_occurrences[logical_key] = logical_occurrences.get(logical_key, 0) + 1

                # 获取字段描述
                field_description = field_descriptions.get(field_path, '')

                field_info = FieldInfo(
                    field_name=field_name,
                    field_path=field_path,
                    field_description=field_description if field_description else None,
                    has_description=bool(field_description and field_description.strip()),
                    source_type=source_type,
                    apis=[{
                        'definition_id': definition.id,
                        'method': definition.method,
                        'path': definition.path,
                        'field_path': field_path
                    }],
                    total_count=logical_occurrences[logical_key],
                    first_seen=f"{definition.method} {definition.path}",
                    appears_in_multiple_apis=False,
                    field_name_common=field_name in common_names,
                    allowed_tables=allowed_tables,
                    rule_candidates=candidates_map.get(field_path, [])
                )
                field_info.logical_cache_key = logical_key
                field_registry[instance_key] = field_info

        # 7. 基于逻辑键回填统计
        for field_info in field_registry.values():
            usage_count = logical_occurrences.get(field_info.logical_cache_key, 0)
            field_info.total_count = usage_count
            field_info.appears_in_multiple_apis = usage_count >= 3

        total_fields = len(field_registry)
        unique_fields = len(logical_occurrences)

        logger.info(f"[{self.trace_id}] V2版本字段提取完成: 原始{total_fields}个, "
                   f"去重后{unique_fields}个唯一字段")

        return field_registry

    def _parse_field_path(self, field_path: str) -> Tuple[str, str]:
        """
        解析字段路径
        
        Returns:
            (source_type, field_name)
        """
        parts = field_path.split('.', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return 'body', field_path

    def _build_logical_cache_key(self, source_type: str, field_name: str) -> str:
        return f"{source_type}:{field_name}".lower()

    def _build_logical_cache_key_v2(
        self,
        api_group: str,
        method: str,
        api_path: str,
        field_path: str
    ) -> str:
        """
        构建V2版本逻辑键：包含API完整上下文

        解决报错.md 问题 #2：扁平键问题

        格式：{api_group}::{method}::{path}::{json_path}
        示例：part_api::POST::/part/::body.category.name
        """
        # 规范化路径（去除路径参数）
        normalized_path = re.sub(r'\{[^}]+\}', ':', api_path)

        # 组装键
        return f"{api_group}::{method}::{normalized_path}::{field_path}".lower()

    def _clone_candidates(
        self,
        candidates: List[FieldMappingCandidate]
    ) -> List[FieldMappingCandidate]:
        return [
            FieldMappingCandidate(
                db_table=c.db_table,
                db_column=c.db_column,
                score=c.score,
                reasons=list(c.reasons or [])
            )
            for c in candidates
        ]
    
    def _count_by_type(self, field_registry: Dict[str, Any]) -> Dict[str, int]:
        """
        按类型统计字段数量
        
        Args:
            field_registry: 字段注册表
        
        Returns:
            按类型统计的字典 {"path": x, "query": y, "body": z}
        """
        type_count = {"path": 0, "query": 0, "body": 0}
        
        for field_info in field_registry.values():
            if field_info.source_type in type_count:
                type_count[field_info.source_type] += 1
        
        return type_count
    
    def _calculate_avg_score(self, rule_results: Dict[str, List[Any]]) -> float:
        """
        计算平均评分
        
        Args:
            rule_results: 规则评分结果
        
        Returns:
            平均评分
        """
        total_score = 0.0
        total_count = 0
        
        for candidates in rule_results.values():
            if candidates:
                total_score += sum(c.score for c in candidates)
                total_count += len(candidates)
        
        if total_count > 0:
            return round(total_score / total_count, 4)
        
        return 0.0

    def _extract_query_params_unified(self, definition: ApiDefinition) -> List[str]:
        """
        统一的Query参数提取方法（V2版本）

        解决报错.md 问题 #3：统一Query参数处理

        Args:
            definition: API定义

        Returns:
            Query参数列表
        """
        query_params = []

        # 检查 schema_snapshot 结构
        schema_snapshot = definition.schema_snapshot
        if schema_snapshot:
            if isinstance(schema_snapshot, str):
                try:
                    schema_snapshot = json.loads(schema_snapshot)
                except:
                    schema_snapshot = {}

            if isinstance(schema_snapshot, dict):
                # 情况1: 直接在 schema_snapshot 顶层有 parameters
                if 'parameters' in schema_snapshot:
                    for param in schema_snapshot.get('parameters', []):
                        if param.get('in') == 'query':
                            query_params.append(param.get('name'))

                # 情况2: 在 schema_snapshot.request_schema 中
                request_schema = schema_snapshot.get('request_schema')
                if not request_schema and hasattr(definition, 'request_schema') and definition.request_schema:
                    request_schema = definition.request_schema
                    if isinstance(request_schema, str):
                        try:
                            request_schema = json.loads(request_schema)
                        except:
                            request_schema = {}

                if request_schema and isinstance(request_schema, dict):
                    # YApi结构：{"type": "json", "schema": {...}}
                    if 'type' in request_schema and 'schema' in request_schema:
                        actual_schema = request_schema.get('schema', {})
                        if isinstance(actual_schema, dict) and 'parameters' in actual_schema:
                            for param in actual_schema['parameters']:
                                if param.get('in') == 'query':
                                    query_params.append(param.get('name'))

        return query_params

    def _extract_body_recursive(self, definition: ApiDefinition) -> List[str]:
        """
        递归提取Body字段（V2版本）

        使用递归提取器处理嵌套对象和数组

        Args:
            definition: API定义

        Returns:
            Body字段路径列表
        """
        body_fields = []

        # 检查 schema_snapshot 结构
        schema_snapshot = definition.schema_snapshot
        if schema_snapshot:
            if isinstance(schema_snapshot, str):
                try:
                    schema_snapshot = json.loads(schema_snapshot)
                except:
                    schema_snapshot = {}

            if isinstance(schema_snapshot, dict):
                # 获取 request_schema
                request_schema = schema_snapshot.get('request_schema')
                if not request_schema and hasattr(definition, 'request_schema') and definition.request_schema:
                    request_schema = definition.request_schema
                    if isinstance(request_schema, str):
                        try:
                            request_schema = json.loads(request_schema)
                        except:
                            request_schema = {}

                if request_schema and isinstance(request_schema, dict):
                    # YApi结构：{"type": "json", "schema": {...}}
                    if 'type' in request_schema and 'schema' in request_schema:
                        actual_schema = request_schema.get('schema', {})
                        if isinstance(actual_schema, dict):
                            # 使用递归提取器
                            extracted = _extract_recursive(actual_schema, "body")
                            body_fields.extend([field_path for field_path, _ in extracted])
                    # 直接有properties
                    elif 'properties' in request_schema:
                        extracted = _extract_recursive(request_schema, "body")
                        body_fields.extend([field_path for field_path, _ in extracted])

        return body_fields

    def _extract_all_fields_v2(
        self,
        definition: ApiDefinition,
        include_paths: bool = True,
        include_query: bool = True,
        include_body: bool = True
    ) -> Tuple[List[str], APIContext]:
        """
        统一的字段提取方法（V2版本，修正版）

        解决报错.md 问题 #3：兄弟节点查询优化

        Returns:
            (字段列表, API上下文)
        """
        all_fields = []

        # 1. 路径参数
        if include_paths:
            path_params = self._extract_query_params_unified(definition)
            # 从路径中提取参数
            import re
            path_params = re.findall(r'\{([^}]+)\}', definition.path)
            all_fields.extend([f"path.{p}" for p in path_params])

        # 2. Query参数（统一处理）
        if include_query:
            query_params = self._extract_query_params_unified(definition)
            all_fields.extend([f"query.{p}" for p in query_params])

        # 3. Body字段（递归提取）
        if include_body:
            body_fields = self._extract_body_recursive(definition)
            all_fields.extend(body_fields)

        # 4. 创建API上下文（新增，解决报错.md 问题3）
        context = APIContext(
            definition_id=definition.id,
            method=definition.method,
            path=definition.path,
            all_fields=all_fields
        )

        return all_fields, context

    def _get_db_schema(self, project_id: int, version_id: int) -> Dict[str, Any]:
        """
        获取数据库结构

        Returns:
            数据库结构快照
        """
        schema_version = self.db.query(DbSchemaVersion).filter(
            DbSchemaVersion.project_id == project_id,
            DbSchemaVersion.version_id == version_id
        ).first()

        if schema_version:
            if schema_version.schema_snapshot:
                snapshot = schema_version.schema_snapshot or {}
                tables_data = snapshot.get("tables", {})
                if isinstance(tables_data, list):
                    table_count = len([t for t in tables_data if isinstance(t, dict)])
                    column_count = 0
                    for table in tables_data:
                        if not isinstance(table, dict):
                            continue
                        columns = table.get("columns", [])
                        if isinstance(columns, list):
                            column_count += len(columns)
                        elif isinstance(columns, dict):
                            column_count += len(columns.keys())
                elif isinstance(tables_data, dict):
                    table_count = len(tables_data.keys())
                    column_count = 0
                    for table_info in tables_data.values():
                        if not isinstance(table_info, dict):
                            continue
                        columns = table_info.get("columns", [])
                        if isinstance(columns, list):
                            column_count += len(columns)
                        elif isinstance(columns, dict):
                            column_count += len(columns.keys())
                else:
                    table_count = 0
                    column_count = 0
                logger.info(
                    f"[{self.trace_id}] 获取数据库结构成功: 表={table_count}, 列={column_count}"
                )
                return schema_version.schema_snapshot
            else:
                logger.warning(f"[{self.trace_id}] 数据库结构版本存在但 schema_snapshot 为空: schema_version_id={schema_version.id}")
        else:
            logger.warning(f"[{self.trace_id}] 未找到数据库结构版本: project_id={project_id}, version_id={version_id}")

        return {}

    def _detect_anchor_table(
        self,
        all_candidates: List[List[Dict]],
        graph: Any  # ForeignKeyGraph类型，避免循环导入
    ) -> Optional[str]:
        """
        检测锚点表（Anchor Table，修正版，解决报错.md 问题2）

        解决报错.md 问题 #2：_detect_anchor_table的"零结果"风险

        算法：
        1. 统计所有候选表的出现频次
        2. 计算候选表的度中心性
        3. 选择 频次*中心性 最高的表作为锚点
        4. 增加置信度阈值，避免零结果风险
        5. 检查分散度，避免候选表过于均匀

        Args:
            all_candidates: 所有候选结果列表
            graph: 外键图实例

        Returns:
            锚点表名，如果置信度不足则返回None
        """
        table_freq = {}
        table_scores = {}

        # 1. 统计频次
        for candidates in all_candidates:
            for cand in candidates[:5]:  # 只看Top5
                table = cand.get('db_table', '')
                if table:
                    table_freq[table] = table_freq.get(table, 0) + 1

        if not table_freq:
            logger.warning("没有候选表，跳过锚点检测")
            return None

        # 2. 计算度中心性
        centrality = graph.get_degree_centrality()

        # 3. 综合评分
        for table, freq in table_freq.items():
            degree = centrality.get(table, 0)
            table_scores[table] = freq * (1 + degree * 10)  # 度中心性权重更高

        # 4. 选择最高分
        max_score = max(table_scores.values())
        anchor_table = max(table_scores, key=table_scores.get)

        # 5. 置信度检查（新增，解决报错.md 问题2）
        confidence_threshold = 2.0  # 阈值可调整
        if max_score < confidence_threshold:
            logger.warning(f"锚点表置信度不足 ({max_score:.2f} < {confidence_threshold})，回退到纯向量匹配")
            return None

        # 6. 检查分散度（新增，解决报错.md 问题2）
        scores_list = list(table_scores.values())
        if len(scores_list) > 1:
            avg_score = sum(scores_list) / len(scores_list)
            if max_score / avg_score < 1.5:  # 最高分与平均分的比例
                logger.warning(f"候选表过于分散 (max/avg={max_score/avg_score:.2f})，回退到纯向量匹配")
                return None

        logger.info(f"检测到锚点表: {anchor_table} (置信度={max_score:.2f})")
        return anchor_table

    def _build_graph_context(
        self,
        candidates_map: Dict[str, List],
        graph
    ) -> Dict[str, Any]:
        """
        构建图谱上下文（V2版本）

        Args:
            candidates_map: 候选映射 {field_path: [candidates]}
            graph: 外键图实例

        Returns:
            图谱上下文字典
        """
        # 检测锚点表
        all_candidates_list = list(candidates_map.values())
        anchor_table = self._detect_anchor_table(all_candidates_list, graph)

        # 获取有效表集合
        if anchor_table:
            valid_tables = graph.get_valid_tables(anchor_table)
        else:
            valid_tables = set(graph.nodes())

        return {
            'anchor_table': anchor_table,
            'valid_tables': valid_tables,
            'graph': graph
        }

    def _get_column_comment(
        self,
        db_schema: Dict[str, Any],
        table_name: str,
        column_name: str
    ) -> str:
        """
        获取列注释

        Args:
            db_schema: 数据库结构
            table_name: 表名
            column_name: 列名

        Returns:
            列注释
        """
        try:
            tables = db_schema.get('tables', {})

            # 兼容两种格式：列表格式 [{"name": "table1", "columns": [...]}, ...] 和字典格式 {"table1": {"columns": [...]}, ...}
            table_info = None
            if isinstance(tables, list):
                # 列表格式：查找匹配的表
                for table in tables:
                    if isinstance(table, dict) and table.get("name") == table_name:
                        table_info = table
                        break
            elif isinstance(tables, dict) and table_name in tables:
                # 字典格式：直接获取
                table_info = tables[table_name]

            if not table_info:
                return ""

            columns = table_info.get('columns', [])

            # 兼容两种格式：列表格式 [{"name": "col1", ...}, ...] 和字典格式 {"col1": {...}, ...}
            column_info = None
            if isinstance(columns, list):
                # 列表格式：查找匹配的列
                for col in columns:
                    if isinstance(col, dict) and col.get("name") == column_name:
                        column_info = col
                        break
            elif isinstance(columns, dict) and column_name in columns:
                # 字典格式：直接获取
                column_info = columns[column_name]

            if not column_info:
                return ""

            comment = column_info.get('comment', '')

            return comment or ""

        except Exception as e:
            logger.warning(f"获取列注释失败: {e}")
            return ""

    def _calculate_v2_score(
        self,
        candidate: Dict[str, Any],
        field_info: FieldInfo,
        graph_context: Dict[str, Any]
    ) -> float:
        """
        计算V2版本评分

        解决报错.md 问题：
        - #5 score混用
        - #6 强行加分
        - #7 粗暴Stopword
        - #10 高频字段

        Args:
            candidate: 候选字段信息
            field_info: 字段信息
            graph_context: 图谱上下文

        Returns:
            最终评分 (0.0 - 1.0)
        """
        from app.domains.data_mapping.scoring import calculate_final_score_v2

        return calculate_final_score_v2(
            candidate,
            field_info,
            graph_context,
            self.token_weight_calc
        )

    def _should_auto_confirm_v2(
        self,
        field_info: FieldInfo,
        top_candidate: Dict[str, Any],
        graph_context: Dict[str, Any]
    ) -> bool:
        """
        V2版本自动确认条件（收紧版）

        解决报错.md 问题 #8：自动确认危险

        条件：
        1. final_score > 0.9
        2. s_graph == 1.0（必须在连通子图中）
        3. 非通用字段

        Args:
            field_info: 字段信息
            top_candidate: 最高分候选
            graph_context: 图谱上下文

        Returns:
            是否自动确认
        """
        final_score = top_candidate.get('final_score', 0.0)
        candidate_table = top_candidate.get('db_table', '')

        # 条件1：分数高
        if final_score <= 0.9:
            return False

        # 条件2：在图谱中
        is_in_graph = candidate_table in graph_context.get('valid_tables', set())
        if not is_in_graph:
            return False

        # 条件3：非通用字段
        common_names = {'data', 'info', 'result', 'content', 'item',
                       'id', 'name', 'code', 'type', 'status', 'time', 'date',
                       'user', 'created', 'updated', 'deleted', 'description'}
        if field_info.field_name.lower() in common_names:
            return False

        return True

    def _get_sibling_fields(
        self,
        field_info: FieldInfo,
        api_context: Optional[APIContext] = None
    ) -> List[str]:
        """
        获取兄弟字段（修正版，解决报错.md 问题3）

        直接从API上下文获取，避免遍历注册表

        Args:
            field_info: 字段信息
            api_context: API上下文（可选）

        Returns:
            兄弟字段列表
        """
        if not api_context:
            logger.warning("缺少API上下文，无法获取兄弟字段")
            return []

        # 获取同一级别的字段
        base_path = field_info.field_path.rsplit('.', 1)[0]

        siblings = []
        for field in api_context.all_fields:
            if field.startswith(base_path) and field != field_info.field_path:
                siblings.append(field)

        return siblings

    def _build_ai_prompt_v2(
        self,
        field_info: FieldInfo,
        graph_context: Dict[str, Any],
        api_context: Optional[APIContext] = None
    ) -> Dict[str, Any]:
        """
        V2版本AI Prompt构建

        解决报错.md 问题：
        - AI-2：去除锚定（不发送Top3候选）
        - AI-3：兄弟节点上下文

        Args:
            field_info: 字段信息
            graph_context: 图谱上下文
            api_context: API上下文（可选）

        Returns:
            AI Prompt字典
        """
        # 获取兄弟字段
        sibling_fields = self._get_sibling_fields(field_info, api_context)

        # 获取图簇范围
        potential_tables = list(graph_context.get('valid_tables', set()))

        return {
            "target_field": {
                "name": field_info.field_name,
                "path": field_info.field_path,
                "description": field_info.field_description or "",
                "source_type": field_info.source_type
            },
            "api_context": {
                "method": field_info.apis[0]['method'] if field_info.apis else '',
                "path": field_info.apis[0]['path'] if field_info.apis else ''
            },
            "sibling_fields": sibling_fields,  # 新增：兄弟字段上下文
            "potential_tables": potential_tables,  # 只发送图计算出的表
            # 注意：不发送Top3候选，让AI独立思考
            "business_domain": graph_context.get('anchor_table', 'unknown'),
            "graph_context": {
                "anchor_table": graph_context.get('anchor_table'),
                "valid_tables_count": len(potential_tables)
            }
        }

    async def _process_api_with_semaphore(
        self,
        definition,
        semaphore: asyncio.Semaphore,
        graph: Any,
        db_schema: Dict[str, Any]
    ) -> Dict[str, List]:
        """
        带并发控制的API处理（V2版本）

        解决报错.md 问题 #13：并发打爆

        Args:
            definition: API定义
            semaphore: 并发控制信号量

        Returns:
            {field_path: candidates}
        """
        async with semaphore:
            logger.info(f"[{self.trace_id}] 处理API: {definition.method} {definition.path}")

            # 1. 提取该API的所有字段（使用V2版本）
            all_fields, api_context = self._extract_all_fields_v2(definition)

            # 2. 域推断（修正调用时机：在API内部）
            domain_inferer = DomainInferer(db_schema)
            allowed_tables = domain_inferer.infer(
                api_path=definition.path,
                fields=[f.split('.')[-1] for f in all_fields]
            )
            if not allowed_tables:
                logger.warning(f"[{self.trace_id}] 域推断失败，降级为全库搜索: {definition.method} {definition.path}")
                # 兼容两种格式：列表格式 [{"name": "table1", ...}, ...] 和字典格式 {"table1": {...}, ...}
                tables_data = db_schema.get("tables")
                if isinstance(tables_data, list):
                    allowed_tables = [table.get("name", "") for table in tables_data if isinstance(table, dict) and table.get("name")]
                elif isinstance(tables_data, dict):
                    allowed_tables = list(tables_data.keys())
                else:
                    allowed_tables = []

            # 3. 为每个字段创建FieldInfo（临时）
            field_infos = {}
            for field_path in all_fields:
                source_type, field_name = self._parse_field_path(field_path)

                # 提取字段描述
                from app.api.v1.field_mappings import _extract_field_descriptions
                field_descriptions = _extract_field_descriptions(definition)
                field_description = field_descriptions.get(field_path, '')

                field_info = FieldInfo(
                    field_name=field_name,
                    field_path=field_path,
                    field_description=field_description if field_description else None,
                    has_description=bool(field_description and field_description.strip()),
                    source_type=source_type,
                    apis=[{
                        'definition_id': definition.id,
                        'method': definition.method,
                        'path': definition.path,
                        'field_path': field_path
                    }],
                    total_count=1,
                    first_seen=f"{definition.method} {definition.path}",
                    appears_in_multiple_apis=False,
                    field_name_common=field_name in {'data', 'info', 'result', 'content', 'item'},
                    allowed_tables=allowed_tables
                )
                field_infos[field_path] = field_info

            # 4. 向量搜索（使用批量搜索，性能优化）
            candidates_map = {}
            vector_manager = get_vector_manager()

            # 批量向量搜索
            field_names = [info.field_name for info in field_infos.values()]
            batch_candidates = vector_manager.batch_search(
                field_names,
                top_k=10,
                allowed_tables=allowed_tables
            )

            # 分发批量搜索结果
            for i, (field_path, field_info) in enumerate(field_infos.items()):
                if i < len(batch_candidates):
                    candidates = batch_candidates[i]

                    # 转换为字典格式
                    candidate_dicts = []
                    for cand in candidates:
                        candidate_dicts.append({
                            'db_table': cand['db_table'],
                            'db_column': cand['db_column'],
                            'score': cand['score'],
                            'reasons': ['向量相似度']
                        })

                    candidates_map[field_path] = candidate_dicts
                else:
                    candidates_map[field_path] = []

            # 5. 构建图谱上下文（使用传入的graph，避免重复构建）
            graph_context = self._build_graph_context(candidates_map, graph)
            graph_context['allowed_tables'] = allowed_tables

            # 6. V2评分
            scored_candidates_map = {}
            for field_path, candidates in candidates_map.items():
                field_info = field_infos[field_path]

                # 计算每个候选的V2评分
                scored_candidates = []
                for cand in candidates:
                    final_score = self._calculate_v2_score(cand, field_info, graph_context)
                    cand_copy = cand.copy()
                    cand_copy['final_score'] = final_score
                    scored_candidates.append(cand_copy)

                # 按final_score排序
                scored_candidates.sort(key=lambda x: x.get('final_score', 0.0), reverse=True)

                scored_candidates_map[field_path] = scored_candidates

            # 7. AI优化（阶段4）
            ai_optimized_candidates_map = {}
            for field_path, scored_candidates in scored_candidates_map.items():
                field_info = field_infos[field_path]

                if not scored_candidates:
                    ai_optimized_candidates_map[field_path] = []
                    continue

                # 获取最高分候选
                top_candidate = scored_candidates[0]

                # 检查是否自动确认
                should_auto_confirm = self._should_auto_confirm_v2(
                    field_info,
                    top_candidate,
                    graph_context
                )

                if should_auto_confirm:
                    # 自动确认：直接使用最高分候选
                    logger.debug(f"[{self.trace_id}] 字段 {field_path} 自动确认: "
                               f"{top_candidate['db_table']}.{top_candidate['db_column']} "
                               f"(score={top_candidate['final_score']:.3f})")
                    ai_optimized_candidates_map[field_path] = scored_candidates[:1]
                else:
                    # 需要AI优化：构建AI Prompt
                    ai_prompt = self._build_ai_prompt_v2(
                        field_info,
                        graph_context,
                        api_context
                    )

                    # 调用AI服务（这里暂时保留原有候选，实际应该调用AI）
                    # TODO: 实现AI调用逻辑
                    logger.debug(f"[{self.trace_id}] 字段 {field_path} 需要AI优化")

                    # 暂时返回原有候选，等待AI优化实现
                    ai_optimized_candidates_map[field_path] = scored_candidates[:3]

            # 8. 语义验证（阶段5）
            validated_candidates_map = {}
            vector_manager = get_vector_manager()

            for field_path, candidates in ai_optimized_candidates_map.items():
                field_info = field_infos[field_path]

                if not candidates:
                    validated_candidates_map[field_path] = []
                    continue

                # 对每个候选进行语义验证
                validated_candidates = []
                for cand in candidates:
                    # 获取列注释
                    column_comment = self._get_column_comment(
                        db_schema,
                        cand.get('db_table', ''),
                        cand.get('db_column', '')
                    )

                    # 向量相似度验证
                    from app.domains.data_mapping.validation import validate_with_vector_similarity
                    is_valid = validate_with_vector_similarity(
                        field_info.field_description or "",
                        column_comment,
                        vector_manager,
                        threshold=0.75
                    )

                    if is_valid:
                        validated_candidates.append(cand)
                    else:
                        logger.debug(f"[{self.trace_id}] 候选 {cand.get('db_table')}.{cand.get('db_column')} "
                                   f"未通过向量验证")

                if validated_candidates:
                    validated_candidates_map[field_path] = validated_candidates
                elif candidates:
                    fallback_candidate = candidates[0].copy()
                    fallback_reasons = list(fallback_candidate.get("reasons", []))
                    fallback_reasons.append("semantic_validation_fallback_top1")
                    fallback_candidate["reasons"] = fallback_reasons
                    validated_candidates_map[field_path] = [fallback_candidate]
                else:
                    validated_candidates_map[field_path] = []

            # 9. 返回结果
            return validated_candidates_map

    async def _batch_rule_scoring(
        self,
        field_registry: Dict[str, FieldInfo],
        db_schema: Dict[str, Any],
        stages: List[Dict[str, Any]],
        field_description_map: Optional[Dict[str, str]] = None
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """
        批量规则评分
        
        Returns:
            评分结果: {field_name: [candidates]}
        """
        logger.info(f"[{self.trace_id}] 开始批量规则评分: "
                   f"{len(field_registry)}个字段")
        
        # 确保向量索引已构建
        vector_manager = get_vector_manager()
        if vector_manager.column_vectors is None:
            logger.info(f"[{self.trace_id}] 向量索引未构建，开始构建...")
            vector_manager.build_index(db_schema)
            if vector_manager.column_vectors is None or len(vector_manager.column_vectors) == 0:
                logger.error(f"[{self.trace_id}] 向量索引构建失败，无法进行规则评分")
                return {field_name: [] for field_name in field_registry.keys()}
            logger.info(f"[{self.trace_id}] 向量索引构建完成: {len(vector_manager.column_vectors)}个列")
        
        # 将字段分批
        field_items = list(field_registry.items())
        batches = [
            field_items[i:i + self.batch_size]
            for i in range(0, len(field_items), self.batch_size)
        ]
        
        all_results = {}
        total_batches = len(batches)
        total_fields = len(field_items)
        processed_fields = 0
        
        # 使用异步并发处理各批次
        batch_tasks = []
        for idx, batch in enumerate(batches):
            batch_task = asyncio.create_task(
                self._process_rule_scoring_batch_async(batch, db_schema, idx, field_description_map)
            )
            batch_tasks.append(batch_task)
        
        # 等待所有批次完成
        batch_results_list = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # 收集结果
        for idx, result in enumerate(batch_results_list):
            if isinstance(result, Exception):
                logger.error(f"[{self.trace_id}] 批次{idx}处理失败: {str(result)}")
            elif result:
                all_results.update(result)
                completed = idx + 1
                processed_fields += len(batches[idx])
                
                stage_progress = int((completed / total_batches) * 100)
                self._update_stage_progress(stages, 1, "running", stage_progress)
                overall_progress = 15 + int((completed / total_batches) * 20)  # 15-35%
                self._update_realtime_progress(
                    overall_progress,
                    f"规则评分 {completed}/{total_batches}",
                    processed_fields,
                    total_fields
                )

        expected_instances = set(field_registry.keys())
        actual_instances = set(all_results.keys())
        missing_instances = sorted(expected_instances - actual_instances)
        if missing_instances:
            logger.warning(
                f"[{self.trace_id}] 规则评分结果缺失: expected={len(expected_instances)}, "
                f"actual={len(actual_instances)}, missing={len(missing_instances)}, "
                f"samples={missing_instances[:10]}"
            )

        cache_key_to_has_candidates: Dict[str, bool] = {}
        for instance_key, candidates in all_results.items():
            field_info = field_registry.get(instance_key)
            if not field_info:
                continue
            cache_key = field_info.logical_cache_key or self._build_logical_cache_key(
                field_info.source_type,
                field_info.field_name
            )
            allowed_tables = sorted(
                set(getattr(field_info, "allowed_tables", None) or db_schema.get("allowed_tables") or [])
            )
            if allowed_tables:
                cache_key = f"{cache_key}|{','.join(allowed_tables)}"
            cache_key_to_has_candidates[cache_key] = (
                cache_key_to_has_candidates.get(cache_key, False) or bool(candidates)
            )

        total_cache_keys = len(cache_key_to_has_candidates)
        non_empty_cache_keys = sum(1 for has in cache_key_to_has_candidates.values() if has)
        empty_cache_keys = [key for key, has in cache_key_to_has_candidates.items() if not has]
        self._rule_scoring_debug = {
            "total_cache_keys": total_cache_keys,
            "non_empty_cache_keys": non_empty_cache_keys,
            "non_empty_ratio": round(non_empty_cache_keys / total_cache_keys, 4) if total_cache_keys else 0.0,
            "sample_empty_cache_keys": empty_cache_keys[:10]
        }

        rule_trace_rows = []
        for field_key, candidates in all_results.items():
            field_info = field_registry.get(field_key)
            if not field_info:
                continue
            rule_trace_rows.extend(
                self._write_rule_traces(
                    field_key=field_key,
                    candidates=candidates,
                    graph_context={},
                    allowed_tables=field_info.allowed_tables
                )
            )
        self._bulk_write_traces(rule_trace_rows)
        
        logger.info(f"[{self.trace_id}] 批量规则评分完成")
        return all_results
    
    async def _process_rule_scoring_batch_async(
        self,
        batch: List[Tuple[str, FieldInfo]],
        db_schema: Dict[str, Any],
        batch_idx: int = 0,
        field_description_map: Optional[Dict[str, str]] = None
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """
        异步处理一批字段的规则评分（使用向量搜索 + 重心算法）
        
        Returns:
            评分结果: {field_name: [candidates]}
        """
        logger.info(f"[{self.trace_id}] 开始处理批次{batch_idx}: {len(batch)}个字段")
        results = {}
        
        try:
            cache_key_to_instances: Dict[str, List[Tuple[str, FieldInfo]]] = {}
            cache_key_to_query: Dict[str, Dict[str, Any]] = {}

            for instance_key, field_info in batch:
                cache_key = field_info.logical_cache_key or self._build_logical_cache_key(
                    field_info.source_type,
                    field_info.field_name
                )
                allowed_tables = sorted(
                    set(getattr(field_info, "allowed_tables", None) or db_schema.get("allowed_tables") or [])
                )
                if allowed_tables:
                    cache_key = f"{cache_key}|{','.join(allowed_tables)}"
                cache_key_to_instances.setdefault(cache_key, []).append((instance_key, field_info))
                if cache_key not in cache_key_to_query:
                    field_description = ""
                    if field_description_map:
                        field_description = field_description_map.get(field_info.field_path, "") or ""
                    cache_key_to_query[cache_key] = {
                        "field_name": field_info.field_name,
                        "field_description": field_description,
                        "allowed_tables": allowed_tables if allowed_tables else None
                    }

            # 使用向量搜索批量生成候选（禁用 AI 兜底，阶段2只做规则评分）。
            # 关键修复：按 cache_key 检索和回填，避免相同 field_path 被覆盖。
            vector_manager = get_vector_manager()
            vector_results = await vector_manager.batch_search_with_gravity_by_key(
                queries=cache_key_to_query,
                top_k=20,
                use_ai_fallback=False
            )
            key_results: Dict[str, List[Dict[str, Any]]] = vector_results.get("results", {})

            cache_key_candidates: Dict[str, List[FieldMappingCandidate]] = {}
            for cache_key in cache_key_to_instances.keys():
                candidates_dicts = key_results.get(cache_key, [])
                cache_key_candidates[cache_key] = [
                    FieldMappingCandidate(
                        db_table=cand.get("db_table", ""),
                        db_column=cand.get("db_column", ""),
                        score=cand.get("score", 0.0),
                        reasons=cand.get("reasons", [])
                    )
                    for cand in candidates_dicts
                ]

            for cache_key, instances in cache_key_to_instances.items():
                shared_candidates = cache_key_candidates.get(cache_key, [])
                for instance_key, _ in instances:
                    results[instance_key] = self._clone_candidates(shared_candidates)
                
        except Exception as e:
            logger.error(f"[{self.trace_id}] 批次{batch_idx}向量搜索失败: {str(e)}")
            # 降级处理：为所有字段返回空列表
            for instance_key, _ in batch:
                results[instance_key] = []
        
        logger.info(f"[{self.trace_id}] 批次{batch_idx}处理完成: {len(results)}个字段有结果")
        return results

    async def _process_rule_scoring_batch(
        self,
        batch: List[Tuple[str, FieldInfo]],
        db_schema: Dict[str, Any],
        field_description_map: Optional[Dict[str, str]] = None
    ) -> Dict[str, List[FieldMappingCandidate]]:
        return await self._process_rule_scoring_batch_async(
            batch, db_schema, batch_idx=-1, field_description_map=field_description_map
        )

    def _intelligent_screening(
        self,
        field_registry: Dict[str, FieldInfo],
        rule_results: Dict[str, List[FieldMappingCandidate]]
    ) -> Dict[str, List[str]]:
        """
        智能筛选

        Returns:
            分类结果: {
                'auto_confirm': [field_names],
                'ai_high': [field_names],
                'ai_medium': [field_names],
                'ai_low': [field_names]
            }
        """
        # 检查规则评分是否全部失败
        total_fields = len(field_registry)
        failed_fields = sum(1 for field_name in field_registry if not rule_results.get(field_name))

        if failed_fields == total_fields:
            logger.warning(f"[{self.trace_id}] 规则评分全部失败 ({failed_fields}/{total_fields})，跳过智能筛选")
            return {
                'auto_confirm': [],
                'ai_high': [],
                'ai_medium': [],
                'ai_low': []
            }

        logger.info(f"[{self.trace_id}] 开始智能筛选")

        categories = {
            'auto_confirm': [],
            'ai_high': [],
            'ai_medium': [],
            'ai_low': []
        }

        for field_name, field_info in field_registry.items():
            rule_candidates = rule_results.get(field_name, [])
            screening_result = self._screen_field(field_info.field_name, field_info, rule_candidates)

            # 更新字段信息
            field_info.rule_candidates = rule_candidates
            field_info.rule_top_score = rule_candidates[0].score if rule_candidates else 0.0
            field_info.ai_priority = screening_result.ai_priority
            field_info.screening_reasons = screening_result.reasons

            # 分类
            if screening_result.ai_priority == "none":
                categories['auto_confirm'].append(field_name)
            elif screening_result.ai_priority == "high":
                categories['ai_high'].append(field_name)
            elif screening_result.ai_priority == "medium":
                categories['ai_medium'].append(field_name)
            else:
                categories['ai_low'].append(field_name)

        logger.info(f"[{self.trace_id}] 智能筛选完成: "
                   f"自动确认={len(categories['auto_confirm'])}, "
                   f"高优先级AI={len(categories['ai_high'])}, "
                   f"中优先级AI={len(categories['ai_medium'])}, "
                   f"低优先级AI={len(categories['ai_low'])}")

        return categories

    def _merge_ai_priority(self, current_priority: str, new_priority: str) -> str:
        """Keep the higher priority to avoid lower-priority rules overriding higher ones."""
        rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
        current_rank = rank.get(current_priority, 0)
        new_rank = rank.get(new_priority, 0)
        return new_priority if new_rank > current_rank else current_priority
    
    def _screen_field(
        self,
        field_name: str,
        field_info: FieldInfo,
        rule_candidates: List[FieldMappingCandidate]
    ) -> ScreeningResult:
        """
        对单个字段进行智能筛选
        """
        reasons = []
        ai_priority = "none"
        
        # 获取最高规则评分
        top_score = rule_candidates[0].score if rule_candidates else 0.0
        
        # === 第一级：规则评分筛选 ===
        if top_score >= 0.85:
            ai_priority = "none"
            reasons.append("规则评分高(≥0.85)，无需AI确认")
            return ScreeningResult(
                ai_priority="none",
                reasons=reasons,
                action="auto_confirm"
            )
        elif top_score >= 0.60:
            ai_priority = self._merge_ai_priority(ai_priority, "medium")
            reasons.append("规则评分中等(0.60-0.85)，AI优化候选排序")
        else:
            ai_priority = self._merge_ai_priority(ai_priority, "high")
            reasons.append("规则评分低(<0.60)，需要AI重新推荐")
        
        # === 第二级：候选数量筛选 ===
        candidate_count = len(rule_candidates)
        if candidate_count <= 1:
            ai_priority = self._merge_ai_priority(ai_priority, "high")
            reasons.append(f"候选数量过少({candidate_count}个)，需要AI扩展")
        elif candidate_count >= 5:
            ai_priority = self._merge_ai_priority(ai_priority, "high")
            reasons.append(f"候选数量过多({candidate_count}个)，需要AI筛选")
        elif candidate_count >= 3 and top_score < 0.70:
            ai_priority = self._merge_ai_priority(ai_priority, "high")
            reasons.append("候选较多且置信度不足，需要AI重新排序")
        
        # === 第三级：字段类型筛选（增强版）===
        if self._is_id_field(field_name):
            # 使用字段描述验证是否真的是 ID 类型
            if self._is_id_type_by_description(field_info.field_description):
                ai_priority = self._merge_ai_priority(ai_priority, "high")
                reasons.append("ID类字段，需要AI精确匹配")
            else:
                # 字段名看起来像 ID，但描述说明不是
                ai_priority = self._merge_ai_priority(ai_priority, "medium")
                reasons.append("字段名像ID但描述表明不是，AI需确认")
        
        if self._is_complex_nested(field_info.field_path):
            ai_priority = self._merge_ai_priority(ai_priority, "high")
            reasons.append("复杂嵌套字段，需要AI深度分析")
        
        if self._is_array_field(field_info.field_path):
            ai_priority = self._merge_ai_priority(ai_priority, "medium")
            reasons.append("数组字段，建议AI优化")
        
        # === 第四级：语义冲突筛选（增强版）===
        if self._has_semantic_conflict(
            rule_candidates, 
            field_name, 
            field_info.field_description,  # 传递字段描述
            field_info.apis[0]['path']
        ):
            ai_priority = self._merge_ai_priority(ai_priority, "high")
            reasons.append("路径语义与候选表名冲突，需要AI纠正")
        
        # === 第五级：使用模式筛选 ===
        if field_info.appears_in_multiple_apis:
            ai_priority = self._merge_ai_priority(ai_priority, "low")
            reasons.append(f"字段在{field_info.total_count}个API中使用，AI可学习模式")
        
        if field_info.field_name_common:
            ai_priority = self._merge_ai_priority(ai_priority, "low")
            reasons.append("通用字段名，建议AI确认上下文")
        
        return ScreeningResult(
            ai_priority=ai_priority,
            reasons=reasons,
            action="ai_enhance" if ai_priority != "none" else "auto_confirm"
        )
    
    def _is_id_field(self, field_name: str) -> bool:
        """判断是否为ID字段"""
        id_patterns = [
            r'^id$', r'_id$', r'Id$', r'ID$',
            r'uuid', r'key$', r'ref_id$'
        ]
        return any(re.search(pattern, field_name, re.IGNORECASE) for pattern in id_patterns)
    
    def _is_complex_nested(self, field_path: str) -> bool:
        """判断是否为复杂嵌套字段"""
        return field_path.count('.') >= 3
    
    def _is_array_field(self, field_path: str) -> bool:
        """判断是否为数组字段"""
        return '[]' in field_path or 'items' in field_path.lower()
    
    def _is_id_type_by_description(self, field_description: Optional[str]) -> bool:
        """
        根据字段描述判断是否为 ID 类型
        
        Args:
            field_description: 字段描述
            
        Returns:
            是否为 ID 类型
        """
        if not field_description:
            # 没有描述时，保守判断
            return True
        
        # 检查描述中是否包含 ID 相关关键词
        id_keywords = [
            'id', 'ID', '标识', '唯一标识', 
            'unique', 'identifier', 'uuid', '主键',
            '主键ID', '唯一ID', 'ID号'
        ]
        
        # 如果描述中包含 ID 关键词，认为是 ID 类型
        for keyword in id_keywords:
            if keyword in field_description:
                return True
        
        # 如果描述明确说明不是 ID（如 "订单编号（非ID）"），则不是
        not_id_keywords = [
            '非ID', 'not id', '不是id', '编号(非ID)', 
            '非标识', 'not identifier', '编号(字符串)'
        ]
        for keyword in not_id_keywords:
            if keyword in field_description:
                return False
        
        # 检查描述长度和内容
        description_lower = field_description.lower().strip()
        
        # 如果描述较短且不包含明确信息，保守认为是 ID 类型
        if len(description_lower) < 10:
            return True
        
        # 如果描述是纯数字相关（如 "12345"），可能是 ID
        if description_lower.isdigit():
            return True
        
        # 如果描述包含 "号"、"码" 等词，可能是编号类，但不是 ID
        code_keywords = ['编号', '号码', '代码', 'code', 'number']
        for keyword in code_keywords:
            if keyword in field_description:
                return False
        
        # 默认判断
        return True
    
    def _description_supports_candidate(
        self,
        field_description: str,
        candidate: FieldMappingCandidate
    ) -> bool:
        """
        检查字段描述是否支持候选
        
        Args:
            field_description: 字段描述
            candidate: 候选映射
            
        Returns:
            是否支持
        """
        if not field_description:
            return False
        
        # 提取表名关键词
        table_keywords = re.split(r"[_\\W]+", candidate.db_table.lower())
        
        # 检查描述中是否包含表名关键词
        for keyword in table_keywords:
            if len(keyword) >= 3 and keyword in field_description.lower():
                return True
        
        return False
    
    def _has_semantic_conflict(
        self,
        candidates: List[FieldMappingCandidate],
        field_name: str,
        field_description: Optional[str],  # 新增参数
        api_path: str
    ) -> bool:
        """判断是否存在语义冲突"""
        if not candidates:
            return False

        # 提取路径资源词：过滤路径参数和过短片段
        path_resources = [
            seg.lower()
            for seg in api_path.strip('/').split('/')
            if seg and not seg.startswith('{') and len(seg) > 2
        ]
        if not path_resources:
            return False

        def _table_overlap_score(table: str) -> int:
            table_tokens = set(re.split(r"[_\\W]+", (table or "").lower()))
            table_tokens.discard("")
            return sum(1 for resource in path_resources if resource in table_tokens)

        top_candidate = candidates[0]
        top_overlap = _table_overlap_score(top_candidate.db_table)

        # Top1 已和路径资源一致，不判冲突
        if top_overlap > 0:
            return False

        # 使用字段描述辅助判断
        if field_description and len(candidates) > 1:
            # 检查其他候选是否与字段描述更匹配
            for candidate in candidates[1:]:
                overlap = _table_overlap_score(candidate.db_table)
                cand_score = candidate.score or 0.0
                top_score = top_candidate.score or 0.0
                
                # 如果其他候选与路径资源匹配且分数接近，且有描述支持
                if overlap > 0 and cand_score >= top_score - self.semantic_conflict_min_score_gap:
                    # 检查字段描述是否支持这个候选
                    if self._description_supports_candidate(field_description, candidate):
                        return True

        # 存在“资源更匹配且分差不大”的备选，才判语义冲突，降低误报
        top_score = top_candidate.score or 0.0
        for candidate in candidates[1:]:
            overlap = _table_overlap_score(candidate.db_table)
            cand_score = candidate.score or 0.0
            if overlap > 0 and cand_score >= top_score - self.semantic_conflict_min_score_gap:
                return True

        return False
    
    async def _priority_ai_calling(
        self,
        field_registry: Dict[str, FieldInfo],
        categories: Dict[str, List[str]],
        stages: List[Dict[str, Any]],
        db_schema: Dict[str, Any]
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """
        优先级AI调用
        
        Returns:
            AI结果: {field_name: [candidates]}
        """
        logger.info(f"[{self.trace_id}] 开始优先级AI调用")
        
        # 创建优先级队列
        priority_queue = PriorityAIQueue()
        
        # 将字段加入队列
        ai_field_names = []
        for field_name in categories.get('ai_high', []):
            priority_queue.enqueue(field_name, field_registry[field_name])
            ai_field_names.append(field_name)
        for field_name in categories.get('ai_medium', []):
            priority_queue.enqueue(field_name, field_registry[field_name])
            ai_field_names.append(field_name)
        for field_name in categories.get('ai_low', []):
            priority_queue.enqueue(field_name, field_registry[field_name])
            ai_field_names.append(field_name)
        
        all_results = {}
        total_batches = 0
        completed_batches = 0
        processed_ai_fields = 0
        total_ai_fields = len(ai_field_names)
        
        # 统计总批次数
        temp_queue = PriorityAIQueue()
        for field_name in ai_field_names:
            temp_queue.enqueue(field_name, field_registry[field_name])
        
        while not temp_queue.is_empty():
            priority, batch = temp_queue.get_next_batch()
            if batch:
                total_batches += 1
        
        # 批量处理
        while not priority_queue.is_empty():
            self._raise_if_cancelled()
            
            priority, batch = priority_queue.get_next_batch()
            if not batch:
                break
            
            try:
                batch_results = await self._call_ai_batch(batch)
                batch_results = self._apply_ai_safety_validation(
                    batch_results=batch_results,
                    field_registry=field_registry,
                    db_schema=db_schema
                )
                all_results.update(batch_results)
                
                completed_batches += 1
                processed_ai_fields += len(batch)
                
                stage_progress = int((completed_batches / total_batches) * 100)
                self._update_stage_progress(stages, 3, "running", stage_progress)
                overall_progress = 45 + int((completed_batches / total_batches) * 50)  # 45-95%
                self._update_realtime_progress(
                    overall_progress,
                    f"AI优化 {completed_batches}/{total_batches}",
                    processed_ai_fields,
                    total_ai_fields
                )
                
            except Exception as e:
                logger.error(f"[{self.trace_id}] AI批次处理失败: {str(e)}")
                # 返回规则结果作为降级方案
                for req in batch:
                    all_results[req.field_name] = req.rule_candidates
        
        logger.info(f"[{self.trace_id}] 优先级AI调用完成")
        return all_results

    def _column_exists(self, db_schema: Dict[str, Any], table: str, column: str) -> bool:
        """校验 AI 推荐的表字段是否在物理 schema 中真实存在。"""
        if not db_schema or not isinstance(db_schema, dict):
            return False
        if not table or not column:
            return False

        tables = db_schema.get("tables", {})

        # 兼容两种格式：列表格式 [{"name": "table1", "columns": [...]}, ...] 和字典格式 {"table1": {"columns": [...]}, ...}
        table_info = None
        if isinstance(tables, list):
            # 列表格式：查找匹配的表
            for t in tables:
                if isinstance(t, dict) and t.get("name") == table:
                    table_info = t
                    break
        elif isinstance(tables, dict):
            # 字典格式：直接获取
            table_info = tables.get(table)

        if not isinstance(table_info, dict):
            return False

        columns = table_info.get("columns", [])
        if isinstance(columns, dict):
            return column in columns
        if isinstance(columns, list):
            # 列表格式：检查列名是否存在
            return any(col.get("name") == column for col in columns if isinstance(col, dict))
        return False

    def _build_valid_tables_for_field(self, field_info: FieldInfo) -> set:
        """
        Step1 的域合理性校验数据来源：
        Step4 使用 DomainInferer 的 allowed_tables，缺失时回退规则候选集合。
        """
        if field_info.allowed_tables:
            return set(field_info.allowed_tables)

        valid_tables = set()
        for candidate in field_info.rule_candidates or []:
            if candidate and candidate.db_table:
                valid_tables.add(candidate.db_table)
        return valid_tables

    def _apply_ai_safety_validation(
        self,
        batch_results: Dict[str, List[FieldMappingCandidate]],
        field_registry: Dict[str, FieldInfo],
        db_schema: Dict[str, Any]
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """
        双层 AI 防护：
        1) 物理存在校验（硬拒绝）
        2) 域合理性校验（软打折，*0.8）
        """
        sanitized_results: Dict[str, List[FieldMappingCandidate]] = {}
        ai_trace_rows: List[FieldMappingTrace] = []

        for field_name, ai_candidates in batch_results.items():
            field_info = field_registry.get(field_name)
            rule_fallback = (field_info.rule_candidates or [])[:1] if field_info else []

            if not ai_candidates:
                sanitized_results[field_name] = []
                continue

            for cand in ai_candidates:
                cand.score = _normalize_confidence_value(cand.score, default=0.5)

            top_candidate = ai_candidates[0]

            if not self._column_exists(db_schema, top_candidate.db_table, top_candidate.db_column):
                logger.error(
                    f"[{self.trace_id}] AI_HALLUCINATION field={field_name} "
                    f"candidate={top_candidate.db_table}.{top_candidate.db_column} "
                    f"action=fallback_rule_top1"
                )
                sanitized_results[field_name] = rule_fallback
                ai_trace_rows.extend(
                    self._write_ai_traces(
                        field_key=field_name,
                        ai_candidate=top_candidate,
                        is_hallucination=True,
                        in_valid_tables=False
                    )
                )
                continue

            valid_tables = self._build_valid_tables_for_field(field_info) if field_info else set()
            in_valid_tables = True
            if valid_tables and top_candidate.db_table not in valid_tables:
                in_valid_tables = False
                original_score = top_candidate.score
                top_candidate.score = _normalize_confidence_value(original_score * 0.8, default=0.5)
                top_candidate.reasons = list(top_candidate.reasons or [])
                top_candidate.reasons.append("域外软校验置信度折扣(0.8)")
                logger.warning(
                    f"[{self.trace_id}] AI_SOFT_PENALTY field={field_name} "
                    f"table={top_candidate.db_table} "
                    f"confidence={original_score:.3f}->{top_candidate.score:.3f}"
                )

            sanitized_results[field_name] = ai_candidates
            ai_trace_rows.extend(
                self._write_ai_traces(
                    field_key=field_name,
                    ai_candidate=top_candidate,
                    is_hallucination=False,
                    in_valid_tables=in_valid_tables
                )
            )

        self._bulk_write_traces(ai_trace_rows)

        return sanitized_results

    def _bulk_write_traces(self, trace_rows: List[FieldMappingTrace]) -> None:
        """批量写入 traces，失败时只记录日志不影响主流程。"""
        if not trace_rows:
            return

        try:
            self.db.bulk_save_objects(trace_rows)
            self._commit_with_retry()
            logger.info(f"[{self.trace_id}] traces写入完成: {len(trace_rows)}条")
        except Exception as e:
            self.db.rollback()
            logger.warning(f"[{self.trace_id}] traces写入失败，已降级忽略: {str(e)}")

    def _write_rule_traces(
        self,
        field_key: str,
        candidates: List[FieldMappingCandidate],
        graph_context: Optional[Dict[str, Any]],
        allowed_tables: Optional[List[str]]
    ) -> List[FieldMappingTrace]:
        """
        构建规则评分 traces（Step2 默认 in_allowed_tables=True，Step4 再接入真实值）。
        """
        rows: List[FieldMappingTrace] = []
        candidate_list = candidates or []
        if not candidate_list:
            return rows

        # field_key 形如 "definition_id:body.order_id"
        definition_id = 0
        try:
            definition_id = int(str(field_key).split(":", 1)[0])
        except Exception:
            return rows

        anchor_table = (graph_context or {}).get("anchor_table")
        allowed_set = set(allowed_tables) if allowed_tables else None

        for candidate in candidate_list[:10]:
            candidate_name = f"{candidate.db_table}.{candidate.db_column}"
            in_allowed = True if allowed_set is None else candidate.db_table in allowed_set
            rows.append(
                FieldMappingTrace(
                    task_id=self.task.id,
                    project_id=self.task.project_id,
                    definition_id=definition_id,
                    trace_id=self.trace_id,
                    field_key=field_key,
                    candidate=candidate_name,
                    stage="rule_scoring",
                    decision_source="rule",
                    in_allowed_tables=in_allowed,
                    is_anchor_table=(candidate.db_table == anchor_table) if anchor_table else None,
                    s_vector=None,
                    s_exact=None,
                    s_graph=None,
                    final_score=candidate.score
                )
            )
        return rows

    def _write_ai_traces(
        self,
        field_key: str,
        ai_candidate: FieldMappingCandidate,
        is_hallucination: bool,
        in_valid_tables: bool
    ) -> List[FieldMappingTrace]:
        """构建 AI traces，含 ai/fallback 决策来源。"""
        if not ai_candidate:
            return []

        try:
            definition_id = int(str(field_key).split(":", 1)[0])
        except Exception:
            return []

        decision_source = "fallback" if is_hallucination else "ai"
        candidate_name = f"{ai_candidate.db_table}.{ai_candidate.db_column}"
        return [
            FieldMappingTrace(
                task_id=self.task.id,
                project_id=self.task.project_id,
                definition_id=definition_id,
                trace_id=self.trace_id,
                field_key=field_key,
                candidate=candidate_name,
                stage="ai_optimization",
                decision_source=decision_source,
                in_allowed_tables=in_valid_tables,
                is_anchor_table=None,
                s_vector=None,
                s_exact=None,
                s_graph=None,
                final_score=ai_candidate.score
            )
        ]
    
    async def _call_ai_batch(
        self,
        requests: List[AIRequest]
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """
        批量调用AI服务（带重试机制）
        
        Returns:
            AI结果: {field_name: [candidates]}
        """
        if not requests:
            return {}
        
        # 构建批量AI输入
        batch_input = {
            "field_mappings": [
                {
                    "api_field_path": req.field_path,
                    "method": req.api_context['method'],
                    "path": req.api_context['path'],
                    "field_name": req.field_name,
                    "field_description": req.field_description or "",  # 传递字段描述
                    "logical_field_name": req.field_path.split('.', 1)[1] if '.' in req.field_path else req.field_path,
                    "rule_candidates": [
                        {
                            "db_table": c.db_table,
                            "db_column": c.db_column,
                            "score": c.score,
                            "reasons": c.reasons,
                            "comment": c.comment if hasattr(c, 'comment') else ""  # 添加数据库列注释
                        }
                        for c in req.rule_candidates[:3]
                    ]
                }
                for req in requests
            ]
        }
        
        # 重试逻辑
        for attempt in range(self.max_ai_retries):
            try:
                result = await self._execute_ai_call(batch_input)
                return self._parse_ai_result(result, requests)
                
            except concurrent.futures.TimeoutError:
                logger.warning(
                    f"[{self.trace_id}] AI调用超时（尝试{attempt + 1}/{self.max_ai_retries}）"
                )
                if attempt < self.max_ai_retries - 1:
                    await asyncio.sleep(self.ai_retry_delay)
                continue
                    
            except Exception as e:
                logger.error(
                    f"[{self.trace_id}] AI调用失败（尝试{attempt + 1}/{self.max_ai_retries}）: {str(e)}"
                )
                if attempt < self.max_ai_retries - 1:
                    await asyncio.sleep(self.ai_retry_delay)
                continue
        
        # 所有重试失败，返回规则结果作为降级方案
        logger.warning(f"[{self.trace_id}] AI调用全部失败，使用规则结果降级")
        for req in requests:
            self.failed_fields.add(req.field_name)
        return {req.field_name: req.rule_candidates for req in requests}
    
    async def _execute_ai_call(self, batch_input: Dict[str, Any]) -> Any:
        """
        执行AI调用（在线程池中运行）
        
        Args:
            batch_input: 批量输入数据
            
        Returns:
            AI返回结果
        """
        import asyncio
        
        def _async_call():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.ai_service.execute(
                        task_type="field_mapping_recommendation_batch",
                        project_id=self.task.project_id,
                        input_data=batch_input
                    )
                )
            finally:
                loop.close()
        
        # 使用线程池执行AI调用
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_async_call)
            return future.result(timeout=self.ai_timeout)
    
    def _parse_ai_result(
        self,
        ai_result: Any,
        requests: List[AIRequest]
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """解析AI返回结果"""
        results = {}

        if not ai_result.get("success"):
            logger.error(f"[{self.trace_id}] AI调用失败: {ai_result.get('error')}")
            return {req.field_name: req.rule_candidates for req in requests}

        result_data = ai_result.get("result", {})

        # 使用安全的 JSON 解析函数
        if isinstance(result_data, str):
            logger.debug(f"[{self.trace_id}] AI返回字符串结果（前500字符）: {result_data[:500]}")
            result_data = parse_json_safely(result_data)
            
            if result_data is None:
                logger.error(f"[{self.trace_id}] AI返回格式错误，无法解析为有效JSON")
                logger.error(f"[{self.trace_id}] 原始内容: {ai_result.get('result', '')[:500]}")
                return {req.field_name: req.rule_candidates for req in requests}

        # 检查解析后的数据格式
        if not isinstance(result_data, dict):
            logger.error(f"[{self.trace_id}] AI返回格式错误，期望dict，实际类型: {type(result_data)}")
            logger.error(f"[{self.trace_id}] 内容: {str(result_data)[:500]}")
            return {req.field_name: req.rule_candidates for req in requests}
        
        # 提取批量结果
        if isinstance(result_data, dict) and "field_mappings" in result_data:
            logger.info(f"[{self.trace_id}] AI返回包含 {len(result_data['field_mappings'])} 个字段映射结果")
            request_keys = [req.field_name for req in requests]
            for idx, mapping_result in enumerate(result_data["field_mappings"]):
                field_name = mapping_result.get("field_name")
                if field_name not in request_keys and idx < len(requests):
                    field_name = requests[idx].field_name
                ai_candidates = mapping_result.get("candidates", [])

                logger.debug(f"[{self.trace_id}] 处理字段 {field_name}: {len(ai_candidates)} 个候选")

                # 转换为FieldMappingCandidate
                candidates = []
                for cand in ai_candidates:
                    candidates.append(FieldMappingCandidate(
                        db_table=cand.get("db_table", ""),
                        db_column=cand.get("db_column", ""),
                        score=_normalize_confidence_value(cand.get("confidence", 0.5), default=0.5),
                        reasons=cand.get("reasons", [])
                    ))

                results[field_name] = candidates if candidates else []
        else:
            logger.error(f"[{self.trace_id}] AI返回格式错误，缺少 field_mappings 字段，实际键: {list(result_data.keys()) if isinstance(result_data, dict) else 'N/A'}")

        return results

    def _build_decision_trace(
        self,
        field_key: str,
        field_info: FieldInfo,
        rule_candidates: List[FieldMappingCandidate],
        ai_candidates: List[FieldMappingCandidate],
        final_candidates: List[FieldMappingCandidate]
    ) -> Dict[str, Any]:
        top_rule = rule_candidates[0] if rule_candidates else None
        top_ai = ai_candidates[0] if ai_candidates else None
        top_final = final_candidates[0] if final_candidates else None
        return {
            "trace_id": self.trace_id,
            "schema_version": SCHEMA_VERSION,
            "field_instance_key": field_key,
            "logical_cache_key": field_info.logical_cache_key,
            "source_type": field_info.source_type,
            "field_name": field_info.field_name,
            "api_context": field_info.apis[0] if field_info.apis else {},
            "ai_priority": field_info.ai_priority,
            "rule_top_score": field_info.rule_top_score,
            "rule_candidate_count": len(rule_candidates),
            "ai_candidate_count": len(ai_candidates),
            "top_rule_candidate": {
                "db_table": top_rule.db_table,
                "db_column": top_rule.db_column,
                "score": top_rule.score,
                "ai_selected": bool(getattr(top_rule, "ai_selected", False))
            } if top_rule else None,
            "top_ai_candidate": {
                "db_table": top_ai.db_table,
                "db_column": top_ai.db_column,
                "score": top_ai.score,
                "ai_selected": bool(getattr(top_ai, "ai_selected", False))
            } if top_ai else None,
            "top_final_candidate": {
                "db_table": top_final.db_table,
                "db_column": top_final.db_column,
                "score": top_final.score,
                "ai_selected": bool(getattr(top_final, "ai_selected", False))
            } if top_final else None
        }
    
    def _merge_results(
        self,
        field_registry: Dict[str, FieldInfo],
        ai_results: Dict[str, List[FieldMappingCandidate]],
        db_schema: Dict[str, Any]  # 新增参数
    ) -> List[FieldMappingSuggestion]:
        """
        合并规则结果和AI结果
        
        Returns:
            最终建议列表
        """
        logger.info(f"[{self.trace_id}] 开始合并结果")
        
        suggestions = []
        
        for field_key, field_info in field_registry.items():
            ai_candidates = ai_results.get(field_key, [])
            rule_candidates = field_info.rule_candidates or []  # 确保 rule_candidates 不为 None

            # Step4: AI 与规则同台竞技，避免无脑覆盖
            decision_source = "rule"
            if ai_candidates:
                ai_top = ai_candidates[0]
                rule_top = rule_candidates[0] if rule_candidates else None
                ai_score = ai_top.score or 0.0
                rule_score = (rule_top.score or 0.0) if rule_top else 0.0

                if rule_top and ai_score < rule_score:
                    final_candidates = rule_candidates
                    decision_source = "fallback"
                    logger.info(
                        f"[{self.trace_id}] AI置信度({ai_score:.3f})低于规则({rule_score:.3f})，回退规则: {field_key}"
                    )
                else:
                    final_candidates = ai_candidates
                    decision_source = "ai"
            else:
                final_candidates = rule_candidates

            field_info.final_candidates = final_candidates

            decision_trace = self._build_decision_trace(
                field_key=field_key,
                field_info=field_info,
                rule_candidates=rule_candidates,
                ai_candidates=ai_candidates,
                final_candidates=final_candidates
            )
            decision_trace["decision_source"] = decision_source
            
            # 为每个API生成建议
            for api_ref in field_info.apis:
                suggestion = FieldMappingSuggestion(
                    definition_id=api_ref['definition_id'],
                    definition_method=api_ref['method'],
                    definition_path=api_ref['path'],
                    api_field_path=api_ref['field_path'],
                    candidates=final_candidates,
                    decision_trace=decision_trace
                )
                suggestions.append(suggestion)
        
        logger.info(f"[{self.trace_id}] 结果合并完成: {len(suggestions)}个建议")
        return suggestions
    
    def _get_column_comment(self, db_schema: Dict[str, Any], table_name: str, column_name: str) -> str:
        """
        获取数据库列的注释

        Args:
            db_schema: 数据库结构
            table_name: 表名
            column_name: 列名

        Returns:
            列注释，如果不存在则返回空字符串
        """
        if not db_schema or not isinstance(db_schema, dict):
            return ""

        tables = db_schema.get("tables", {})

        # 兼容两种格式：列表格式 [{"name": "table1", "columns": [...]}, ...] 和字典格式 {"table1": {"columns": [...]}, ...}
        table_info = None
        if isinstance(tables, list):
            # 列表格式：查找匹配的表
            for table in tables:
                if isinstance(table, dict) and table.get("name") == table_name:
                    table_info = table
                    break
        elif isinstance(tables, dict) and table_name in tables:
            # 字典格式：直接获取
            table_info = tables[table_name]

        if not table_info:
            return ""

        columns = table_info.get('columns', [])

        # 兼容两种格式：列表格式 [{"name": "col1", ...}, ...] 和字典格式 {"col1": {...}, ...}
        column_info = None
        if isinstance(columns, list):
            # 列表格式：查找匹配的列
            for col in columns:
                if isinstance(col, dict) and col.get("name") == column_name:
                    column_info = col
                    break
        elif isinstance(columns, dict) and column_name in columns:
            # 字典格式：直接获取
            column_info = columns[column_name]

        if not column_info:
            return ""

        return column_info.get("comment", "")
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（基于关键词重叠）
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            相似度分数 0.0-1.0
        """
        if not text1 or not text2:
            return 0.0
        
        # 分词并转为小写
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        # 计算Jaccard相似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _validate_candidate_with_description(
        self,
        field_description: str,
        candidate: FieldMappingCandidate,
        db_schema: Dict[str, Any]
    ) -> bool:
        """
        使用字段描述验证候选映射是否合理
        
        Args:
            field_description: 字段描述
            candidate: 候选映射
            db_schema: 数据库结构
            
        Returns:
            True if 验证通过，False otherwise
        """
        if not field_description or not field_description.strip():
            # 没有字段描述，无法验证，默认通过
            return True
        
        # 获取数据库列注释
        column_comment = self._get_column_comment(
            db_schema,
            candidate.db_table,
            candidate.db_column
        )
        
        # 如果没有列注释，无法验证，默认通过
        if not column_comment or not column_comment.strip():
            return True
        
        # 计算字段描述和列注释的相似度
        similarity = self._calculate_text_similarity(field_description, column_comment)
        
        # 相似度大于阈值则通过
        threshold = 0.3  # 可调整的阈值
        return similarity >= threshold
    
    def _merge_candidates(
        self,
        rule_candidates: List[FieldMappingCandidate],
        ai_candidates: List[FieldMappingCandidate],
        field_description: Optional[str] = None,
        db_schema: Optional[Dict[str, Any]] = None
    ) -> List[FieldMappingCandidate]:
        """
        合并规则候选和AI候选
        
        Args:
            rule_candidates: 规则候选列表
            ai_candidates: AI候选列表
            field_description: 字段描述（可选）
            db_schema: 数据库结构（可选）
        """
        # 合并所有候选
        all_candidates = rule_candidates + ai_candidates
        
        # 按字段去重
        unique = {}
        for cand in all_candidates:
            key = f"{cand.db_table}.{cand.db_column}"
            if key not in unique:
                unique[key] = cand
            else:
                # 保留分数更高的
                if cand.score > unique[key].score:
                    unique[key] = cand
        
        # 使用字段描述进行验证（如果提供了描述和数据库结构）
        if field_description and db_schema:
            validated_candidates = []
            for cand in unique.values():
                # 验证候选是否通过描述验证
                if self._validate_candidate_with_description(
                    field_description,
                    cand,
                    db_schema
                ):
                    validated_candidates.append(cand)
                # 注意：未通过验证的候选将被过滤掉
            
            # 如果有通过验证的候选，使用它们；否则使用原始候选（降级策略）
            if validated_candidates:
                unique = {f"{c.db_table}.{c.db_column}": c for c in validated_candidates}
        
        # 按分数排序
        sorted_candidates = sorted(
            unique.values(),
            key=lambda x: x.score,
            reverse=True
        )
        
        # 只返回前10个
        return sorted_candidates[:10]
    
    def _calculate_statistics(
        self,
        field_registry: Dict[str, FieldInfo],
        categories: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """计算统计信息"""
        total_fields = len(field_registry)
        auto_confirmed = len(categories.get('auto_confirm', []))
        ai_high = len(categories.get('ai_high', []))
        ai_medium = len(categories.get('ai_medium', []))
        ai_low = len(categories.get('ai_low', []))
        
        # 统计置信度
        high_confidence = 0
        medium_confidence = 0
        low_confidence = 0
        
        for field_info in field_registry.values():
            if field_info.final_candidates:
                top_score = field_info.final_candidates[0].score
                if top_score >= 0.85:
                    high_confidence += 1
                elif top_score >= 0.60:
                    medium_confidence += 1
                else:
                    low_confidence += 1
        
        return {
            "total_fields": total_fields,
            "auto_confirmed": auto_confirmed,
            "ai_enhanced": ai_high + ai_medium + ai_low,
            "ai_high": ai_high,
            "ai_medium": ai_medium,
            "ai_low": ai_low,
            "high_confidence": high_confidence,
            "medium_confidence": medium_confidence,
            "low_confidence": low_confidence
        }


class PriorityAIQueue:
    """优先级AI队列"""
    
    def __init__(self):
        self.high_queue: List[AIRequest] = []
        self.medium_queue: List[AIRequest] = []
        self.low_queue: List[AIRequest] = []
        
        # 批处理配置
        self.batch_sizes = {
            'high': 5,
            'medium': 10,
            'low': 15
        }
    
    def enqueue(self, field_name: str, field_info: FieldInfo):
        """将字段加入相应优先级队列"""
        request = AIRequest(
            field_name=field_name,
            field_path=field_info.field_path,
            field_description=field_info.field_description,  # 传递字段描述
            rule_candidates=field_info.rule_candidates or [],
            api_context=field_info.apis[0] if field_info.apis else {}
        )
        
        if field_info.ai_priority == "high":
            self.high_queue.append(request)
        elif field_info.ai_priority == "medium":
            self.medium_queue.append(request)
        else:
            self.low_queue.append(request)
    
    def get_next_batch(self) -> Tuple[Optional[str], List[AIRequest]]:
        """获取下一批待处理的AI请求"""
        if self.high_queue:
            batch = self.high_queue[:self.batch_sizes['high']]
            self.high_queue = self.high_queue[self.batch_sizes['high']:]
            return 'high', batch
        
        if self.medium_queue:
            batch = self.medium_queue[:self.batch_sizes['medium']]
            self.medium_queue = self.medium_queue[self.batch_sizes['medium']:]
            return 'medium', batch
        
        if self.low_queue:
            batch = self.low_queue[:self.batch_sizes['low']]
            self.low_queue = self.low_queue[self.batch_sizes['low']:]
            return 'low', batch
        
        return None, []
    
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return not (self.high_queue or self.medium_queue or self.low_queue)
