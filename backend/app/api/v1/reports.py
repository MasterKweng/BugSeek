"""报告生成与输出接口（V2.0 - 场景工作室）

BSK-SC-029: 报告输出接口（HTML/PDF）
BSK-SC-030: AI 根因分析注入报告
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.reporting.aggregator import ReportAggregator, ReportData
from app.core.reporting.generator import ReportGenerator
from app.core.trace import get_trace_id
from app.dependencies import get_db
from app.platform.db.base import ApiScenario, Environment, ScenarioNode, TestExecution, TestExecutionResult

router = APIRouter()
logger = logging.getLogger(__name__)


def _unwrap_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and set(payload.keys()) == {"raw"}:
        return payload.get("raw")
    return payload


def _load_report_context(db: Session, scenario_id: int, execution_id: int) -> Tuple[ApiScenario, TestExecution, Environment, ReportData]:
    execution = db.query(TestExecution).filter(
        TestExecution.id == execution_id,
        TestExecution.target_id == scenario_id,
        TestExecution.execution_type == "scenario",
    ).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在：{execution_id}")

    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"场景不存在：{scenario_id}")

    environment = db.query(Environment).filter(Environment.id == execution.environment_id).first()
    if not environment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"环境不存在：{execution.environment_id}")

    result_rows = db.query(TestExecutionResult).filter(
        TestExecutionResult.execution_id == execution_id
    ).order_by(TestExecutionResult.id.asc()).all()

    node_ids = [row.target_id for row in result_rows if row.target_type == "scenario_node" and row.target_id]
    node_map = {
        node.id: node
        for node in db.query(ScenarioNode).filter(ScenarioNode.id.in_(node_ids)).all()
    } if node_ids else {}

    execution_results: List[Dict[str, Any]] = []
    for row in result_rows:
        scenario_node = node_map.get(row.target_id)
        execution_results.append({
            "node_key": scenario_node.node_key if scenario_node else f"node_{row.target_id}",
            "node_name": scenario_node.node_name if scenario_node and scenario_node.node_name else f"Node {row.target_id}",
            "node_type": scenario_node.node_type if scenario_node else row.target_type,
            "status": row.status,
            "response_time": row.response_time or 0,
            "response_code": row.response_code or 0,
            "request_body": _unwrap_payload(row.request_body),
            "response_body": _unwrap_payload(row.response_body),
            "assertion_results": row.assertion_results,
            "extracted_variables": row.extracted_variables,
            "error_message": row.error_message,
        })

    report_data = ReportAggregator().aggregate(
        scenario_id=scenario_id,
        scenario_name=scenario.name,
        environment_id=environment.id,
        environment_name=environment.name,
        execution_results=execution_results,
        context_variables={},
        started_at=execution.started_at or datetime.now(timezone.utc),
        finished_at=execution.finished_at,
    )
    return scenario, execution, environment, report_data


@router.get("/scenarios/{scenario_id}/executions/{execution_id}/report")
async def get_scenario_report(
    scenario_id: int,
    execution_id: int,
    format: str = Query("html", description="报告格式（html/pdf）"),
    include_rca: bool = Query(True, description="是否包含 AI 根因分析"),
    db: Session = Depends(get_db),
):
    trace_id = get_trace_id()
    logger.info(
        "[%s] 生成场景报告: scenario_id=%s, execution_id=%s, format=%s, include_rca=%s",
        trace_id,
        scenario_id,
        execution_id,
        format,
        include_rca,
    )

    scenario, _, _, report_data = _load_report_context(db, scenario_id, execution_id)
    generator = ReportGenerator()

    if format.lower() == "html":
        html_content = await generator.generate_html_report(
            report_data,
            scenario_description=scenario.description,
            include_rca=include_rca,
        )
        return Response(
            content=html_content,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=scenario_{scenario_id}_execution_{execution_id}.html"},
        )

    if format.lower() == "pdf":
        pdf_content = await generator.generate_pdf_report(
            report_data,
            scenario_description=scenario.description,
            include_rca=include_rca,
        )
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=scenario_{scenario_id}_execution_{execution_id}.pdf"},
        )

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的格式：{format}")


@router.get("/scenarios/{scenario_id}/executions/{execution_id}/report/summary")
async def get_report_summary(
    scenario_id: int,
    execution_id: int,
    db: Session = Depends(get_db),
):
    trace_id = get_trace_id()
    logger.info("[%s] 获取报告摘要: scenario_id=%s, execution_id=%s", trace_id, scenario_id, execution_id)

    _, _, _, report_data = _load_report_context(db, scenario_id, execution_id)
    summary = ReportAggregator().generate_report_summary(report_data)
    return {"code": 0, "message": "success", "data": summary}


@router.get("/scenarios/{scenario_id}/executions/{execution_id}/rca")
async def get_rca_analysis(
    scenario_id: int,
    execution_id: int,
    db: Session = Depends(get_db),
):
    trace_id = get_trace_id()
    logger.info("[%s] 获取 RCA 分析: scenario_id=%s, execution_id=%s", trace_id, scenario_id, execution_id)

    scenario, _, _, report_data = _load_report_context(db, scenario_id, execution_id)
    if not report_data.summary.failed_node_keys:
        return {
            "code": 0,
            "message": "success",
            "data": {"has_failures": False, "message": "场景执行成功，无需进行根因分析"},
        }

    generator = ReportGenerator()
    rca_result = await generator.generate_rca_analysis(report_data, scenario_description=scenario.description)
    if not rca_result:
        return {"code": 1, "message": "RCA 分析失败", "data": None}

    return {"code": 0, "message": "success", "data": {"has_failures": True, "rca_result": rca_result}}
