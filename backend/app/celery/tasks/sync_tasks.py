from ._common import *

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
        from app.platform.db.base import SyncTask, ApiDefinition, ApiEndpointGroup
        from app.integrations import ParserFactory
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


