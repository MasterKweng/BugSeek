"""
完整追踪从解析文档到存入数据库再到查询的数据流
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine, get_db
from app.parsers import ParserFactory
from app.core.sync.change_detector import ChangeDetector
from app.db.base import ApiDefinition, SyncTask
import logging
import json
import requests
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_section(title, data, indent=0):
    """打印数据块"""
    prefix = "  " * indent
    logger.info(f"{prefix}{'='*60}")
    logger.info(f"{prefix}{title}")
    logger.info(f"{prefix}{'='*60}")
    if isinstance(data, (dict, list)):
        logger.info(f"{prefix}{json.dumps(data, indent=2, ensure_ascii=False)[:2000]}")
    else:
        logger.info(f"{prefix}{data}")


def trace_full_data_flow():
    """完整追踪数据流"""
    trace_id = f"trace_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 开始完整数据流追踪")
        
        # ========== 步骤1: 获取并解析文档 ==========
        # 使用Petstore的OpenAPI文档作为测试
        source_url = "https://petstore.swagger.io/v2/swagger.json"
        source_type = "swagger"
        
        logger.info(f"\n[{trace_id}] 步骤1: 获取并解析文档")
        logger.info(f"[{trace_id}] 源URL: {source_url}")
        
        # 获取文档内容
        response = requests.get(source_url, timeout=30)
        
        # 检查是否是HTML页面
        if '<!DOCTYPE html>' in response.text:
            logger.info(f"[{trace_id}] 检测到HTML页面，尝试提取JSON URL")
            patterns = [
                r'url:\s*[\'"]([^\'"]+\.json)[\'"]',
                r'spec:\s*[\'"]([^\'"]+\.json)[\'"]',
            ]
            for pattern in patterns:
                match = re.search(pattern, response.text)
                if match:
                    json_url = match.group(1)
                    if json_url.startswith('/'):
                        source_url = f"http://127.0.0.1:1337{json_url}"
                    else:
                        source_url = json_url
                    logger.info(f"[{trace_id}] 提取到JSON URL: {source_url}")
                    response = requests.get(source_url, timeout=30)
                    break
        
        response.raise_for_status()
        content = response.text
        
        # 解析文档
        parser = ParserFactory.create(source_type, content, source_url)
        parse_result = parser.parse()
        
        if not parse_result.success:
            logger.error(f"[{trace_id}] 解析失败: {parse_result.error}")
            return
        
        logger.info(f"[{trace_id}] 解析成功: {len(parse_result.endpoints)} 个接口")
        
        # 打印第一个接口的完整数据（解析器输出）
        if parse_result.endpoints:
            first_endpoint = parse_result.endpoints[0]
            print_section(f"步骤1.1: 解析器输出的第一个接口数据", first_endpoint)
            logger.info(f"[{trace_id}] 解析器输出字段: {list(first_endpoint.keys())}")
        
        # ========== 步骤2: 变更检测 ==========
        logger.info(f"\n[{trace_id}] 步骤2: 变更检测")
        db = next(get_db())
        
        try:
            # 获取现有接口定义（应该是空的，因为我们刚刚清理了）
            existing_endpoints = db.query(ApiDefinition).filter(
                ApiDefinition.project_id == 1
            ).all()
            
            logger.info(f"[{trace_id}] 现有接口数量: {len(existing_endpoints)}")
            
            # 构建old_endpoints
            old_endpoints = []
            for ep in existing_endpoints:
                old_endpoints.append({
                    "method": ep.method,
                    "path": ep.path,
                    "summary": ep.summary,
                    "description": ep.description,
                    "tags": ep.tags or [],
                    "request_schema": ep.request_schema,
                    "response_schema": ep.response_schema,
                    "parameters": ep.schema_snapshot.get('parameters', []) if ep.schema_snapshot else [],
                    "responses": ep.schema_snapshot.get('responses', {}) if ep.schema_snapshot else {},
                    "security": ep.schema_snapshot.get('security', []) if ep.schema_snapshot else []
                })
            
            # new_definitions来自解析器
            new_definitions = parse_result.endpoints
            
            logger.info(f"[{trace_id}] 新接口数量: {len(new_definitions)}")
            
            if new_definitions:
                print_section(f"步骤2.1: new_definitions的第一个元素", new_definitions[0])
                logger.info(f"[{trace_id}] new_definitions[0]字段: {list(new_definitions[0].keys())}")
            
            # 执行变更检测
            detector = ChangeDetector(db, trace_id)
            changes = detector.detect_changes(old_endpoints, new_definitions)
            
            logger.info(f"[{trace_id}] 变更检测完成")
            print_section(f"步骤2.2: 变更检测结果摘要", changes.get('summary', {}))
            
            # 打印diff_data中的第一个added接口
            if changes.get('added'):
                print_section(f"步骤2.3: diff_data['added']的第一个接口", changes['added'][0])
                logger.info(f"[{trace_id}] diff_data['added'][0]字段: {list(changes['added'][0].keys())}")
        
        finally:
            db.close()
        
        # ========== 步骤3: 模拟应用变更（不实际保存到数据库，只打印） ==========
        logger.info(f"\n[{trace_id}] 步骤3: 模拟应用变更")
        
        if changes.get('added'):
            endpoint_data = changes['added'][0]
            
            # 构建request_schema
            request_schema = endpoint_data.get('request_schema') or {}
            if 'parameters' in endpoint_data:
                request_schema['parameters'] = endpoint_data['parameters']
            
            # 构建response_schema
            response_schema = endpoint_data.get('response_schema') or {}
            if 'responses' in endpoint_data:
                response_schema['responses'] = endpoint_data['responses']
            
            print_section(f"步骤3.1: 构建的request_schema", request_schema)
            print_section(f"步骤3.2: 构建的response_schema", response_schema)
            
            # 模拟创建ApiDefinition对象
            simulated_api_def = {
                "project_id": 1,
                "method": endpoint_data.get('method'),
                "path": endpoint_data.get('path'),
                "summary": endpoint_data.get('summary', '')[:200],
                "description": endpoint_data.get('summary', '')[:200],
                "tags": endpoint_data.get('tags', []),
                "request_schema": request_schema,
                "response_schema": response_schema,
                "schema_snapshot": endpoint_data
            }
            
            print_section(f"步骤3.3: 模拟的ApiDefinition对象", simulated_api_def)
        
        # ========== 步骤4: 创建同步任务并执行 ==========
        logger.info(f"\n[{trace_id}] 步骤4: 创建同步任务")
        db = next(get_db())
        
        try:
            # 创建同步任务
            sync_task = SyncTask(
                project_id=1,
                name="数据流追踪测试",
                source_type=source_type,
                source_url=source_url,
                status="pending",
                total_count=0,
                added_count=0,
                updated_count=0,
                deleted_count=0,
                conflict_count=0,
                progress=0,
                created_by=1
            )
            
            db.add(sync_task)
            db.commit()
            db.refresh(sync_task)
            
            logger.info(f"[{trace_id}] 同步任务创建成功: id={sync_task.id}")
            
            # 执行同步任务逻辑
            from app.celery.tasks import _compare_and_detect_changes_impl
            
            result = _compare_and_detect_changes_impl(
                sync_task.id,
                sync_task.project_id,
                parse_result.endpoints,
                trace_id
            )
            
            logger.info(f"[{trace_id}] 同步任务执行完成")
            print_section(f"步骤4.1: 同步任务结果", result)
            
            # 刷新sync_task查看diff_data
            db.refresh(sync_task)
            
            if sync_task.diff_data and sync_task.diff_data.get('added'):
                print_section(f"步骤4.2: 数据库中sync_task.diff_data['added'][0]", sync_task.diff_data['added'][0])
                logger.info(f"[{trace_id}] 数据库diff_data['added'][0]字段: {list(sync_task.diff_data['added'][0].keys())}")
        
        finally:
            db.close()
        
        # ========== 步骤5: 应用变更到数据库 ==========
        logger.info(f"\n[{trace_id}] 步骤5: 应用变更到数据库")
        db = next(get_db())
        
        try:
            # 刷新sync_task
            sync_task = db.query(SyncTask).filter(SyncTask.id == sync_task.id).first()
            
            if sync_task.diff_data and sync_task.diff_data.get('added'):
                endpoint_data = sync_task.diff_data['added'][0]
                
                # 构建request_schema
                request_schema = endpoint_data.get('request_schema') or {}
                if 'parameters' in endpoint_data:
                    request_schema['parameters'] = endpoint_data['parameters']
                
                # 构建response_schema
                response_schema = endpoint_data.get('response_schema') or {}
                if 'responses' in endpoint_data:
                    response_schema['responses'] = endpoint_data['responses']
                
                # 创建ApiDefinition
                api_definition = ApiDefinition(
                    project_id=1,
                    method=endpoint_data.get('method'),
                    path=endpoint_data.get('path'),
                    summary=endpoint_data.get('summary', '')[:200],
                    description=endpoint_data.get('summary', '')[:200],
                    tags=endpoint_data.get('tags', []),
                    request_schema=request_schema,
                    response_schema=response_schema,
                    source_type=sync_task.source_type,
                    source_url=sync_task.source_url,
                    status="active",
                    schema_snapshot=endpoint_data
                )
                
                db.add(api_definition)
                db.commit()
                db.refresh(api_definition)
                
                logger.info(f"[{trace_id}] ApiDefinition创建成功: id={api_definition.id}")
                
                # 打印数据库中的数据
                print_section(f"步骤5.1: 数据库中的ApiDefinition.request_schema", api_definition.request_schema)
                print_section(f"步骤5.2: 数据库中的ApiDefinition.response_schema", api_definition.response_schema)
                print_section(f"步骤5.3: 数据库中的ApiDefinition.schema_snapshot", api_definition.schema_snapshot)
        
        finally:
            db.close()
        
        # ========== 步骤6: 查询接口定义详情 ==========
        logger.info(f"\n[{trace_id}] 步骤6: 查询接口定义详情")
        db = next(get_db())
        
        try:
            # 查询刚刚创建的接口定义
            api_definition = db.query(ApiDefinition).filter(
                ApiDefinition.path == sync_task.diff_data['added'][0]['path'],
                ApiDefinition.method == sync_task.diff_data['added'][0]['method']
            ).first()
            
            if api_definition:
                # 模拟API响应
                api_response = {
                    "id": api_definition.id,
                    "project_id": api_definition.project_id,
                    "group_id": api_definition.group_id,
                    "group_name": None,
                    "method": api_definition.method,
                    "path": api_definition.path,
                    "summary": api_definition.summary,
                    "description": api_definition.description,
                    "tags": api_definition.tags or [],
                    "request_schema": api_definition.request_schema,
                    "response_schema": api_definition.response_schema,
                    "mock_data": api_definition.mock_data,
                    "status": api_definition.status,
                    "sync_status": api_definition.sync_status,
                    "lock_status": api_definition.lock_status,
                    "content_hash": api_definition.content_hash,
                    "source_type": api_definition.source_type,
                    "source_version": api_definition.source_version,
                    "last_sync_at": api_definition.last_sync_at.isoformat() if api_definition.last_sync_at else None,
                    "case_count": 0,
                    "created_at": api_definition.created_at.isoformat() if api_definition.created_at else "",
                    "updated_at": api_definition.updated_at.isoformat() if api_definition.updated_at else "",
                    "created_by": api_definition.created_by,
                    "updated_by": api_definition.updated_by
                }
                
                print_section(f"步骤6.1: API查询响应（模拟）", api_response)
                logger.info(f"[{trace_id}] API响应request_schema字段: {api_response['request_schema']}")
                logger.info(f"[{trace_id}] API响应response_schema字段: {api_response['response_schema']}")
        
        finally:
            db.close()
        
        logger.info(f"\n[{trace_id}] 完整数据流追踪完成")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 追踪失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    trace_full_data_flow()