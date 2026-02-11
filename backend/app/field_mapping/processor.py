"""字段映射处理器（异步任务处理）"""
import asyncio
import concurrent.futures
import logging
import re
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.base import ApiDefinition, DbSchemaVersion, ApiFieldMapping, User, AsyncTask
from app.api.v1.field_mappings import (
    _extract_api_fields,
    _generate_mapping_candidates,
    FieldMappingCandidate,
    FieldMappingSuggestion
)
from app.core.trace import get_trace_id
from app.ai.service import AIService

logger = logging.getLogger(__name__)


@dataclass
class FieldInfo:
    """字段信息"""
    field_name: str
    field_path: str
    source_type: str
    apis: List[Dict[str, Any]]
    total_count: int
    first_seen: str
    
    # 规则评分结果
    rule_candidates: List[FieldMappingCandidate] = None
    rule_top_score: float = 0.0
    
    # 筛选结果
    ai_priority: str = "none"
    screening_reasons: List[str] = None
    
    # AI结果
    ai_candidates: List[FieldMappingCandidate] = None
    final_candidates: List[FieldMappingCandidate] = None
    
    # 标记
    appears_in_multiple_apis: bool = False
    field_name_common: bool = False


@dataclass
class AIRequest:
    """AI请求"""
    field_name: str
    field_path: str
    rule_candidates: List[FieldMappingCandidate]
    api_context: Dict[str, Any]


@dataclass
class ScreeningResult:
    """筛选结果"""
    ai_priority: str
    reasons: List[str]
    action: str


