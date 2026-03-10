"""
Celery 异步任务定义

遵循后端代码规范：
- 全链路 TraceID：所有日志包含 TraceID
- 异常处理：确保任务失败时正确记录状态
- 数据库事务：每个任务独立管理数据库连接
- 魔法值清理：使用常量定义状态值
- 双写策略：同时写入 JSON 和建议表
"""
import asyncio
from datetime import datetime
from typing import Optional
from celery import Task
from app.celery_config import celery_app
from app.core.trace import get_trace_id
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.base import AsyncTask, FieldMappingSuggestion
from app.field_mapping.processor import FieldMappingProcessor
from app.field_mapping.constants import Stage
import logging

logger = logging.getLogger(__name__)


def _save_suggestions_to_db(db: Session, task_id: int, result: dict) -> None:
    """
    将建议数据保存到建议表（幂等性保证）
    
    遵循后端代码规范：
    - 幂等性保证：先删除旧数据再插入
    - 事务原子性：整个操作在一个事务中
    - 批量插入：使用 bulk_save_objects 提升性能
    - 异常处理：记录错误并回滚
    
    Args:
        db: 数据库会话
        task_id: 任务ID
        result: 任务结果
    """
    trace_id = get_trace_id()
    suggestions_list = result.get("suggestions", [])
    
    if not suggestions_list:
        logger.info(f"[{trace_id}] 建议列表为空，跳过保存到建议表")
        return
    
    logger.info(f"[{trace_id}] 开始保存建议数据到数据库: task_id={task_id}, count={len(suggestions_list)}")
    
    try:
        # 1. 清理旧建议（幂等性保证）
        # 如果任务重试，先删除之前的建议，防止数据重复
        deleted_count = db.query(FieldMappingSuggestion).filter(
            FieldMappingSuggestion.task_id == task_id
        ).delete(synchronize_session=False)
        
        if deleted_count > 0:
            logger.info(f"[{trace_id}] 清理旧建议数据: {deleted_count} 条")
        
        # 2. 准备新数据
        suggestion_objects = []
        
        for item in suggestions_list:
            # 确保 candidates 是可序列化的纯字典/列表
            candidates = item.get("candidates", [])
            
            # 序列化检查：确保不包含不可序列化的对象
            if not isinstance(candidates, list):
                logger.warning(f"[{trace_id}] candidates 不是列表: {type(candidates)}")
                candidates = []
            
            # 获取 project_id（从 result 中获取，如果没有则从 task 中获取）
            project_id = item.get("project_id")
            if project_id is None:
                task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
                if task:
                    project_id = task.project_id
            
            obj = FieldMappingSuggestion(
                task_id=task_id,
                project_id=project_id,
                definition_id=item.get("definition_id"),
                api_field_path=item.get("api_field_path"),
                candidates=candidates,  # JSON 字段，SQLAlchemy 自动序列化
                decision_trace=item.get("decision_trace"),
                status="pending"
            )
            suggestion_objects.append(obj)
        
        # 3. 批量插入（性能优化）
        if suggestion_objects:
            db.bulk_save_objects(suggestion_objects)
            logger.info(f"[{trace_id}] 批量插入建议数据: {len(suggestion_objects)} 条")
        
        db.commit()
        logger.info(f"[{trace_id}] 建议数据保存成功")
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 保存建议数据失败: {str(e)}", exc_info=True)
        # 记录失败信息到任务（可观测性）
        error_msg = f"保存建议数据失败: {str(e)}"
        try:
            task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
            if task:
                task.error_message = error_msg
                if not task.statistics:
                    task.statistics = {}
                task.statistics["write_table_failed"] = True
                task.statistics["write_table_error"] = str(e)
                db.commit()
        except:
            pass
        # 抛出异常，让任务状态变为 failed
        raise Exception(error_msg)


@celery_app.task(bind=True)
def example_task(self, *args, **kwargs):
    """
    示例任务
    """
    logger.info(f"Example task executed with args: {args}, kwargs: {kwargs}")
    return {"status": "success"}


