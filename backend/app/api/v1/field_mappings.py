"""API 字段映射管理接口（V2.0 - 版本中心）"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging
import json
import concurrent.futures

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.db.base import ApiFieldMapping, ApiDefinition, Version, User, DbSchemaVersion
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.utils.field_mapping_utils import (
    extract_path_params, 
    parse_path_segments, 
    calculate_mapping_score,
    normalize_field_name,
    tokenize_field,
    field_similarity_score,
    table_similarity_score
)

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


class FieldMappingCreate(BaseModel):
    """创建字段映射"""
    definition_id: int = Field(..., description="API 定义ID")
    api_field_path: str = Field(..., description="API 字段路径，如 body.order_id")
    db_table: str = Field(..., description="数据库表名")
    db_column: str = Field(..., description="数据库字段名")
    relation_type: Optional[str] = Field("direct", description="关系类型：direct/fk/derived")
    confidence: Optional[float] = Field(None, description="映射置信度")
    source: Optional[str] = Field("manual", description="来源：manual/ai")


class FieldMappingUpdate(BaseModel):
    """更新字段映射"""
    api_field_path: Optional[str] = Field(None, description="API 字段路径")
    db_table: Optional[str] = Field(None, description="数据库表名")
    db_column: Optional[str] = Field(None, description="数据库字段名")
    relation_type: Optional[str] = Field(None, description="关系类型")
    confidence: Optional[float] = Field(None, description="映射置信度")
    source: Optional[str] = Field(None, description="来源")


class FieldMappingSuggestRequest(BaseModel):
    """字段映射建议请求"""
    include_paths: Optional[bool] = Field(True, description="是否包含路径参数")
    include_query: Optional[bool] = Field(True, description="是否包含查询参数")
    include_body: Optional[bool] = Field(True, description="是否包含请求体参数")


class FieldMappingCandidate(BaseModel):
    """字段映射候选"""
    db_table: str = Field(..., description="数据库表名")
    db_column: str = Field(..., description="数据库字段名")
    score: float = Field(..., description="匹配分数", ge=0.0, le=1.0)
    reasons: List[str] = Field(..., description="匹配原因")


class FieldMappingSuggestion(BaseModel):
    """字段映射建议"""
    definition_id: int = Field(..., description="API 定义ID")
    definition_method: str = Field(..., description="API 方法")
    definition_path: str = Field(..., description="API 路径")
    api_field_path: str = Field(..., description="API 字段路径")
    candidates: List[FieldMappingCandidate] = Field(..., description="候选映射列表")


class FieldMappingBatchApplyItem(BaseModel):
    """批量应用映射项"""
    definition_id: int = Field(..., description="API 定义ID")
    api_field_path: str = Field(..., description="API 字段路径")
    db_table: str = Field(..., description="数据库表名")
    db_column: str = Field(..., description="数据库字段名")
    relation_type: Optional[str] = Field("direct", description="关系类型")
    source: Optional[str] = Field("ai", description="来源")


class FieldMappingBatchApplyRequest(BaseModel):
    """批量应用映射请求"""
    items: List[FieldMappingBatchApplyItem] = Field(..., description="映射项列表")
    mode: str = Field("propose", description="模式：propose(建议)/confirm(确认)")


def _get_project_and_version(
    db: Session,
    current_user: User,
    project_id: Optional[int],
    version_id: Optional[int]
) -> Dict[str, int]:
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    if version_id is None:
        version_id = get_current_version_id(db, current_user)

    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择项目"
        )
    if not version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择版本"
        )

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本不存在：{version_id}"
        )
    if version.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该版本"
        )

    return {"project_id": project_id, "version_id": version_id}


def _get_db_schema_for_project(db: Session, project_id: int, version_id: int) -> Dict[str, Any]:
    """
    获取项目当前版本的数据库结构
    """
    # 尝试从 DbSchemaVersion 获取数据库结构
    schema_version = db.query(DbSchemaVersion).filter(
        DbSchemaVersion.project_id == project_id,
        DbSchemaVersion.version_id == version_id
    ).first()
    
    if schema_version and schema_version.schema_snapshot:
        return schema_version.schema_snapshot
    else:
        # 如果没有找到，返回空结构
        return {}


def _generate_mapping_candidates(
    db: Session,
    ctx: Dict[str, int],
    api_field_path: str,
    api_method: str,
    api_path: str,
    schema_snapshot: Dict[str, Any],
    use_ai: bool = False
) -> List[FieldMappingCandidate]:
    """
    生成字段映射候选列表
    结合规则评分和AI推荐（如果AI服务可用）

    Args:
        use_ai: 是否使用AI推荐，默认False（批处理阶段禁用AI）
    """
    # 获取API字段名（去掉路径前缀，如 body., query., path.）
    api_field_name = api_field_path.split('.')[-1]

    # 获取数据库结构
    db_schema = _get_db_schema_for_project(db, ctx["project_id"], ctx["version_id"])
    logger.debug(f"生成映射候选: api_field={api_field_name}, db_schema={len(db_schema) if db_schema else 0}个表")

    # 获取项目字段字典
    from sqlalchemy import func
    field_dict_query = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "confirmed"
    ).all()
    
    field_dictionary = {}
    for mapping in field_dict_query:
        field_name = mapping.api_field_path.split('.')[-1]  # 获取字段名部分
        key = field_name.lower()
        
        if key not in field_dictionary:
            field_dictionary[key] = {
                "field_name": field_name,
                "db_table": mapping.db_table,
                "db_column": mapping.db_column,
                "count": 1
            }
        else:
            field_dictionary[key]["count"] += 1
    
    # 首先使用规则评分生成候选
    rule_candidates = []

    if db_schema and isinstance(db_schema, dict):
        # 处理两种格式的数据库结构：
        # 1. 字典格式: {table_name: {columns: [...], ...}}
        # 2. 列表格式: {tables: [{name: ..., columns: [...]}, ...]}

        # 检查是否是列表格式（SQL解析器返回的格式）
        if "tables" in db_schema and isinstance(db_schema["tables"], list):
            # 使用列表格式
            for table_info in db_schema["tables"]:
                if isinstance(table_info, dict):
                    table_name = table_info.get("name", "")
                    columns = table_info.get("columns", [])
                    for column_info in columns:
                        if isinstance(column_info, dict):
                            column_name = column_info.get("name", "")
                            is_primary_key = column_info.get("primary_key", False)
                            type_compatible = True

                            scores = calculate_mapping_score(
                                api_field=api_field_name,
                                db_column=column_name,
                                db_table=table_name,
                                path=api_path,
                                is_primary_key=is_primary_key,
                                type_compatible=type_compatible
                            )

                            score = scores["total_score"]

                            if score > 0.3:
                                reasons = []
                                if scores["field_score"] > 0.1:
                                    reasons.append("字段名匹配")
                                if scores["table_score"] > 0.1:
                                    reasons.append("表名匹配")
                                if scores["path_score"] > 0.05:
                                    reasons.append("路径语义匹配")
                                if scores["pk_score"] > 0.05:
                                    reasons.append("主键优先")
                                if scores["type_score"] > 0.02:
                                    reasons.append("类型匹配")

                                rule_candidates.append(FieldMappingCandidate(
                                    db_table=table_name,
                                    db_column=column_name,
                                    score=score,
                                    reasons=reasons
                                ))
        else:
            # 使用字典格式（旧格式）
            for table_name, table_info in db_schema.items():
                if isinstance(table_info, dict) and "columns" in table_info:
                    for column_info in table_info["columns"]:
                        if isinstance(column_info, dict):
                            column_name = column_info.get("name", "")

                            # 计算映射评分
                            is_primary_key = column_info.get("is_primary_key", False)
                            type_compatible = True  # 简化处理

                            scores = calculate_mapping_score(
                                api_field=api_field_name,
                                db_column=column_name,
                                db_table=table_name,
                                path=api_path,
                                is_primary_key=is_primary_key,
                                type_compatible=type_compatible
                            )

                            score = scores["total_score"]

                            # 只保留分数大于0.3的候选
                            if score > 0.3:
                                reasons = []
                                if scores["field_score"] > 0.1:
                                    reasons.append("字段名匹配")
                                if scores["table_score"] > 0.1:
                                    reasons.append("表名匹配")
                                if scores["path_score"] > 0.05:
                                    reasons.append("路径语义匹配")
                                if scores["pk_score"] > 0.05:
                                    reasons.append("主键优先")
                                if scores["type_score"] > 0.02:
                                    reasons.append("类型匹配")

                                rule_candidates.append(FieldMappingCandidate(
                                    db_table=table_name,
                                    db_column=column_name,
                                    score=score,
                                    reasons=reasons
                                ))
    
    # 按分数降序排列
    rule_candidates.sort(key=lambda x: x.score, reverse=True)
    
    # 只返回前10个规则评分候选，为AI推荐留出空间
    final_candidates = rule_candidates[:10]
    
    # 只在明确启用AI时才调用AI（批处理阶段禁用）
    if use_ai:
        try:
            # 检查AI服务是否可用并调用
            from app.ai.service import AIService
            
            # 准备AI输入数据
            ai_input = {
                "api_field_path": api_field_path,
                "method": api_method,
                "path": api_path,
                "summary": "",  # 在这里可以添加API摘要
                "schema_snapshot": db_schema,
                "field_dictionary": field_dictionary
            }
            
            # 创建AI服务实例
            ai_service = AIService()
            
            # 使用现有事件循环调用AI服务（避免创建新的事件循环）
            import asyncio
            try:
                # 尝试获取当前事件循环
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用create_task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            ai_service.execute(
                                task_type="field_mapping_recommendation",
                                project_id=ctx["project_id"],
                                input_data=ai_input
                            )
                        )
                        ai_result = future.result(timeout=30)  # 设置30秒超时
                else:
                    # 如果事件循环未运行，直接使用asyncio.run
                    ai_result = asyncio.run(
                        ai_service.execute(
                            task_type="field_mapping_recommendation",
                            project_id=ctx["project_id"],
                            input_data=ai_input
                        )
                    )
            except RuntimeError:
                # 如果获取事件循环失败，回退到线程池执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        ai_service.execute(
                            task_type="field_mapping_recommendation",
                            project_id=ctx["project_id"],
                            input_data=ai_input
                        )
                    )
                    ai_result = future.result(timeout=30)  # 设置30秒超时
            
            ai_candidates = []
            if ai_result.get("success"):
                result_data = ai_result.get("result")
                if isinstance(result_data, str):
                    try:
                        result_data = json.loads(result_data)
                    except json.JSONDecodeError:
                        logger.warning(f"AI结果JSON解析失败: {result_data[:200]}...")
                        result_data = {}
                
                if isinstance(result_data, dict) and "candidates" in result_data:
                    for candidate in result_data["candidates"]:
                        if isinstance(candidate, dict):
                            ai_candidates.append(FieldMappingCandidate(
                                db_table=candidate.get("db_table", ""),
                                db_column=candidate.get("db_column", ""),
                                score=candidate.get("confidence", 0.0),
                                reasons=candidate.get("reasons", [])
                            ))
            
            # 合并AI候选和规则候选
            all_candidates = final_candidates + ai_candidates
            
            # 按分数去重并排序
            unique_candidates = {}
            for candidate in all_candidates:
                key = f"{candidate.db_table}.{candidate.db_column}"
                if key not in unique_candidates or unique_candidates[key].score < candidate.score:
                    unique_candidates[key] = candidate
            
            # 返回前10个最佳候选
            result = sorted(unique_candidates.values(), key=lambda x: x.score, reverse=True)
            return result[:10]
        
        except ImportError as e:
            # 如果AI模块不可用，只返回规则评分的候选
            logger.warning(f"AI 模块导入失败: {str(e)}")
            return final_candidates
        except concurrent.futures.TimeoutError:
            # 如果AI调用超时，只返回规则评分的候选
            logger.warning(f"AI 服务调用超时，使用规则生成候选: api_field_path={api_field_path}")
            return final_candidates
        except Exception as e:
            logger.warning(f"AI 服务调用异常，使用规则生成候选: api_field_path={api_field_path}, error={str(e)}")
            return final_candidates
    
    # 如果不使用AI，直接返回规则评分结果
    return final_candidates


def _extract_api_fields(definition: ApiDefinition, include_paths: bool = True, include_query: bool = True, include_body: bool = True) -> List[str]:
    """
    从API定义中提取待映射字段
    修复报错.md中提到的问题：
    1. schema_snapshot 结构不统一
    2. request_schema 与 parameters 存储位置不一致
    3. 过滤逻辑无效
    4. array 递归字段路径问题
    """
    fields = []
    
    # 提取路径参数
    if include_paths:
        path_params = extract_path_params(definition.path)
        for param in path_params:
            fields.append(f"path.{param}")
    
    # 检查 definition.schema_snapshot 结构
    schema_snapshot = definition.schema_snapshot
    if schema_snapshot:
        if isinstance(schema_snapshot, str):
            try:
                schema_snapshot = json.loads(schema_snapshot)
            except:
                schema_snapshot = {}
        
        if isinstance(schema_snapshot, dict):
            # 情况1: 直接在 schema_snapshot 顶层有 parameters
            if include_query and 'parameters' in schema_snapshot:
                for param in schema_snapshot.get('parameters', []):
                    if param.get('in') == 'query':
                        fields.append(f"query.{param.get('name')}")
            
            # 情况2: 在 schema_snapshot.request_schema 中
            request_schema = schema_snapshot.get('request_schema')
            if not request_schema and hasattr(definition, 'request_schema') and definition.request_schema:
                # 备用：直接从 definition.request_schema 获取
                request_schema = definition.request_schema
                if isinstance(request_schema, str):
                    try:
                        request_schema = json.loads(request_schema)
                    except:
                        request_schema = {}
            
            if request_schema and isinstance(request_schema, dict):
                # 检查是否是YApi结构：{"type": "json", "schema": {...}}
                if 'type' in request_schema and 'schema' in request_schema:
                    actual_schema = request_schema.get('schema', {})
                    if isinstance(actual_schema, dict) and 'properties' in actual_schema:
                        for prop_name in actual_schema['properties'].keys():
                            fields.append(f"body.{prop_name}")
                # 检查是否有properties字段
                elif 'properties' in request_schema:
                    for prop_name in request_schema['properties'].keys():
                        fields.append(f"body.{prop_name}")
                # 检查是否是其他结构
                else:
                    # 递归查找properties
                    def find_properties_recursive(obj, prefix="body"):
                        found_fields = []
                        if isinstance(obj, dict):
                            if 'properties' in obj:
                                for prop_name in obj['properties'].keys():
                                    found_fields.append(f"{prefix}.{prop_name}")
                            else:
                                # 递归检查子对象
                                for key, value in obj.items():
                                    if isinstance(value, dict):
                                        found_fields.extend(find_properties_recursive(value, f"{prefix}.{key}"))
                        return found_fields
                    
                    fields.extend(find_properties_recursive(request_schema))
            
            # 情况3: 从 schema_snapshot.parameters 提取
            if include_query:
                # 检查 schema_snapshot 顶层的 parameters
                for param in schema_snapshot.get('parameters', []):
                    if param.get('in') == 'query':
                        fields.append(f"query.{param.get('name')}")
    
    # 最后，保留所有字段，但按规则过滤（去重）
    # 修复报错.md中提到的过滤逻辑问题
    result_fields = []
    for field in fields:
        if field not in result_fields:  # 防止重复添加
            result_fields.append(field)
    
    return result_fields


@router.post("/field-mappings", response_model=ApiResponse)
async def create_field_mapping(
    request: FieldMappingCreate,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建 API 字段映射
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    definition = db.query(ApiDefinition).filter(ApiDefinition.id == request.definition_id).first()
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{request.definition_id}"
        )
    if definition.project_id != ctx["project_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该 API 定义"
        )

    logger.info(
        f"[{trace_id}] 创建字段映射: project_id={ctx['project_id']}, version_id={ctx['version_id']}, "
        f"definition_id={request.definition_id}, api_field_path={request.api_field_path}"
    )

    mapping = ApiFieldMapping(
        project_id=ctx["project_id"],
        version_id=ctx["version_id"],
        definition_id=request.definition_id,
        api_field_path=request.api_field_path,
        db_table=request.db_table,
        db_column=request.db_column,
        relation_type=request.relation_type or "direct",
        confidence=request.confidence,
        source=request.source or "manual",
        created_by=current_user.id,
        updated_by=current_user.id
    )

    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return ApiResponse(
        code=0,
        message="创建成功",
        data={"id": mapping.id}
    )


from fastapi import Body  # 在文件顶部导入 Body

@router.post("/field-mappings/suggest", response_model=ApiResponse)
async def suggest_field_mappings(
    request: FieldMappingSuggestRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    生成字段映射建议
    """
    
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(
        f"[{trace_id}] 生成字段映射建议: project_id={ctx['project_id']}, version_id={ctx['version_id']}, "
        f"include_paths={request.include_paths}, include_query={request.include_query}, include_body={request.include_body}"
    )

    # 获取项目中的所有API定义
    definitions = db.query(ApiDefinition).filter(
        ApiDefinition.project_id == ctx["project_id"]
    ).all()

    suggestions = []
    
    for definition in definitions:
        # 提取API字段
        api_fields = _extract_api_fields(
            definition, 
            request.include_paths, 
            request.include_query, 
            request.include_body
        )
        
        for api_field_path in api_fields:
            # 生成候选映射
            candidates = _generate_mapping_candidates(
                db, 
                ctx, 
                api_field_path, 
                definition.method, 
                definition.path, 
                definition.schema_snapshot or {}
            )
            
            if candidates:  # 只有在有候选时才添加建议
                suggestion = FieldMappingSuggestion(
                    definition_id=definition.id,
                    definition_method=definition.method,
                    definition_path=definition.path,
                    api_field_path=api_field_path,
                    candidates=candidates
                )
                suggestions.append(suggestion)

    return ApiResponse(
        code=0,
        message="生成建议成功",
        data={"items": [suggestion.model_dump() for suggestion in suggestions]}
    )