class TaskCancelledException(Exception):
    """任务取消异常"""
    pass


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
        
        # 记录失败的字段
        self.failed_fields = set()
        self.retry_queue = []
        
        # 任务取消标志
        self._cancelled = False
    
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
        
    async def process(self) -> Dict[str, Any]:
        """
        处理字段映射建议任务
        
        Returns:
            处理结果
        """
        try:
            params = self.task.task_params
            project_id = params.get('project_id')
            version_id = params.get('version_id')
            
            logger.info(
                f"[{self.trace_id}] 开始处理字段映射任务: "
                f"project_id={project_id}, version_id={version_id}"
            )
            
            # 检查是否被取消
            self._raise_if_cancelled()
            
            # 初始化阶段列表
            stages = [
                {"name": "字段提取", "status": "pending", "progress": 0},
                {"name": "规则评分", "status": "pending", "progress": 0},
                {"name": "智能筛选", "status": "pending", "progress": 0},
                {"name": "AI优化", "status": "pending", "progress": 0},
                {"name": "结果合并", "status": "pending", "progress": 0}
            ]
            
            # 阶段1: 字段提取和去重
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
            
            # 更新初步统计信息
            self._update_statistics({"total_fields": len(field_registry)})
            
            # 阶段2: 规则评分
            self._raise_if_cancelled()
            self._update_stage_progress(stages, 1, "running", 0)
            self._update_progress(15, "正在进行规则评分...")
            db_schema = self._get_db_schema(project_id, version_id)
            rule_results = await self._batch_rule_scoring(
                field_registry, db_schema, stages
            )
            self._update_stage_progress(stages, 1, "completed", 100)
            
            # 阶段3: 智能筛选
            self._raise_if_cancelled()
            self._update_stage_progress(stages, 2, "running", 50)
            self._update_progress(40, "正在进行智能筛选...")
            categories = self._intelligent_screening(field_registry, rule_results)
            self._update_stage_progress(stages, 2, "completed", 100)
            
            # 更新分类统计
            self._update_statistics({
                "auto_confirmed": len(categories.get('auto_confirm', [])),
                "ai_high": len(categories.get('ai_high', [])),
                "ai_medium": len(categories.get('ai_medium', [])),
                "ai_low": len(categories.get('ai_low', []))
            })
            
            # 阶段4: AI调用
            self._raise_if_cancelled()
            if params.get('use_ai', True):
                self._update_stage_progress(stages, 3, "running", 0)
                self._update_progress(45, "正在进行AI优化...")
                ai_results = await self._priority_ai_calling(
                    field_registry, categories, stages
                )
                self._update_stage_progress(stages, 3, "completed", 100)
            else:
                ai_results = {}
                self._update_stage_progress(stages, 3, "completed", 100)
            
            # 阶段5: 结果合并
            self._raise_if_cancelled()
            self._update_stage_progress(stages, 4, "running", 50)
            self._update_progress(98, "正在合并结果...")
            suggestions = self._merge_results(field_registry, ai_results)
            self._update_stage_progress(stages, 4, "completed", 100)
            
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
        if not self.task.statistics:
            self.task.statistics = {}
        self.task.statistics.update(statistics)
        self.db.commit()
    
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
        
        Returns:
            字段注册表: {field_name: FieldInfo}
        """
        logger.info(f"[{self.trace_id}] 开始提取字段: "
                   f"project_id={project_id}, version_id={version_id}")
        
        field_registry: Dict[str, FieldInfo] = {}
        
        # 获取所有API定义
        definitions = self.db.query(ApiDefinition).filter(
            ApiDefinition.project_id == project_id
        ).all()
        
        logger.info(f"[{self.trace_id}] 找到 {len(definitions)} 个API定义")
        
        # 遍历所有API定义，提取字段
        for definition in definitions:
            api_fields = _extract_api_fields(
                definition, include_paths, include_query, include_body
            )
            
            for field_path in api_fields:
                # 解析字段路径
                source_type, field_name = self._parse_field_path(field_path)
                
                # 检查字段名是否已存在
                if field_name not in field_registry:
                    field_registry[field_name] = FieldInfo(
                        field_name=field_name,
                        field_path=field_path,
                        source_type=source_type,
                        apis=[],
                        total_count=0,
                        first_seen=f"{definition.method} {definition.path}"
                    )
                
                # 记录该字段出现的API
                field_registry[field_name].apis.append({
                    'definition_id': definition.id,
                    'method': definition.method,
                    'path': definition.path,
                    'field_path': field_path
                })
                field_registry[field_name].total_count += 1
        
        # 分析字段使用模式
        for field_name, field_info in field_registry.items():
            # 判断是否为多API共享字段
            field_info.appears_in_multiple_apis = field_info.total_count >= 3
            
            # 判断是否为通用字段名
            common_names = ['data', 'info', 'result', 'content', 'item']
            field_info.field_name_common = field_name in common_names
        
        total_fields = sum(len(f.apis) for f in field_registry.values())
        unique_fields = len(field_registry)
        
        logger.info(f"[{self.trace_id}] 字段提取完成: 原始{total_fields}个, "
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
                logger.info(f"[{self.trace_id}] 获取数据库结构成功: {len(schema_version.schema_snapshot)}个表")
                return schema_version.schema_snapshot
            else:
                logger.warning(f"[{self.trace_id}] 数据库结构版本存在但 schema_snapshot 为空: schema_version_id={schema_version.id}")
        else:
            logger.warning(f"[{self.trace_id}] 未找到数据库结构版本: project_id={project_id}, version_id={version_id}")

        return {}
    
    async def _batch_rule_scoring(
        self,
        field_registry: Dict[str, FieldInfo],
        db_schema: Dict[str, Any],
        stages: List[Dict[str, Any]]
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """
        批量规则评分
        
        Returns:
            评分结果: {field_name: [candidates]}
        """
        logger.info(f"[{self.trace_id}] 开始批量规则评分: "
                   f"{len(field_registry)}个字段")
        
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
                self._process_rule_scoring_batch_async(batch, db_schema, idx)
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
        
        logger.info(f"[{self.trace_id}] 批量规则评分完成")
        return all_results
    
    async def _process_rule_scoring_batch_async(
        self,
        batch: List[Tuple[str, FieldInfo]],
        db_schema: Dict[str, Any],
        batch_idx: int = 0
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """
        异步处理一批字段的规则评分
        
        Returns:
            评分结果: {field_name: [candidates]}
        """
        logger.info(f"[{self.trace_id}] 开始处理批次{batch_idx}: {len(batch)}个字段")
        results = {}
        
        for field_name, field_info in batch:
            try:
                # 从第一个出现该字段的API获取上下文
                first_api = field_info.apis[0]

                # 从 task_params 中获取 version_id
                version_id = self.task.task_params.get("version_id") if self.task.task_params else None

                # 生成候选映射（批处理阶段禁用AI，只使用规则评分）
                candidates = _generate_mapping_candidates(
                    self.db,
                    {"project_id": self.task.project_id, "version_id": version_id},
                    field_info.field_path,
                    first_api['method'],
                    first_api['path'],
                    db_schema,
                    use_ai=False  # 批处理阶段禁用AI调用
                )
                
                results[field_name] = candidates
            except Exception as e:
                logger.error(f"[{self.trace_id}] 字段{field_name}处理失败: {str(e)}")
                results[field_name] = []
        
        logger.info(f"[{self.trace_id}] 批次{batch_idx}处理完成: {len(results)}个字段有结果")
        return results

    def _process_rule_scoring_batch(
        self,
        batch: List[Tuple[str, FieldInfo]],
        db_schema: Dict[str, Any]
    ) -> Dict[str, List[FieldMappingCandidate]]:
        """
        处理一批字段的规则评分
        
        Returns:
            评分结果: {field_name: [candidates]}
        """
        results = {}
        
        for field_name, field_info in batch:
            # 从第一个出现该字段的API获取上下文
            first_api = field_info.apis[0]

            # 从 task_params 中获取 version_id
            version_id = self.task.task_params.get("version_id") if self.task.task_params else None

            # 生成候选映射
            candidates = _generate_mapping_candidates(
                self.db,
                {"project_id": self.task.project_id, "version_id": version_id},
                field_info.field_path,
                first_api['method'],
                first_api['path'],
                db_schema
            )

            results[field_name] = candidates

        return results

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
            screening_result = self._screen_field(field_name, field_info, rule_candidates)

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
            ai_priority = "medium"
            reasons.append("规则评分中等(0.60-0.85)，AI优化候选排序")
        else:
            ai_priority = "high"
            reasons.append("规则评分低(<0.60)，需要AI重新推荐")
        
        # === 第二级：候选数量筛选 ===
        candidate_count = len(rule_candidates)
        if candidate_count <= 1:
            ai_priority = "high"
            reasons.append(f"候选数量过少({candidate_count}个)，需要AI扩展")
        elif candidate_count >= 5:
            ai_priority = "high"
            reasons.append(f"候选数量过多({candidate_count}个)，需要AI筛选")
        elif candidate_count >= 3 and top_score < 0.70:
            ai_priority = "high"
            reasons.append("候选较多且置信度不足，需要AI重新排序")
        
        # === 第三级：字段类型筛选 ===
        if self._is_id_field(field_name):
            ai_priority = "high"
            reasons.append("ID类字段，需要AI精确匹配")
        
        if self._is_complex_nested(field_info.field_path):
            ai_priority = "high"
            reasons.append("复杂嵌套字段，需要AI深度分析")
        
        if self._is_array_field(field_info.field_path):
            ai_priority = "medium"
            reasons.append("数组字段，建议AI优化")
        
        # === 第四级：语义冲突筛选 ===
        if self._has_semantic_conflict(
            rule_candidates, 
            field_name, 
            field_info.apis[0]['path']
        ):
            ai_priority = "high"
            reasons.append("路径语义与候选表名冲突，需要AI纠正")
        
        # === 第五级：使用模式筛选 ===
        if field_info.appears_in_multiple_apis:
            if ai_priority == "none":
                ai_priority = "low"
            elif ai_priority == "medium":
                ai_priority = "medium"
            reasons.append(f"字段在{field_info.total_count}个API中使用，AI可学习模式")
        
        if field_info.field_name_common:
            if ai_priority == "none":
                ai_priority = "low"
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
    
    def _has_semantic_conflict(
        self,
        candidates: List[FieldMappingCandidate],
        field_name: str,
        api_path: str
    ) -> bool:
        """判断是否存在语义冲突"""
        if not candidates:
            return True
        
        top_candidate = candidates[0]
        top_table = top_candidate.db_table
        
        # 提取路径中的资源词
        path_segments = api_path.strip('/').split('/')
        path_resources = [seg for seg in path_segments 
                        if not seg.startswith('{') and len(seg) > 2]
        
        # 如果路径有明确资源，但候选表名不匹配
        if path_resources:
            has_better_match = False
            
            for candidate in candidates[1:]:
                for resource in path_resources:
                    if resource in candidate.db_table:
                        has_better_match = True
                        break
                if has_better_match:
                    break
            
            if has_better_match:
                return True
        
        return False
    
    async def _priority_ai_calling(
        self,
        field_registry: Dict[str, FieldInfo],
        categories: Dict[str, List[str]],
        stages: List[Dict[str, Any]]
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
                    "rule_candidates": [
                        {
                            "db_table": c.db_table,
                            "db_column": c.db_column,
                            "score": c.score,
                            "reasons": c.reasons
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

        # 尝试解析JSON
        import json
        if isinstance(result_data, str):
            logger.debug(f"[{self.trace_id}] AI返回字符串结果（前500字符）: {result_data[:500]}")

            # 尝试提取 markdown 代码块中的 JSON
            json_content = result_data
            if "```json" in result_data:
                # 提取 ```json ... ``` 之间的内容
                start = result_data.find("```json") + 7
                end = result_data.find("```", start)
                if end > start:
                    json_content = result_data[start:end].strip()
            elif "```" in result_data:
                # 提取 ``` ... ``` 之间的内容
                start = result_data.find("```") + 3
                end = result_data.find("```", start)
                if end > start:
                    json_content = result_data[start:end].strip()

            try:
                result_data = json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.error(f"[{self.trace_id}] AI返回格式错误，不是有效的JSON: {str(e)}")
                logger.error(f"[{self.trace_id}] 原始内容: {result_data[:500]}")
                return {req.field_name: req.rule_candidates for req in requests}

        # 检查解析后的数据格式
        if not isinstance(result_data, dict):
            logger.error(f"[{self.trace_id}] AI返回格式错误，期望dict，实际类型: {type(result_data)}")
            logger.error(f"[{self.trace_id}] 内容: {str(result_data)[:500]}")
            return {req.field_name: req.rule_candidates for req in requests}
        
        # 提取批量结果
        if isinstance(result_data, dict) and "field_mappings" in result_data:
            logger.info(f"[{self.trace_id}] AI返回包含 {len(result_data['field_mappings'])} 个字段映射结果")
            for mapping_result in result_data["field_mappings"]:
                field_name = mapping_result.get("field_name")
                ai_candidates = mapping_result.get("candidates", [])

                logger.debug(f"[{self.trace_id}] 处理字段 {field_name}: {len(ai_candidates)} 个候选")

                # 转换为FieldMappingCandidate
                candidates = []
                for cand in ai_candidates:
                    candidates.append(FieldMappingCandidate(
                        db_table=cand.get("db_table", ""),
                        db_column=cand.get("db_column", ""),
                        score=cand.get("confidence", 0.0),
                        reasons=cand.get("reasons", [])
                    ))

                results[field_name] = candidates if candidates else []
        else:
            logger.error(f"[{self.trace_id}] AI返回格式错误，缺少 field_mappings 字段，实际键: {list(result_data.keys()) if isinstance(result_data, dict) else 'N/A'}")

        return results
    
    def _merge_results(
        self,
        field_registry: Dict[str, FieldInfo],
        ai_results: Dict[str, List[FieldMappingCandidate]]
    ) -> List[FieldMappingSuggestion]:
        """
        合并规则结果和AI结果
        
        Returns:
            最终建议列表
        """
        logger.info(f"[{self.trace_id}] 开始合并结果")
        
        suggestions = []
        
        for field_name, field_info in field_registry.items():
            ai_candidates = ai_results.get(field_name, [])
            rule_candidates = field_info.rule_candidates or []  # 确保 rule_candidates 不为 None
            
            # 合并策略
            if field_info.ai_priority == "none":
                final_candidates = rule_candidates
            elif ai_candidates:
                merged = self._merge_candidates(rule_candidates, ai_candidates)
                final_candidates = merged
            else:
                final_candidates = rule_candidates
            
            # 为每个API生成建议
            for api_ref in field_info.apis:
                suggestion = FieldMappingSuggestion(
                    definition_id=api_ref['definition_id'],
                    definition_method=api_ref['method'],
                    definition_path=api_ref['path'],
                    api_field_path=api_ref['field_path'],
                    candidates=final_candidates
                )
                suggestions.append(suggestion)
        
        logger.info(f"[{self.trace_id}] 结果合并完成: {len(suggestions)}个建议")
        return suggestions
    
    def _merge_candidates(
        self,
        rule_candidates: List[FieldMappingCandidate],
        ai_candidates: List[FieldMappingCandidate]
    ) -> List[FieldMappingCandidate]:
        """合并规则候选和AI候选"""
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