@celery_app.task(bind=True, name="app.celery.tasks.execute_sync_task")
def execute_sync_task(self, sync_task_id: int):
    """
    执行文档同步任务

    Args:
        sync_task_id: 同步任务 ID（sync_tasks.id）

    Returns:
        任务结果
    """
    trace_id = get_trace_id()
    
    db: Session = SessionLocal()
    
    try:
        logger.info(f"[{trace_id}] 同步任务开始执行，任务 ID: {sync_task_id}")
        
        # 导入 SyncTask 模型（避免循环导入）
        from app.db.base import SyncTask, ApiDefinition, ApiEndpointGroup
        from app.parsers import ParserFactory
        from app.core.sync.change_detector import ChangeDetector, ImpactAnalyzer
        
        # 查询同步任务
        sync_task = db.query(SyncTask).filter(SyncTask.id == sync_task_id).first()
        
        if not sync_task:
            logger.error(f"[{trace_id}] 同步任务不存在: {sync_task_id}")
            return {"success": False, "error": "同步任务不存在"}
        
        # 更新 Celery 任务 ID
        sync_task.task_id = self.request.id
        sync_task.celery_task_id = self.request.id
        db.commit()

        logger.info(f"[{trace_id}] Celery 任务 ID: {self.request.id}")

        # 更新任务状态为 running
        sync_task.status = "running"
        sync_task.started_at = datetime.now()
        sync_task.progress = 0
        db.commit()

        logger.info(f"[{trace_id}] 任务状态已设置为 running")

        # 步骤 1: 获取文档内容
        logger.info(f"[{trace_id}] [步骤1] 获取文档内容...")
        
        if sync_task.source_url:
            # 从 URL 获取内容
            document_content = sync_task.source_url
        else:
            # 从其他来源获取内容（这里需要根据实际需求实现）
            logger.error(f"[{trace_id}] 缺少文档来源 URL")
            raise ValueError("缺少文档来源 URL")
        
        logger.info(f"[{trace_id}] [步骤1] 文档来源: {document_content[:100]}...")

        # 步骤 2: 解析文档
        logger.info(f"[{trace_id}] [步骤2] 解析文档...")
        sync_task.progress = 10
        db.commit()
        
        try:
            parser = ParserFactory.create(
                source_type=sync_task.source_type,
                content=document_content,
                source_url=sync_task.source_url
            )
            parse_result = parser.parse()
            
            if not parse_result.success:
                logger.error(f"[{trace_id}] 文档解析失败: {parse_result.error}")
                raise ValueError(f"文档解析失败: {parse_result.error}")
            
            logger.info(f"[{trace_id}] [步骤2] 文档解析成功，提取到 {len(parse_result.endpoints)} 个接口")
        except Exception as e:
            logger.error(f"[{trace_id}] 文档解析异常: {str(e)}", exc_info=True)
            raise
        
        # 步骤 3: 获取现有接口定义
        logger.info(f"[{trace_id}] [步骤3] 获取现有接口定义...")
        sync_task.progress = 20
        db.commit()
        
        existing_definitions = db.query(ApiDefinition).filter(
            ApiDefinition.project_id == sync_task.project_id
        ).all()
        
        old_definitions = [
            {
                "method": d.method,
                "path": d.path,
                "summary": d.summary,
                "description": d.description,
                "tags": d.tags or [],
                "request_schema": d.request_schema or {},
                "response_schema": d.response_schema or {},
                "parameters": [],  # 简化处理
                "responses": {},  # 简化处理
                "security": [],  # 简化处理
            }
            for d in existing_definitions
        ]
        
        logger.info(f"[{trace_id}] [步骤3] 找到 {len(old_definitions)} 个现有接口")

        # 步骤 4: 变更检测
        logger.info(f"[{trace_id}] [步骤4] 执行变更检测...")
        sync_task.progress = 30
        db.commit()
        
        change_detector = ChangeDetector(db, trace_id)
        diff_result = change_detector.detect_changes(old_definitions, parse_result.endpoints)
        
        logger.info(f"[{trace_id}] [步骤4] 变更检测完成: {diff_result['summary']}")

        # 步骤 5: 影响分析
        logger.info(f"[{trace_id}] [步骤5] 执行影响分析...")
        sync_task.progress = 50
        db.commit()
        
        impact_analyzer = ImpactAnalyzer(db, trace_id)
        
        # 收集所有变更的接口
        changed_endpoints = (
            diff_result.get("added", []) +
            diff_result.get("changed", []) +
            diff_result.get("removed", [])
        )
        
        if changed_endpoints:
            impact_result = impact_analyzer.scan_impact(
                changed_endpoints=changed_endpoints,
                project_id=sync_task.project_id,
                user_id=sync_task.created_by or 0
            )
            logger.info(f"[{trace_id}] [步骤5] 影响分析完成: {impact_result['summary']}")
        else:
            impact_result = {
                "affected_cases": [],
                "affected_scenarios": [],
                "summary": {
                    "affected_case_count": 0,
                    "affected_scenario_count": 0,
                    "total_affected": 0
                }
            }
            logger.info(f"[{trace_id}] [步骤5] 无变更，跳过影响分析")

        # 步骤 6: 保存结果
        logger.info(f"[{trace_id}] [步骤6] 保存同步结果...")
        sync_task.progress = 80
        db.commit()
        
        sync_task.diff_data = {
            "old_definitions": old_definitions,
            "new_definitions": parse_result.endpoints,
            "added": diff_result.get("added", []),
            "changed": diff_result.get("changed", []),
            "removed": diff_result.get("removed", []),
            "unchanged": diff_result.get("unchanged", []),
            "summary": diff_result.get("summary", {})
        }
        
        sync_task.impact_analysis = impact_result
        
        sync_task.total_count = len(parse_result.endpoints)
        sync_task.added_count = diff_result["summary"].get("added_count", 0)
        sync_task.updated_count = diff_result["summary"].get("changed_count", 0)
        sync_task.deleted_count = diff_result["summary"].get("removed_count", 0)
        
        # 保存执行日志
        sync_task.execution_log = [
            {
                "step": "解析文档",
                "status": "success",
                "message": f"成功解析 {len(parse_result.endpoints)} 个接口"
            },
            {
                "step": "变更检测",
                "status": "success",
                "message": f"发现 {diff_result['summary']['total_changes']} 个变更"
            },
            {
                "step": "影响分析",
                "status": "success",
                "message": f"影响 {impact_result['summary']['total_affected']} 个用例/场景"
            }
        ]
        
        sync_task.progress = 100
        sync_task.status = "completed"
        sync_task.completed_at = datetime.now()
        db.commit()
        
        logger.info(f"[{trace_id}] 同步任务执行完成")
        
        return {
            "success": True,
            "sync_task_id": sync_task_id,
            "summary": {
                "total": sync_task.total_count,
                "added": sync_task.added_count,
                "updated": sync_task.updated_count,
                "deleted": sync_task.deleted_count,
                "affected_cases": impact_result["summary"]["affected_case_count"],
                "affected_scenarios": impact_result["summary"]["affected_scenario_count"]
            }
        }
        
    except Exception as e:
        logger.error(f"[{trace_id}] 同步任务执行失败: {str(e)}", exc_info=True)
        
        # 更新任务状态为失败
        try:
            sync_task = db.query(SyncTask).filter(SyncTask.id == sync_task_id).first()
            if sync_task:
                sync_task.status = "failed"
                sync_task.error_message = str(e)
                sync_task.completed_at = datetime.now()
                db.commit()
        except:
            pass
        
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()


