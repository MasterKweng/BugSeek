"""CI/CD trigger endpoints for scenario execution."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.trace import get_trace_id
from app.dependencies import get_db
from app.execution.engine import ScenarioExecutor, create_scenario_execution
from app.platform.db.base import (
    ApiScenario,
    Environment,
    TestExecution,
    TestExecutionResult,
    User,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class TriggerScenarioRequest(BaseModel):
    environment_id: int = Field(..., description="Environment id")
    async_mode: bool = Field(False, description="Whether to run asynchronously")
    callback_url: Optional[str] = Field(None, description="Optional callback url")


def _verify_api_key(api_key: Optional[str], db: Session) -> User:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    raw_token = api_key.replace("Bearer ", "")
    try:
        user_id = int(raw_token.split(":", 1)[0])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return user


@router.post("/scenarios/{scenario_id}/trigger", response_model=ApiResponse)
async def trigger_scenario(
    scenario_id: int,
    request: TriggerScenarioRequest,
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    token: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    trace_id = get_trace_id()
    logger.info("[%s] trigger scenario: scenario_id=%s", trace_id, scenario_id)

    _verify_api_key(api_key or token, db)

    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario not found: {scenario_id}",
        )

    environment = db.query(Environment).filter(Environment.id == request.environment_id).first()
    if not environment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment not found: {request.environment_id}",
        )

    if environment.project_id != scenario.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Environment project mismatch",
        )

    try:
        if request.async_mode:
            from app.celery.tasks import execute_scenario_task

            execution = create_scenario_execution(
                db=db,
                scenario=scenario,
                environment_id=request.environment_id,
                operator_user_id=None,
                triggered_by="jenkins",
                webhook_url=request.callback_url,
            )

            celery_task = execute_scenario_task.apply_async(
                args=[execution.id, scenario_id, request.environment_id],
                kwargs={"callback_url": request.callback_url},
            )

            return ApiResponse(
                code=0,
                message="Async task submitted",
                data={
                    "execution_id": execution.id,
                    "scenario_id": scenario_id,
                    "status": execution.status,
                    "result_status": execution.result_status,
                    "success": False,
                    "async_mode": True,
                    "callback_url": request.callback_url,
                    "celery_task_id": celery_task.id,
                    "started_at": execution.started_at.isoformat() if execution.started_at else None,
                },
            )

        executor = ScenarioExecutor()
        execution = create_scenario_execution(
            db=db,
            scenario=scenario,
            environment_id=request.environment_id,
            operator_user_id=None,
            triggered_by="jenkins",
        )
        result = await executor.execute_scenario(
            scenario_id=scenario_id,
            graph_data=None,
            variables={},
            environment_id=request.environment_id,
            version_id=scenario.version_id,
            execution_id=execution.id,
            db=db,
            triggered_by="jenkins",
        )

        code = 0 if result["success"] else 1
        return ApiResponse(
            code=code,
            message="Execution completed" if code == 0 else "Execution failed",
            data={
                "execution_id": result["execution_id"],
                "scenario_id": scenario_id,
                "status": result["status"],
                "result_status": result["result_status"],
                "success": result["success"],
                "async_mode": False,
                "summary": result["summary"],
                "error_message": result.get("error_message"),
                "results": result["results"],
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[%s] trigger scenario failed: %s", trace_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scenario execution failed: {exc}",
        ) from exc


@router.get("/scenarios/{scenario_id}/trigger/{execution_id}", response_model=ApiResponse)
async def get_trigger_result(
    scenario_id: int,
    execution_id: int,
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    trace_id = get_trace_id()
    logger.info(
        "[%s] get trigger result: scenario_id=%s, execution_id=%s",
        trace_id,
        scenario_id,
        execution_id,
    )

    _verify_api_key(api_key, db)

    execution = (
        db.query(TestExecution)
        .filter(
            TestExecution.id == execution_id,
            TestExecution.execution_type == "scenario",
            TestExecution.target_id == scenario_id,
        )
        .first()
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution not found: {execution_id}",
        )

    result_rows = (
        db.query(TestExecutionResult)
        .filter(TestExecutionResult.execution_id == execution_id)
        .order_by(TestExecutionResult.id.asc())
        .all()
    )

    payload = _serialize_execution(execution, scenario_id, result_rows)
    code = 0 if execution.status == "completed" and execution.result_status == "passed" else 1
    return ApiResponse(code=code, message=execution.status, data=payload)


@router.post("/scenarios/{scenario_id}/webhook", response_model=ApiResponse)
async def scenario_webhook(
    scenario_id: int,
    payload: Dict[str, Any],
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    environment_id = payload.get("environment_id")
    if not environment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing environment_id",
        )

    request = TriggerScenarioRequest(
        environment_id=environment_id,
        async_mode=payload.get("async_mode", False),
        callback_url=payload.get("callback_url"),
    )
    return await trigger_scenario(
        scenario_id=scenario_id,
        request=request,
        api_key=api_key,
        token=None,
        db=db,
    )


def _serialize_execution(
    execution: TestExecution,
    scenario_id: int,
    result_rows: List[TestExecutionResult],
) -> Dict[str, Any]:
    serialized_results = [
        {
            "id": row.id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "status": row.status,
            "response_time": row.response_time,
            "response_code": row.response_code,
            "request_body": row.request_body,
            "response_body": row.response_body,
            "assertion_results": row.assertion_results,
            "extracted_variables": row.extracted_variables,
            "error_message": row.error_message,
        }
        for row in result_rows
    ]

    error_message = next((item["error_message"] for item in serialized_results if item["error_message"]), None)
    return {
        "execution_id": execution.id,
        "scenario_id": scenario_id,
        "status": execution.status,
        "result_status": getattr(execution, "result_status", None),
        "success": execution.status == "completed" and getattr(execution, "result_status", None) == "passed",
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
        "duration_ms": execution.duration,
        "error_message": error_message or (((getattr(execution, "summary_json", None) or {}).get("error_message")) if isinstance(getattr(execution, "summary_json", None), dict) else None),
        "summary": {
            "total": execution.total or 0,
            "passed": execution.passed or 0,
            "failed": execution.failed or 0,
            "skipped": execution.skipped or 0,
            "duration_ms": execution.duration or 0,
            "result_status": getattr(execution, "result_status", None),
        },
        "results": serialized_results,
        "callback_status": getattr(execution, "callback_status", None),
    }
