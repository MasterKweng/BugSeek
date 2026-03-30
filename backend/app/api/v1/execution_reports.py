from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.dependencies import get_db
from app.platform.db.base import User
from app.services.execution_query_service import _validate_environment, _validate_version
from app.services.execution_report_service import (
    get_execution_report_environment_comparison_data,
    get_execution_report_failures_data,
    get_execution_report_performance_data,
    get_execution_report_summary_data,
    get_execution_report_trends_data,
    get_execution_report_version_comparison_data,
)

router = APIRouter()


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


@router.get("/reports/executions/summary", response_model=ApiResponse)
async def get_execution_report_summary(
    version_id: Optional[int] = Query(None),
    environment_id: Optional[int] = Query(None),
    started_after: Optional[datetime] = Query(None),
    started_before: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _validate_version(db, project_id, version_id)
    _validate_environment(db, project_id, environment_id)
    return ApiResponse(
        data=get_execution_report_summary_data(
            db=db,
            project_id=project_id,
            version_id=version_id,
            environment_id=environment_id,
            started_after=started_after,
            started_before=started_before,
        )
    )


@router.get("/reports/executions/trends", response_model=ApiResponse)
async def get_execution_report_trends(
    group_by: str = Query("day", pattern="^(day|week|month)$"),
    version_id: Optional[int] = Query(None),
    environment_id: Optional[int] = Query(None),
    started_after: Optional[datetime] = Query(None),
    started_before: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _validate_version(db, project_id, version_id)
    _validate_environment(db, project_id, environment_id)
    return ApiResponse(
        data=get_execution_report_trends_data(
            db=db,
            project_id=project_id,
            group_by=group_by,
            version_id=version_id,
            environment_id=environment_id,
            started_after=started_after,
            started_before=started_before,
        )
    )


@router.get("/reports/executions/failures", response_model=ApiResponse)
async def get_execution_report_failures(
    version_id: Optional[int] = Query(None),
    environment_id: Optional[int] = Query(None),
    started_after: Optional[datetime] = Query(None),
    started_before: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _validate_version(db, project_id, version_id)
    _validate_environment(db, project_id, environment_id)
    return ApiResponse(
        data=get_execution_report_failures_data(
            db=db,
            project_id=project_id,
            version_id=version_id,
            environment_id=environment_id,
            started_after=started_after,
            started_before=started_before,
        )
    )


@router.get("/reports/executions/performance", response_model=ApiResponse)
async def get_execution_report_performance(
    version_id: Optional[int] = Query(None),
    environment_id: Optional[int] = Query(None),
    started_after: Optional[datetime] = Query(None),
    started_before: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _validate_version(db, project_id, version_id)
    _validate_environment(db, project_id, environment_id)
    return ApiResponse(
        data=get_execution_report_performance_data(
            db=db,
            project_id=project_id,
            version_id=version_id,
            environment_id=environment_id,
            started_after=started_after,
            started_before=started_before,
        )
    )


@router.get("/reports/executions/environment-comparison", response_model=ApiResponse)
async def get_execution_report_environment_comparison(
    version_id: Optional[int] = Query(None),
    started_after: Optional[datetime] = Query(None),
    started_before: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _validate_version(db, project_id, version_id)
    return ApiResponse(
        data=get_execution_report_environment_comparison_data(
            db=db,
            project_id=project_id,
            version_id=version_id,
            started_after=started_after,
            started_before=started_before,
        )
    )


@router.get("/reports/executions/version-comparison", response_model=ApiResponse)
async def get_execution_report_version_comparison(
    environment_id: Optional[int] = Query(None),
    started_after: Optional[datetime] = Query(None),
    started_before: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _validate_environment(db, project_id, environment_id)
    return ApiResponse(
        data=get_execution_report_version_comparison_data(
            db=db,
            project_id=project_id,
            environment_id=environment_id,
            started_after=started_after,
            started_before=started_before,
        )
    )