@celery_app.task(bind=True, name="app.celery.tasks.execute_field_mapping_task")
def execute_field_mapping_task(self, task_id: int):
    """
    执行字段映射建议任务

    Args:
        task_id: 异步任务 ID（async_tasks.id）

    Returns:
        任务结果
    """
    trace_id = get_trace_id()
    
    db: Session = SessionLocal()
    
    try:
        logger.info(f"[{trace_id}] Celery 任务开始执行，任务 ID: {task_id}")
        
        # 查询任务信息
        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        
        if not task:
            logger.error(f"[{trace_id}] 任务不存在: {task_id}")
            return {"success": False, "error": "任务不存在"}
        
        # 更新 Celery 任务 ID
        task.celery_task_id = self.request.id
        db.commit()

        logger.info(f"[{trace_id}] Celery 任务 ID: {self.request.id}")

        # 显式设置任务状态为 running
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()

        logger.info(f"[{trace_id}] 任务状态已设置为 running")

        # 执行字段映射处理
        processor = FieldMappingProcessor(db, task)
        
        # 使用 asyncio.run 执行异步处理器
        result = asyncio.run(processor.process())
        
        # 保存结果到数据库（双写策略）
        if result and result.get('success'):
            # 1. 保存 JSON 备份（向后兼容）
            task.result = result

            # 2. 双写到建议表，失败时标记 PARTIAL_SUCCESS
            write_table_ok = True
            try:
                _save_suggestions_to_db(db, task_id, result)
            except Exception as write_err:
                write_table_ok = False
                logger.error(f"[{trace_id}] 双写建议表失败，降级为 partial_success: {str(write_err)}")
                if not task.statistics:
                    task.statistics = {}
                task.statistics["write_table_failed"] = True
                task.statistics["write_table_error"] = str(write_err)
                task.error_message = f"建议表写入失败: {str(write_err)}"

            if write_table_ok:
                task.status = "completed"
                # 3. 结果一致性约束检查
                try:
                    from app.db.base import FieldMappingSuggestion

                    # 检查建议表数量是否与 result.suggestions 一致
                    suggestions_count = len(result.get("suggestions", []))
                    table_count = db.query(FieldMappingSuggestion).filter(
                        FieldMappingSuggestion.task_id == task_id
                    ).count()

                    if suggestions_count != table_count:
                        logger.warning(
                            f"[{trace_id}] 结果数量不一致: "
                            f"result.suggestions={suggestions_count}, 建议表={table_count}"
                        )

                        # 记录偏差到统计信息
                        if not task.statistics:
                            task.statistics = {}
                        task.statistics["result_consistency_mismatch"] = True
                        task.statistics["result_suggestions_count"] = suggestions_count
                        task.statistics["table_suggestions_count"] = table_count
                        task.statistics["consistency_diff"] = abs(suggestions_count - table_count)

                except Exception as e:
                    logger.warning(f"[{trace_id}] 结果一致性检查失败: {str(e)}")
            else:
                task.status = "partial_success"
        else:
            task.status = "failed"
            task.error_message = (result or {}).get("error", "字段映射任务执行失败")

        task.finished_at = datetime.now()
        db.commit()
        
        logger.info(f"[{trace_id}] Celery 任务执行完成，结果: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"[{trace_id}] Celery 任务执行失败: {str(e)}", exc_info=True)
        
        # 更新任务状态为失败
        try:
            task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                
                # 记录失败指标
                if not task.statistics:
                    task.statistics = {}
                task.statistics["failed_at"] = datetime.now().isoformat()
                
                db.commit()
        except:
            pass
        
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()


@celery_app.task(bind=True, name="app.celery.tasks.execute_scenario_task")
def execute_scenario_task(self, execution_id: int, scenario_id: int, environment_id: int, callback_url: Optional[str] = None):
    """
    执行场景任务（用于 CI/CD 触发）
    
    BSK-SC-026: CI/CD 触发接口
    
    Args:
        execution_id: 执行 ID
        scenario_id: 场景 ID
        environment_id: 环境 ID
        callback_url: 回调 URL（可选）
        
    Returns:
        任务结果
    """
    trace_id = get_trace_id()
    
    db: Session = SessionLocal()
    
    try:
        logger.info(f"[{trace_id}] Celery 场景任务开始执行: execution_id={execution_id}, scenario_id={scenario_id}")
        
        # 查询执行记录
        from app.db.base import TestExecution
        execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
        
        if not execution:
            logger.error(f"[{trace_id}] 执行记录不存在: {execution_id}")
            return {"success": False, "error": "执行记录不存在"}
        
        # 更新 Celery 任务 ID
        execution.celery_task_id = self.request.id
        execution.status = "running"
        execution.started_at = datetime.now()
        db.commit()
        
        logger.info(f"[{trace_id}] Celery 任务 ID: {self.request.id}")
        
        # 执行场景
        from app.core.test_execution import ScenarioExecutor
        executor = ScenarioExecutor()
        
        # 使用 asyncio.run 执行异步处理器
        result = asyncio.run(executor.execute_scenario(
            scenario_id=scenario_id,
            graph_data=None,
            variables={},
            db=db
        ))
        
        # 更新执行结果
        execution.status = result['status']
        execution.finished_at = datetime.now()
        execution.duration_ms = result['summary'].get('duration_ms', 0)
        execution.summary = result['summary']
        execution.results = result['results']
        
        if result['status'] == 'failed':
            execution.error_message = f"执行失败: {result['summary'].get('failed', 0)} 个节点失败"
        
        db.commit()
        
        logger.info(
            f"[{trace_id}] Celery 场景任务执行完成: "
            f"status={result['status']}, passed={result['summary']['passed']}, "
            f"failed={result['summary']['failed']}"
        )
        
        # BSK-SC-026: 异步回调
        if callback_url:
            try:
                import httpx
                
                callback_payload = {
                    "execution_id": execution_id,
                    "scenario_id": scenario_id,
                    "status": result['status'],
                    "summary": result['summary'],
                    "timestamp": datetime.now().isoformat()
                }
                
                response = httpx.post(callback_url, json=callback_payload, timeout=30.0)
                logger.info(f"[{trace_id}] 回调发送成功: {callback_url}, status={response.status_code}")
            except Exception as callback_error:
                logger.warning(f"[{trace_id}] 回调发送失败: {str(callback_error)}")
        
        return result
        
    except Exception as e:
        logger.error(f"[{trace_id}] Celery 场景任务执行失败: {str(e)}", exc_info=True)
        
        # 更新执行状态为失败
        try:
            execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
            if execution:
                execution.status = "failed"
                execution.finished_at = datetime.now()
                execution.error_message = str(e)
                db.commit()
        except:
            pass
        
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()