@router.post("/field-mappings/batch-apply", response_model=ApiResponse)
async def batch_apply_field_mappings(
    request: FieldMappingBatchApplyRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量应用字段映射
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(
        f"[{trace_id}] 批量应用字段映射: project_id={ctx['project_id']}, version_id={ctx['version_id']}, "
        f"items_count={len(request.items)}, mode={request.mode}"
    )

    created_count = 0
    for item in request.items:
        # 验证API定义存在性
        definition = db.query(ApiDefinition).filter(
            ApiDefinition.id == item.definition_id,
            ApiDefinition.project_id == ctx["project_id"]
        ).first()
        
        if not definition:
            logger.warning(f"[{trace_id}] API定义不存在或无权限: {item.definition_id}")
            continue
        
        # 检查是否已存在相同的映射
        existing = db.query(ApiFieldMapping).filter(
            ApiFieldMapping.project_id == ctx["project_id"],
            ApiFieldMapping.version_id == ctx["version_id"],
            ApiFieldMapping.definition_id == item.definition_id,
            ApiFieldMapping.api_field_path == item.api_field_path,
            ApiFieldMapping.db_table == item.db_table,
            ApiFieldMapping.db_column == item.db_column
        ).first()
        
        if existing:
            # 如果已存在，更新状态和置信度
            existing.relation_type = item.relation_type
            existing.source = item.source
            existing.updated_by = current_user.id
        else:
            # 创建新的映射
            mapping = ApiFieldMapping(
                project_id=ctx["project_id"],
                version_id=ctx["version_id"],
                definition_id=item.definition_id,
                api_field_path=item.api_field_path,
                db_table=item.db_table,
                db_column=item.db_column,
                relation_type=item.relation_type,
                source=item.source,
                status="confirmed" if request.mode == "confirm" else "proposed",
                created_by=current_user.id,
                updated_by=current_user.id
            )
            db.add(mapping)
        
        created_count += 1

    db.commit()

    return ApiResponse(
        code=0,
        message=f"批量应用成功，处理了 {created_count} 个映射",
        data={"processed_count": created_count}
    )


@router.put("/field-mappings/{mapping_id}/status", response_model=ApiResponse)
async def update_field_mapping_status(
    mapping_id: int,
    status: str = Query(..., description="新状态：confirmed/rejected"),
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新字段映射状态
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    mapping = db.query(ApiFieldMapping).filter(ApiFieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"字段映射不存在：{mapping_id}"
        )
    if mapping.project_id != ctx["project_id"] or mapping.version_id != ctx["version_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该字段映射"
        )

    # 验证状态值
    if status not in ["proposed", "confirmed", "rejected"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的状态值，必须是：proposed/confirmed/rejected"
        )

    mapping.status = status
    mapping.updated_by = current_user.id

    db.commit()

    logger.info(f"[{trace_id}] 更新字段映射状态: id={mapping_id}, status={status}")

    return ApiResponse(
        code=0,
        message="更新状态成功",
        data={"id": mapping_id, "status": status}
    )


@router.get("/field-mappings/pending", response_model=ApiResponse)
async def get_pending_field_mappings(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取待审核的字段映射（状态为proposed）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询待审核字段映射: project_id={ctx['project_id']}, version_id={ctx['version_id']}")

    mappings = db.query(ApiFieldMapping, ApiDefinition).join(
        ApiDefinition, ApiDefinition.id == ApiFieldMapping.definition_id
    ).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.version_id == ctx["version_id"],
        ApiFieldMapping.status == "proposed"
    ).order_by(ApiFieldMapping.created_at.desc()).all()

    items = []
    for mapping, definition in mappings:
        items.append({
            "id": mapping.id,
            "project_id": mapping.project_id,
            "version_id": mapping.version_id,
            "definition_id": mapping.definition_id,
            "definition_method": definition.method,
            "definition_path": definition.path,
            "api_field_path": mapping.api_field_path,
            "db_table": mapping.db_table,
            "db_column": mapping.db_column,
            "relation_type": mapping.relation_type,
            "confidence": mapping.confidence,
            "source": mapping.source,
            "status": mapping.status,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else "",
            "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else ""
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={"items": items, "total": len(items)}
    )


@router.post("/field-mappings/clone", response_model=ApiResponse)
async def clone_field_mappings(
    from_version_id: int = Query(..., description="源版本ID"),
    to_version_id: int = Query(..., description="目标版本ID"),
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从指定版本克隆字段映射到当前版本
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, to_version_id)

    logger.info(
        f"[{trace_id}] 克隆字段映射: project_id={ctx['project_id']}, "
        f"from_version_id={from_version_id}, to_version_id={ctx['version_id']}"
    )

    # 验证源版本是否存在且属于同一项目
    from_version = db.query(Version).filter(Version.id == from_version_id).first()
    if not from_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"源版本不存在：{from_version_id}"
        )
    if from_version.project_id != ctx["project_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="源版本不属于当前项目"
        )

    # 查询源版本的字段映射
    from_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.version_id == from_version_id
    ).all()

    cloned_count = 0
    for mapping in from_mappings:
        # 检查目标版本是否已存在相同的映射
        existing = db.query(ApiFieldMapping).filter(
            ApiFieldMapping.project_id == ctx["project_id"],
            ApiFieldMapping.version_id == ctx["version_id"],
            ApiFieldMapping.definition_id == mapping.definition_id,
            ApiFieldMapping.api_field_path == mapping.api_field_path,
            ApiFieldMapping.db_table == mapping.db_table,
            ApiFieldMapping.db_column == mapping.db_column
        ).first()

        if not existing:
            # 创建新的映射记录
            new_mapping = ApiFieldMapping(
                project_id=ctx["project_id"],
                version_id=ctx["version_id"],
                definition_id=mapping.definition_id,
                api_field_path=mapping.api_field_path,
                db_table=mapping.db_table,
                db_column=mapping.db_column,
                relation_type=mapping.relation_type,
                confidence=mapping.confidence,
                source=mapping.source,
                status=mapping.status,  # 保持原始状态
                created_by=current_user.id,
                updated_by=current_user.id
            )
            db.add(new_mapping)
            cloned_count += 1

    db.commit()

    return ApiResponse(
        code=0,
        message=f"成功克隆了 {cloned_count} 个字段映射",
        data={"cloned_count": cloned_count}
    )


class ProjectFieldDictionary(BaseModel):
    """项目字段字典项"""
    field_name: str = Field(..., description="字段名")
    db_table: str = Field(..., description="推荐的数据库表")
    db_column: str = Field(..., description="推荐的数据库字段")
    priority: int = Field(1, description="优先级")


@router.get("/field-mappings/dictionary", response_model=ApiResponse)
async def get_field_dictionary(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目字段字典（基于已确认的映射生成）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询项目字段字典: project_id={ctx['project_id']}")

    # 从已确认的映射中提取字段字典
    confirmed_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "confirmed"
    ).all()

    # 按字段名分组，取最常见的映射作为字典项
    field_dict = {}
    for mapping in confirmed_mappings:
        field_name = mapping.api_field_path.split('.')[-1]  # 获取字段名部分
        key = field_name.lower()
        
        if key not in field_dict:
            field_dict[key] = {
                "field_name": field_name,
                "db_table": mapping.db_table,
                "db_column": mapping.db_column,
                "priority": 1,
                "count": 1
            }
        else:
            # 如果发现不同的映射，增加计数并保留置信度最高的
            field_dict[key]["count"] += 1
            if mapping.confidence and mapping.confidence > field_dict[key].get("max_confidence", 0):
                field_dict[key]["db_table"] = mapping.db_table
                field_dict[key]["db_column"] = mapping.db_column
                field_dict[key]["max_confidence"] = mapping.confidence

    # 转换为字典列表
    result = []
    for item in field_dict.values():
        result.append({
            "field_name": item["field_name"],
            "db_table": item["db_table"],
            "db_column": item["db_column"],
            "priority": item.get("max_confidence", item["count"])  # 使用置信度或计数作为优先级
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={"items": result, "total": len(result)}
    )


@router.post("/field-mappings/auto-apply", response_model=ApiResponse)
async def auto_apply_field_mappings(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    min_confidence: float = Query(0.85, description="最低置信度阈值"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    自动应用高置信度的映射建议
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(
        f"[{trace_id}] 自动应用高置信度映射: project_id={ctx['project_id']}, "
        f"version_id={ctx['version_id']}, min_confidence={min_confidence}"
    )

    # 查询置信度高于阈值且状态为proposed的映射
    high_confidence_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.version_id == ctx["version_id"],
        ApiFieldMapping.status == "proposed",
        ApiFieldMapping.confidence >= min_confidence
    ).all()

    updated_count = 0
    for mapping in high_confidence_mappings:
        mapping.status = "confirmed"
        mapping.updated_by = current_user.id
        updated_count += 1

    db.commit()

    return ApiResponse(
        code=0,
        message=f"成功自动应用了 {updated_count} 个高置信度映射",
        data={"updated_count": updated_count}
    )


@router.get("/field-mappings/learning-stats", response_model=ApiResponse)
async def get_learning_stats(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取学习统计信息（基于历史确认映射）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询学习统计: project_id={ctx['project_id']}")

    # 统计不同类型映射的数量
    total_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"]
    ).count()
    
    confirmed_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "confirmed"
    ).count()
    
    proposed_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "proposed"
    ).count()
    
    rejected_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "rejected"
    ).count()
    
    # 计算平均置信度
    avg_confidence_result = db.query(func.avg(ApiFieldMapping.confidence)).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.confidence.isnot(None)
    ).scalar()
    
    avg_confidence = float(avg_confidence_result) if avg_confidence_result else 0.0

    # 统计AI vs 手动创建的映射
    ai_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.source == "ai"
    ).count()
    
    manual_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.source == "manual"
    ).count()

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total_mappings": total_mappings,
            "confirmed_mappings": confirmed_mappings,
            "proposed_mappings": proposed_mappings,
            "rejected_mappings": rejected_mappings,
            "avg_confidence": round(avg_confidence, 3),
            "ai_mappings": ai_mappings,
            "manual_mappings": manual_mappings
        }
    )


