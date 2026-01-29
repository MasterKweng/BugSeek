"""Celery 异步任务"""
from typing import List
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
]