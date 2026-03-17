"""Celery tasks for async scenario execution."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from ._common import *


@celery_app.task(bind=True, name="app.celery.tasks.execute_scenario_task")
def execute_scenario_task(
    self,
    execution_id: int,
    scenario_id: int,
    environment_id: int,
    callback_url: Optional[str] = None,
):
    trace_id = get_trace_id()
    db: Session = SessionLocal()

    try:
        logger.info(
            "[%s] celery scenario task start: execution_id=%s, scenario_id=%s, environment_id=%s",
            trace_id,
            execution_id,
            scenario_id,
            environment_id,
        )

        from app.platform.db.base import TestExecution

        execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
        if not execution:
            logger.error("[%s] execution not found: %s", trace_id, execution_id)
            return {"success": False, "error": "execution not found"}

        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)
        db.commit()

        from app.execution.engine import ScenarioExecutor

        executor = ScenarioExecutor()
        result = asyncio.run(
            executor.execute_scenario(
                scenario_id=scenario_id,
                graph_data=None,
                variables={},
                environment_id=environment_id,
                db=db,
            )
        )

        execution.status = result["status"]
        execution.finished_at = datetime.now(timezone.utc)
        execution.duration = result["summary"].get("duration_ms", 0)
        execution.total = result["summary"].get("total", 0)
        execution.passed = result["summary"].get("passed", 0)
        execution.failed = result["summary"].get("failed", 0)
        execution.skipped = result["summary"].get("skipped", 0)
        if callback_url:
            execution.webhook_url = callback_url
            execution.callback_status = "pending"
        db.commit()

        if callback_url:
            try:
                import httpx

                callback_payload = {
                    "execution_id": execution_id,
                    "scenario_id": scenario_id,
                    "status": result["status"],
                    "summary": result["summary"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                response = httpx.post(callback_url, json=callback_payload, timeout=30.0)
                execution.callback_status = "success" if response.is_success else "failed"
                db.commit()
            except Exception as callback_error:
                logger.warning("[%s] callback failed: %s", trace_id, callback_error)
                execution.callback_status = "failed"
                db.commit()

        return result
    except Exception as exc:
        logger.error("[%s] celery scenario task failed: %s", trace_id, exc, exc_info=True)
        try:
            from app.platform.db.base import TestExecution

            execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
            if execution:
                execution.status = "failed"
                execution.finished_at = datetime.now(timezone.utc)
                execution.callback_status = "failed" if callback_url else execution.callback_status
                db.commit()
        except Exception:
            pass

        return {"success": False, "error": str(exc)}
    finally:
        db.close()
