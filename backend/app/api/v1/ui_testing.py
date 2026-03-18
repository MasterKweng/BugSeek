"""UI automation API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Optional

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.dependencies import get_db
from app.domains.ui_testing.schemas import UITestExecutionRequest
from app.domains.ui_testing.service import UIExecutionService
from app.platform.db.base import User

router = APIRouter(prefix="/ui-testing")


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


@router.post("/executions", response_model=ApiResponse)
async def create_ui_execution(
    request: UITestExecutionRequest,
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_project_id = project_id or get_current_project_id(db, current_user)
    if not resolved_project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少项目上下文")

    result = await UIExecutionService(db).run_and_persist(resolved_project_id, request)
    return ApiResponse(message="UI 自动化执行完成", data=result.model_dump())


@router.get("/executions/{execution_id}", response_model=ApiResponse)
async def get_ui_execution(
    execution_id: int,
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_project_id = project_id or get_current_project_id(db, current_user)
    if not resolved_project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少项目上下文")

    result = UIExecutionService(db).get_execution_detail(resolved_project_id, execution_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"UI 执行记录不存在：{execution_id}")

    return ApiResponse(data=result.model_dump())
