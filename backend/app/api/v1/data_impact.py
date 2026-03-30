"""Data impact analysis API."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from app.dependencies import get_db, engine as db_engine
from app.domains.data_impact.engine import DataImpactEngine
from app.domains.data_impact.impact_repository import ImpactRepository
from app.platform.db.base import TableImpact, FieldImpact
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class ImpactExecutionStartRequest(BaseModel):
    execution_id: str = Field(..., description="Execution ID")
    api_id: int = Field(..., description="API ID")


class SnapshotCreateRequest(BaseModel):
    table_name: str = Field(..., description="Table name")
    data_json: List[Dict[str, Any]] = Field(..., description="Snapshot rows")


class AnalyzeRequest(BaseModel):
    api_id: Optional[int] = Field(None, description="API ID (optional)")
    include_assertions: bool = Field(False, description="Include assertion suggestions")


class LineageBuildRequest(BaseModel):
    definition_id: int = Field(..., description="API definition ID")
    execution_id: Optional[str] = Field(None, description="Execution ID for SQL lineage extraction")
    workspace_root: Optional[str] = Field(None, description="Workspace root for mapper/code scanning")
    version_id: Optional[int] = Field(None, description="Version ID")
    max_files: int = Field(200, description="Maximum files to scan from workspace")


@router.get("/impact/api/{api_id}", response_model=ApiResponse)
def get_impacts_by_api(api_id: int, db: Session = Depends(get_db)):
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] Query api impacts: api_id={api_id}")
    repo = ImpactRepository(db)
    impacts = repo.get_impacts_by_api(api_id)
    return ApiResponse(
        data={
            "api_id": api_id,
            "items": [
                {
                    "table_name": impact.table_name,
                    "confidence": impact.confidence,
                    "updated_at": impact.updated_at.isoformat() if impact.updated_at else None,
                }
                for impact in impacts
            ],
        }
    )


@router.get("/impact/execution/{execution_id}", response_model=ApiResponse)
def get_impacts_by_execution(execution_id: str, db: Session = Depends(get_db)):
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] Query execution impacts: execution_id={execution_id}")
    repo = ImpactRepository(db)
    table_impacts = repo.get_impacts_by_execution(execution_id)
    table_ids = [impact.id for impact in table_impacts]
    field_impacts = repo.get_field_impacts(table_ids)

    field_map: Dict[int, List[FieldImpact]] = {}
    for field in field_impacts:
        field_map.setdefault(field.table_impact_id, []).append(field)

    return ApiResponse(
        data={
            "execution_id": execution_id,
            "tables": [
                {
                    "id": impact.id,
                    "api_id": impact.api_id,
                    "table_name": impact.table_name,
                    "operation": impact.operation,
                    "row_count": impact.row_count,
                    "fields": [
                        {
                            "field_name": field.field_name,
                            "old_value": field.old_value,
                            "new_value": field.new_value,
                            "change_type": field.change_type,
                        }
                        for field in field_map.get(impact.id, [])
                    ],
                }
                for impact in table_impacts
            ],
        }
    )


@router.post("/impact/execution/start", response_model=ApiResponse)
def start_execution(request: ImpactExecutionStartRequest, db: Session = Depends(get_db)):
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] Start impact execution: {request.execution_id}")
    engine = DataImpactEngine(db, db_engine)
    result = engine.start_execution(request.execution_id, request.api_id)
    return ApiResponse(data=result)


@router.post("/impact/execution/{execution_id}/snapshot", response_model=ApiResponse)
def record_snapshot(execution_id: str, request: SnapshotCreateRequest, db: Session = Depends(get_db)):
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] Record snapshot: execution_id={execution_id} table={request.table_name}")
    engine = DataImpactEngine(db, db_engine)
    engine.record_snapshot(execution_id, request.table_name, request.data_json)
    return ApiResponse(data={"execution_id": execution_id, "table_name": request.table_name})


@router.post("/impact/execution/{execution_id}/analyze", response_model=ApiResponse)
def analyze_execution(execution_id: str, request: AnalyzeRequest, db: Session = Depends(get_db)):
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] Analyze impact: execution_id={execution_id}")
    engine = DataImpactEngine(db, db_engine)
    try:
        result = engine.analyze(
            execution_id,
            request.api_id,
            include_assertions=request.include_assertions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(data=result)


@router.post("/impact/lineage/build", response_model=ApiResponse)
def build_lineage_assets(request: LineageBuildRequest, db: Session = Depends(get_db)):
    trace_id = get_trace_id()
    logger.info(
        f"[{trace_id}] Build lineage assets: definition_id={request.definition_id} execution_id={request.execution_id}"
    )
    engine = DataImpactEngine(db, db_engine)
    try:
        result = engine.build_lineage_assets(
            definition_id=request.definition_id,
            execution_id=request.execution_id,
            workspace_root=request.workspace_root,
            version_id=request.version_id,
            max_files=request.max_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(data=result)


@router.post("/impact/execution/{execution_id}/finish", response_model=ApiResponse)
def finish_execution(execution_id: str, db: Session = Depends(get_db)):
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] Finish impact execution: execution_id={execution_id}")
    engine = DataImpactEngine(db, db_engine)
    engine.end_execution(execution_id)
    return ApiResponse(data={"execution_id": execution_id, "status": "completed"})