@router.get("/field-mappings", response_model=ApiResponse)
async def list_field_mappings(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    definition_id: Optional[int] = Query(None, description="API 定义ID过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取字段映射列表（当前版本）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询字段映射列表: project_id={ctx['project_id']}, version_id={ctx['version_id']}")

    query = db.query(ApiFieldMapping, ApiDefinition).join(
        ApiDefinition, ApiDefinition.id == ApiFieldMapping.definition_id
    ).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.version_id == ctx["version_id"]
    )

    if definition_id:
        query = query.filter(ApiFieldMapping.definition_id == definition_id)

    total = query.count()
    rows = query.order_by(ApiFieldMapping.updated_at.desc()).all()

    items: List[Dict[str, Any]] = []
    for mapping, definition in rows:
        items.append({
            "id": mapping.id,
            "project_id": mapping.project_id,
            "version_id": mapping.version_id,
            "definition_id": mapping.definition_id,
            "definition_method": definition.method,
            "definition_path": definition.path,
            "api_field_path": mapping.api_field_path,
            "db_table": mapping.db_table,
            "db_column": mapping.db_column,
            "relation_type": mapping.relation_type,
            "confidence": mapping.confidence,
            "source": mapping.source,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else "",
            "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else ""
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={"total": total, "items": items}
    )


@router.put("/field-mappings/{mapping_id}", response_model=ApiResponse)
async def update_field_mapping(
    mapping_id: int,
    request: FieldMappingUpdate,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新字段映射
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    mapping = db.query(ApiFieldMapping).filter(ApiFieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"字段映射不存在：{mapping_id}"
        )
    if mapping.project_id != ctx["project_id"] or mapping.version_id != ctx["version_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该字段映射"
        )

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(mapping, key, value)
    mapping.updated_by = current_user.id

    db.commit()

    logger.info(f"[{trace_id}] 更新字段映射: id={mapping_id}")

    return ApiResponse(
        code=0,
        message="更新成功",
        data={"id": mapping_id}
    )


@router.delete("/field-mappings/{mapping_id}", response_model=ApiResponse)
async def delete_field_mapping(
    mapping_id: int,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除字段映射
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    mapping = db.query(ApiFieldMapping).filter(ApiFieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"字段映射不存在：{mapping_id}"
        )
    if mapping.project_id != ctx["project_id"] or mapping.version_id != ctx["version_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该字段映射"
        )

    db.delete(mapping)
    db.commit()

    logger.info(f"[{trace_id}] 删除字段映射: id={mapping_id}")

    return ApiResponse(
        code=0,
        message="删除成功"
    )
