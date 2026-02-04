"""Celery 异步任务"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from celery import chain, group
from app.celery_config import celery_app
from app.db.base import ApiEndpoint, ApiDependency, ApiEndpointGroup, AsyncTask
from app.core.dependency import DependencyAnalyzer
from app.db.session import get_db
from app.core.trace import get_trace_id
from app.constants.task import TaskType, TaskStatus
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def analyze_group_dependencies(self, task_id: int, group_id: int, project_id: int, version_id: int = None):
    """
    分析单个分组的依赖关系

    Args:
        task_id: 异步任务ID
        group_id: 分组ID
        project_id: 项目ID
        version_id: 版本ID（可选）

    Returns:
        依赖关系ID列表
    """
    trace_id = get_trace_id()
    db = next(get_db())

    try:
        # 更新任务状态为运行中
        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.utcnow()
            db.commit()

        logger.info(f"[{trace_id}] 开始分析分组依赖: group_id={group_id}, project_id={project_id}")

        # 查询该分组的所有接口
        query = db.query(ApiEndpoint).filter(
            ApiEndpoint.project_id == project_id,
            ApiEndpoint.group_id == group_id,
            ApiEndpoint.is_deleted == False
        )

        if version_id:
            from app.db.base import VersionEndpoint
            query = query.join(VersionEndpoint, VersionEndpoint.endpoint_id == ApiEndpoint.id).filter(
                VersionEndpoint.version_id == version_id
            )

        endpoints = query.all()

        if not endpoints:
            logger.warning(f"[{trace_id}] 分组 {group_id} 中没有接口")
            return []

        logger.info(f"[{trace_id}] 分组 {group_id} 查询到 {len(endpoints)} 个接口")

        # 分析依赖关系
        analyzer = DependencyAnalyzer(db)
        dependencies = analyzer.analyze_dependencies(project_id, endpoints)

        # 保存依赖关系
        for dep in dependencies:
            db.add(dep)

        db.commit()

        # 更新任务状态为完成
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.finished_at = datetime.utcnow()
            task.task_result = {
                "group_id": group_id,
                "dependency_count": len(dependencies),
                "dependencies": [
                    {
                        "source": dep.source_endpoint_id,
                        "target": dep.target_endpoint_id,
                        "strength": dep.dependency_strength
                    }
                    for dep in dependencies
                ]
            }
            db.commit()

        logger.info(f"[{trace_id}] 分组 {group_id} 依赖分析完成: {len(dependencies)} 个依赖关系")
        return [dep.id for dep in dependencies]

    except Exception as e:
        logger.error(f"[{trace_id}] 分组 {group_id} 依赖分析失败: {str(e)}", exc_info=True)

        # 更新任务状态为失败
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = str(e)
            task.finished_at = datetime.utcnow()
            db.commit()

        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        db.close()


@celery_app.task(bind=True)
def aggregate_group_results(self, task_id: int):
    """
    聚合所有分组的分析结果

    Args:
        task_id: 主任务ID

    Returns:
        业务链路列表
    """
    trace_id = get_trace_id()
    db = next(get_db())

    try:
        # 更新任务状态
        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        project_id = task.project_id if task else None

        if task:
            task.progress = 80
            task.progress_message = "正在聚合分析结果"
            db.commit()

        logger.info(f"[{trace_id}] 开始聚合分析结果: task_id={task_id}")

        # 查询所有依赖关系
        all_dependencies = db.query(ApiDependency).filter(
            ApiDependency.project_id == project_id
        ).all()

        # 识别业务链路
        analyzer = DependencyAnalyzer(db)
        chains = analyzer.find_business_chains(all_dependencies)

        # 更新任务状态为完成
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.finished_at = datetime.utcnow()
            task.task_result = {
                "dependency_count": len(all_dependencies),
                "chain_count": len(chains),
                "chains": chains
            }
            db.commit()

        logger.info(f"[{trace_id}] 聚合完成: {len(all_dependencies)} 个依赖, {len(chains)} 个链路")
        return chains

    except Exception as e:
        logger.error(f"[{trace_id}] 聚合失败: {str(e)}", exc_info=True)

        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = str(e)
            task.finished_at = datetime.utcnow()
            db.commit()

        raise
    finally:
        db.close()


@celery_app.task
def create_group_analysis_tasks(project_id: int, user_id: int, version_id: int = None):
    """
    为项目的所有分组创建分析任务

    Args:
        project_id: 项目ID
        user_id: 用户ID
        version_id: 版本ID（可选）

    Returns:
        主任务ID
    """
    trace_id = get_trace_id()
    db = next(get_db())

    try:
        logger.info(f"[{trace_id}] 创建分组分析任务: project_id={project_id}")

        # 查询所有分组
        groups = db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.project_id == project_id
        ).all()

        if not groups:
            logger.warning(f"[{trace_id}] 项目 {project_id} 没有分组")
            return None

        # 创建主任务
        main_task = AsyncTask(
            project_id=project_id,
            user_id=user_id,
            task_type=TaskType.DEPENDENCY_ANALYSIS.value,
            task_params={"project_id": project_id, "version_id": version_id},
            status=TaskStatus.PENDING.value,
            priority=5,
            estimated_duration=len(groups) * 30  # 预计每个分组30秒
        )
        db.add(main_task)
        db.commit()
        db.refresh(main_task)

        logger.info(f"[{trace_id}] 创建主任务: task_id={main_task.id}, group_count={len(groups)}")

        # 为每个分组创建子任务
        group_tasks = []
        for grp in groups:
            sub_task = AsyncTask(
                project_id=project_id,
                user_id=user_id,
                group_id=grp.id,
                task_type=TaskType.DEPENDENCY_ANALYSIS.value,
                task_params={"project_id": project_id, "version_id": version_id},
                status=TaskStatus.PENDING.value,
                priority=5
            )
            db.add(sub_task)
            db.commit()
            db.refresh(sub_task)

            # 创建 Celery 任务
            celery_task = analyze_group_dependencies.apply_async(
                args=[sub_task.id, grp.id, project_id, version_id],
                priority=5
            )

            sub_task.celery_task_id = celery_task.id
            db.commit()

            group_tasks.append(analyze_group_dependencies.si(sub_task.id, grp.id, project_id, version_id))

        # 创建任务链：并行分析所有分组 -> 聚合结果
        task_chain = chain(
            group(*group_tasks),  # 并行执行所有分组分析
            aggregate_group_results.s(main_task.id)  # 聚合结果
        )

        result = task_chain.apply_async()

        main_task.celery_task_id = result.id
        db.commit()

        logger.info(f"[{trace_id}] 分组分析任务链已创建: celery_task_id={result.id}")
        return main_task.id

    except Exception as e:
        logger.error(f"[{trace_id}] 创建分组分析任务失败: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


# ==================== 模块化依赖分析任务 ====================

@celery_app.task(bind=True, max_retries=3)
def analyze_module(self, task_id: int, group_id: int, project_id: int, version_id: int = None):
    """
    分析单个模块的依赖关系

    Args:
        task_id: 异步任务ID
        group_id: 分组ID（模块ID）
        project_id: 项目ID
        version_id: 版本ID（可选）

    Returns:
        模块分析结果
    """
    trace_id = get_trace_id()
    db = next(get_db())

    try:
        # 更新任务状态为运行中
        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.utcnow()
            db.commit()

        logger.info(f"[{trace_id}] 开始分析模块: group_id={group_id}, project_id={project_id}")

        # 使用 ModuleAnalyzer 分析模块
        from app.core.dependency import ModuleAnalyzer
        analyzer = ModuleAnalyzer(db)
        result = analyzer.analyze_module_dependencies(
            project_id=project_id,
            group_id=group_id,
            version_id=version_id
        )

        # 更新任务状态为完成
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.finished_at = datetime.utcnow()
            task.task_result = result
            db.commit()

        logger.info(f"[{trace_id}] 模块 {group_id} 分析完成: {result}")
        return result

    except Exception as e:
        logger.error(f"[{trace_id}] 模块 {group_id} 分析失败: {str(e)}", exc_info=True)

        # 更新任务状态为失败
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = str(e)
            task.finished_at = datetime.utcnow()
            db.commit()

        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        db.close()


@celery_app.task(bind=True)
def analyze_cross_module_dependencies(self, task_id: int, project_id: int, version_id: int = None):
    """
    分析模块间的依赖关系

    Args:
        task_id: 主任务ID
        project_id: 项目ID
        version_id: 版本ID（可选）

    Returns:
        模块链路列表
    """
    trace_id = get_trace_id()
    db = next(get_db())

    try:
        # 更新任务状态
        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.progress = 50
            task.progress_message = "正在分析模块间依赖"
            db.commit()

        logger.info(f"[{trace_id}] 开始分析模块间依赖: project_id={project_id}")

        # 使用 ModuleDependencyAnalyzer 分析模块间依赖
        from app.core.dependency import ModuleDependencyAnalyzer
        analyzer = ModuleDependencyAnalyzer(db)
        module_dependencies = analyzer.analyze_module_dependencies(
            project_id=project_id,
            version_id=version_id
        )

        # 识别模块链路
        module_chains = analyzer.find_module_chains(project_id, module_dependencies)

        # 更新任务状态为完成
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.finished_at = datetime.utcnow()
            task.task_result = {
                "module_dependency_count": len(module_dependencies),
                "module_chain_count": len(module_chains),
                "module_chains": module_chains
            }
            db.commit()

        logger.info(
            f"[{trace_id}] 模块间依赖分析完成: "
            f"{len(module_dependencies)} 个依赖, {len(module_chains)} 个链路"
        )
        return module_chains

    except Exception as e:
        logger.error(f"[{trace_id}] 模块间依赖分析失败: {str(e)}", exc_info=True)

        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = str(e)
            task.finished_at = datetime.utcnow()
            db.commit()

        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def compose_module_scenarios(self, task_id: int, project_id: int, module_chain: List[int], chain_name: str):
    """
    组合跨模块场景

    Args:
        task_id: 任务ID
        project_id: 项目ID
        module_chain: 模块链路
        chain_name: 链路名称

    Returns:
        生成的场景列表
    """
    trace_id = get_trace_id()
    db = next(get_db())

    try:
        # 更新任务状态
        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.progress = 50
            task.progress_message = "正在组合跨模块场景"
            db.commit()

        logger.info(
            f"[{trace_id}] 开始组合跨模块场景: "
            f"project_id={project_id}, chain={module_chain}, name={chain_name}"
        )

        # 使用 ModuleChainComposer 组合场景
        from app.core.scenario import ModuleChainComposer
        composer = ModuleChainComposer(db)

        # 保存模块链路
        module_chain_obj = composer.save_module_chain(
            project_id=project_id,
            module_chain=module_chain,
            chain_name=chain_name
        )

        # 生成场景
        scenarios = composer.compose_cross_module_scenarios(
            project_id=project_id,
            module_chain=module_chain,
            chain_name=chain_name,
            description=f"基于模块链路自动生成的业务场景"
        )

        # 更新任务状态为完成
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.finished_at = datetime.utcnow()
            task.task_result = {
                "module_chain_id": module_chain_obj.id,
                "scenario_count": len(scenarios),
                "scenarios": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "endpoint_count": s.endpoint_count
                    }
                    for s in scenarios
                ]
            }
            db.commit()

        logger.info(
            f"[{trace_id}] 跨模块场景组合完成: "
            f"module_chain_id={module_chain_obj.id}, scenario_count={len(scenarios)}"
        )
        return [s.id for s in scenarios]

    except Exception as e:
        logger.error(f"[{trace_id}] 跨模块场景组合失败: {str(e)}", exc_info=True)

        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = str(e)
            task.finished_at = datetime.utcnow()
            db.commit()

        raise
    finally:
        db.close()


@celery_app.task
def create_module_analysis_tasks(project_id: int, user_id: int, version_id: int = None):
    """
    为项目的所有模块创建分析任务

    Args:
        project_id: 项目ID
        user_id: 用户ID
        version_id: 版本ID（可选）

    Returns:
        主任务ID
    """
    trace_id = get_trace_id()
    db = next(get_db())

    try:
        logger.info(f"[{trace_id}] 创建模块分析任务: project_id={project_id}")

        # 查询所有分组（模块）
        groups = db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.project_id == project_id
        ).all()

        if not groups:
            logger.warning(f"[{trace_id}] 项目 {project_id} 没有模块")
            return None

        # 创建主任务
        main_task = AsyncTask(
            project_id=project_id,
            user_id=user_id,
            task_type="module_analysis",
            task_params={"project_id": project_id, "version_id": version_id},
            status="pending",
            priority=5,
            estimated_duration=len(groups) * 30  # 预计每个模块30秒
        )
        db.add(main_task)
        db.commit()
        db.refresh(main_task)

        logger.info(f"[{trace_id}] 创建主任务: task_id={main_task.id}, module_count={len(groups)}")

        # 为每个模块创建子任务
        module_tasks = []
        for grp in groups:
            sub_task = AsyncTask(
                project_id=project_id,
                user_id=user_id,
                group_id=grp.id,
                task_type="module_analysis",
                task_params={"project_id": project_id, "version_id": version_id},
                status="pending",
                priority=5
            )
            db.add(sub_task)
            db.commit()
            db.refresh(sub_task)

            # 创建 Celery 任务
            celery_task = analyze_module.apply_async(
                args=[sub_task.id, grp.id, project_id, version_id],
                priority=5
            )

            sub_task.celery_task_id = celery_task.id
            db.commit()

            module_tasks.append(analyze_module.si(sub_task.id, grp.id, project_id, version_id))

        # 创建任务链：并行分析所有模块 -> 分析模块间依赖
        task_chain = chain(
            group(*module_tasks),  # 并行执行所有模块分析
            analyze_cross_module_dependencies.s(main_task.id, project_id, version_id)  # 分析模块间依赖
        )

        result = task_chain.apply_async()

        main_task.celery_task_id = result.id
        db.commit()

        logger.info(f"[{trace_id}] 模块分析任务链已创建: celery_task_id={result.id}")
        return main_task.id

    except Exception as e:
        logger.error(f"[{trace_id}] 创建模块分析任务失败: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


__all__ = [
    'analyze_group_dependencies',
    'aggregate_group_results',
    'create_group_analysis_tasks',
    'analyze_module',
    'analyze_cross_module_dependencies',
    'compose_module_scenarios',
    'create_module_analysis_tasks',
    'execute_sync_task',
    'fetch_and_parse_document',
    'compare_and_detect_changes',
    'scan_impact_and_report',
]


# ==================== API 资产库同步任务 ====================

@celery_app.task(bind=True, max_retries=3)
def execute_sync_task(self, task_id: int):
    """
    执行同步任务的主入口
    
    Args:
        task_id: 同步任务 ID
    """
    trace_id = get_trace_id()
    db = next(get_db())

    try:
        from app.db.base import SyncTask
        from app.core.sync.change_detector import ChangeDetector, ImpactAnalyzer
        from app.parsers import ParserFactory
        
        # 获取同步任务
        sync_task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
        if not sync_task:
            logger.error(f"[{trace_id}] 同步任务不存在: task_id={task_id}")
            return
        
        # 更新任务状态为运行中
        sync_task.status = "running"
        sync_task.started_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"[{trace_id}] 开始执行同步任务: {sync_task.name} (source_type={sync_task.source_type})")
        
        # 1. 获取并解析文档（直接调用函数，不使用子任务）
        from app.celery.tasks import _fetch_and_parse_document_impl
        result = _fetch_and_parse_document_impl(task_id, sync_task.source_type, sync_task.source_url, trace_id)
        
        if not result.get("success"):
            raise Exception(f"文档解析失败: {result.get('error')}")
        
        # 2. 对比并检测变更（直接调用函数，不使用子任务）
        from app.celery.tasks import _compare_and_detect_changes_impl
        result = _compare_and_detect_changes_impl(task_id, sync_task.project_id, result.get("endpoints", []), trace_id)
        
        # 3. 扫描影响范围并生成报告（直接调用函数，不使用子任务）
        from app.celery.tasks import _scan_impact_and_report_impl
        result = _scan_impact_and_report_impl(task_id, sync_task.project_id, sync_task.created_by, result.get("changes", []), trace_id)
        
        # 更新任务状态为完成
        sync_task.status = "completed"
        sync_task.completed_at = datetime.utcnow()
        sync_task.progress = 100
        db.commit()
        
        logger.info(f"[{trace_id}] 同步任务完成: {sync_task.name}")
        
        return result
        
    except Exception as e:
        logger.error(f"[{trace_id}] 同步任务执行失败: {str(e)}", exc_info=True)
        
        # 更新任务状态为失败
        sync_task.status = "failed"
        sync_task.error_message = str(e)
        sync_task.completed_at = datetime.utcnow()
        db.commit()
        
        raise


def _fetch_and_parse_document_impl(task_id: int, source_type: str, source_url: str, trace_id: str) -> Dict[str, Any]:
    """
    获取并解析文档的实现函数
    
    Args:
        task_id: 任务 ID
        source_type: 来源类型
        source_url: 来源 URL
        trace_id: 追踪 ID
        
    Returns:
        Dict: 解析结果
    """
    db = next(get_db())
    
    try:
        from app.db.base import SyncTask
        from app.parsers import ParserFactory
        
        # 获取同步任务
        sync_task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
        if not sync_task:
            return {"success": False, "error": "任务不存在"}
        
        logger.info(f"[{trace_id}] 开始获取文档: {source_url}")

        # 获取文档内容
        import requests
        response = requests.get(source_url, timeout=30)
        response.raise_for_status()
        content = response.text

        # 检测是否是 Swagger UI HTML 页面
        if '<!DOCTYPE html>' in content or '<html' in content.lower():
            logger.warning(f"[{trace_id}] 检测到 HTML 页面，尝试提取 OpenAPI JSON URL")

            # 尝试从 HTML 中提取 Swagger UI 的 spec URL
            import re
            # 查找常见的 Swagger UI 配置模式
            patterns = [
                r'url:\s*[\'"]([^\'"]+\.json)[\'"]',  # url: "/api-docs.json"
                r'spec:\s*[\'"]([^\'"]+\.json)[\'"]',  # spec: "/api-docs.json"
                r'swagger-ui\.bundle\.js.*url:\s*[\'"]([^\'"]+)[\'"]',  # Swagger UI bundle
                r'href=[\'"]([^\'"]+\.json)[\'"]',  # href="swagger.json"
            ]

            extracted_url = None
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    extracted_url = match.group(1)
                    logger.info(f"[{trace_id}] 从 HTML 中提取到文档 URL: {extracted_url}")
                    break

            if extracted_url:
                # 处理相对路径
                if extracted_url.startswith('/'):
                    from urllib.parse import urlparse
                    parsed = urlparse(source_url)
                    actual_url = f"{parsed.scheme}://{parsed.netloc}{extracted_url}"
                elif not extracted_url.startswith('http'):
                    from urllib.parse import urljoin
                    actual_url = urljoin(source_url, extracted_url)
                else:
                    actual_url = extracted_url

                logger.info(f"[{trace_id}] 使用提取的实际文档 URL: {actual_url}")

                # 重新获取实际的 JSON 文档
                response = requests.get(actual_url, timeout=30)
                response.raise_for_status()
                content = response.text
            else:
                # 无法提取 URL，提供友好的错误提示
                return {
                    "success": False,
                    "error": f"检测到 Swagger UI HTML 页面，但无法提取文档 URL。请使用实际的 OpenAPI JSON/YAML 文档 URL（通常以 .json 或 .yaml 结尾）。示例：{source_url.rstrip('/')}.json"
                }

        # 解析文档
        parser = ParserFactory.create(source_type, content, source_url)
        parse_result = parser.parse()
        
        if not parse_result.success:
            error_msg = parse_result.error

            # 检查是否是 URL 格式问题
            if '无法解析文档内容' in error_msg or 'JSON' in error_msg or 'YAML' in error_msg:
                error_msg += f"\n\n提示：请确保使用正确的 OpenAPI/Swagger 文档 URL。\n常见格式：\n- Swagger UI HTML 页面不是有效的文档 URL\n- 应该使用实际的 JSON/YAML 文档 URL（通常以 .json 或 .yaml 结尾）\n- 示例：http://127.0.0.1:1337/api-docs.json 或 http://127.0.0.1:1337/openapi.json"

            return {
                "success": False,
                "error": error_msg
            }
        
        logger.info(f"[{trace_id}] 文档解析成功: {len(parse_result.endpoints)} 个接口")
        
        return {
            "success": True,
            "endpoints": parse_result.endpoints,
            "metadata": parse_result.metadata,
            "groups": parse_result.groups
        }
        
    except Exception as e:
        logger.error(f"[{trace_id}] 获取或解析文档失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()


@celery_app.task(bind=True)
def fetch_and_parse_document(self, task_id: int, source_type: str, source_url: str):
    """
    获取并解析文档的 Celery 任务包装器
    
    Args:
        task_id: 任务 ID
        source_type: 来源类型
        source_url: 来源 URL
        
    Returns:
        Dict: 解析结果
    """
    trace_id = get_trace_id()
    return _fetch_and_parse_document_impl(task_id, source_type, source_url, trace_id)


def _compare_and_detect_changes_impl(task_id: int, project_id: int, new_endpoints: List[Dict], trace_id: str) -> Dict[str, Any]:
    """
    对比并检测变更的实现函数
    
    Args:
        task_id: 任务 ID
        project_id: 项目 ID
        new_endpoints: 新接口列表
        trace_id: 追踪 ID
        
    Returns:
        Dict: 变更检测结果
    """
    db = next(get_db())
    
    try:
        from app.db.base import ApiDefinition, SyncTask
        from app.core.sync.change_detector import ChangeDetector
        
        # 获取同步任务
        sync_task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
        if not sync_task:
            return {"success": False, "error": "任务不存在"}
        
        # 获取现有接口定义
        existing_endpoints = db.query(ApiDefinition).filter(
            ApiDefinition.project_id == project_id
        ).all()
        
        old_endpoints = []
        for ep in existing_endpoints:
            old_endpoints.append({
                "method": ep.method,
                "path": ep.path,
                "summary": ep.summary,
                "request_schema": ep.request_schema,
                "response_schema": ep.response_schema
            })
        
        # 检测变更
        detector = ChangeDetector(db, trace_id)
        changes = detector.detect_changes(old_endpoints, new_endpoints)
        
        # 更新同步任务统计
        sync_task.total_count = changes["summary"]["unchanged_count"] + changes["summary"]["total_changes"]
        sync_task.added_count = changes["summary"]["added_count"]
        sync_task.updated_count = changes["summary"]["changed_count"]
        sync_task.deleted_count = changes["summary"]["removed_count"]
        sync_task.conflict_count = changes["summary"]["changed_count"]
        sync_task.diff_data = changes
        sync_task.progress = 50
        db.commit()
        
        logger.info(f"[{trace_id}] 变更检测完成: {changes['summary']}")
        
        return {
            "success": True,
            "changes": changes
        }
        
    except Exception as e:
        logger.error(f"[{trace_id}] 变更检测失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()


@celery_app.task(bind=True)
def compare_and_detect_changes(self, task_id: int, project_id: int, new_endpoints: List[Dict]):
    """
    对比并检测变更的 Celery 任务包装器
    
    Args:
        task_id: 任务 ID
        project_id: 项目 ID
        new_endpoints: 新接口列表
        
    Returns:
        Dict: 变更检测结果
    """
    trace_id = get_trace_id()
    return _compare_and_detect_changes_impl(task_id, project_id, new_endpoints, trace_id)


def _scan_impact_and_report_impl(task_id: int, project_id: int, user_id: int, changes: Dict, trace_id: str) -> Dict[str, Any]:
    """
    扫描影响范围并生成报告的实现函数
    
    Args:
        task_id: 任务 ID
        project_id: 项目 ID
        user_id: 用户 ID
        changes: 变更数据
        trace_id: 追踪 ID
        
    Returns:
        Dict: 影响分析结果
    """
    db = next(get_db())
    
    try:
        from app.db.base import SyncTask
        from app.core.sync.change_detector import ImpactAnalyzer
        
        # 获取同步任务
        sync_task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
        if not sync_task:
            return {"success": False, "error": "任务不存在"}
        
        # 扫描影响范围
        changed_endpoints = changes.get("changed", [])
        if not changed_endpoints:
            logger.info(f"[{trace_id}] 没有变更接口，跳过影响扫描")
            return {
                "success": True,
                "impact": {
                    "affected_cases": [],
                    "affected_scenarios": [],
                    "summary": {
                        "affected_case_count": 0,
                        "affected_scenario_count": 0,
                        "total_affected": 0
                    }
                }
            }
        
        analyzer = ImpactAnalyzer(db, trace_id)
        impact = analyzer.scan_impact(changed_endpoints, project_id, user_id)
        
        # 保存影响分析结果
        sync_task.impact_analysis = impact
        sync_task.progress = 80
        db.commit()
        
        logger.info(f"[{trace_id}] 影响扫描完成: {impact['summary']}")
        
        return {
            "success": True,
            "impact": impact
        }
        
    except Exception as e:
        logger.error(f"[{trace_id}] 影响扫描失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()


@celery_app.task(bind=True)
def scan_impact_and_report(self, task_id: int, project_id: int, user_id: int, changes: Dict):
    """
    扫描影响范围并生成报告的 Celery 任务包装器
    
    Args:
        task_id: 任务 ID
        project_id: 项目 ID
        user_id: 用户 ID
        changes: 变更数据
        
    Returns:
        Dict: 影响分析结果
    """
    trace_id = get_trace_id()
    return _scan_impact_and_report_impl(task_id, project_id, user_id, changes, trace_id)