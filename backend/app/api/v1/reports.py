"""报告生成与输出接口（V2.0 - 场景工作室）

BSK-SC-029: 报告输出接口（HTML/PDF）
BSK-SC-030: AI 根因分析注入报告

功能：
1. 生成场景执行报告
2. 支持 HTML 和 PDF 格式
3. 下载和在线查看
4. 集成 AI 根因分析
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from app.dependencies import get_db
from app.platform.db.base import TestExecution, ApiScenario, Environment
from app.core.trace import get_trace_id
from app.core.reporting.aggregator import ReportAggregator
from app.core.reporting.generator import ReportGenerator

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/scenarios/{scenario_id}/executions/{execution_id}/report")
async def get_scenario_report(
    scenario_id: int,
    execution_id: int,
    format: str = Query("html", description="报告格式（html/pdf）"),
    include_rca: bool = Query(True, description="是否包含 AI 根因分析"),
    db: Session = Depends(get_db)
):
    """
    获取场景执行报告
    
    BSK-SC-029: 报告输出接口
    BSK-SC-030: AI 根因分析注入报告
    
    Args:
        scenario_id: 场景 ID
        execution_id: 执行 ID
        format: 报告格式（html/pdf）
        include_rca: 是否包含 AI 根因分析
        db: 数据库会话
        
    Returns:
        Response: 报告内容
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 生成场景报告: scenario_id={scenario_id}, execution_id={execution_id}, format={format}, include_rca={include_rca}")
    
    # 查询执行记录
    execution = db.query(TestExecution).filter(
        TestExecution.id == execution_id,
        TestExecution.scenario_id == scenario_id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"执行记录不存在：{execution_id}"
        )
    
    # 查询场景信息
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )
    
    # 查询环境信息
    environment = db.query(Environment).filter(Environment.id == execution.environment_id).first()
    if not environment:
        raise HTTPException(
            status=status.HTTP_404_NOT_FOUND,
            detail=f"环境不存在：{execution.environment_id}"
        )
    
    # 聚合报告数据
    aggregator = ReportAggregator()
    report_data = aggregator.aggregate(
        scenario_id=scenario_id,
        scenario_name=scenario.name,
        environment_id=environment.id,
        environment_name=environment.name,
        execution_results=execution.results or [],
        context_variables=execution.context_variables or {},
        started_at=execution.started_at,
        finished_at=execution.finished_at
    )
    
    # 生成报告
    generator = ReportGenerator()
    
    if format.lower() == 'html':
        # 生成 HTML 报告（包含 RCA）
        html_content = await generator.generate_html_report(
            report_data,
            scenario_description=scenario.description,
            include_rca=include_rca
        )
        
        return Response(
            content=html_content,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename=scenario_{scenario_id}_execution_{execution_id}.html"
            }
        )
    elif format.lower() == 'pdf':
        # 生成 PDF 报告
        pdf_content = generator.generate_pdf_report(report_data)
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=scenario_{scenario_id}_execution_{execution_id}.pdf"
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的格式：{format}"
        )


@router.get("/scenarios/{scenario_id}/executions/{execution_id}/report/summary")
async def get_report_summary(
    scenario_id: int,
    execution_id: int,
    db: Session = Depends(get_db)
):
    """
    获取报告摘要
    
    Args:
        scenario_id: 场景 ID
        execution_id: 执行 ID
        db: 数据库会话
        
    Returns:
        dict: 报告摘要
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 获取报告摘要: scenario_id={scenario_id}, execution_id={execution_id}")
    
    # 查询执行记录
    execution = db.query(TestExecution).filter(
        TestExecution.id == execution_id,
        TestExecution.scenario_id == scenario_id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"执行记录不存在：{execution_id}"
        )
    
    # 查询场景信息
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )
    
    # 查询环境信息
    environment = db.query(Environment).filter(Environment.id == execution.environment_id).first()
    if not environment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境不存在：{execution.environment_id}"
        )
    
    # 聚合报告数据
    aggregator = ReportAggregator()
    report_data = aggregator.aggregate(
        scenario_id=scenario_id,
        scenario_name=scenario.name,
        environment_id=environment.id,
        environment_name=environment.name,
        execution_results=execution.results or [],
        context_variables=execution.context_variables or {},
        started_at=execution.started_at,
        finished_at=execution.finished_at
    )
    
    # 生成摘要
    summary = aggregator.generate_report_summary(report_data)
    
    return {
        "code": 0,
        "message": "success",
        "data": summary
    }


@router.get("/scenarios/{scenario_id}/executions/{execution_id}/rca")
async def get_rca_analysis(
    scenario_id: int,
    execution_id: int,
    db: Session = Depends(get_db)
):
    """
    获取场景执行的 AI 根因分析（BSK-SC-030）
    
    Args:
        scenario_id: 场景 ID
        execution_id: 执行 ID
        db: 数据库会话
        
    Returns:
        dict: RCA 分析结果
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 获取 RCA 分析: scenario_id={scenario_id}, execution_id={execution_id}")
    
    # 查询执行记录
    execution = db.query(TestExecution).filter(
        TestExecution.id == execution_id,
        TestExecution.scenario_id == scenario_id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"执行记录不存在：{execution_id}"
        )
    
    # 查询场景信息
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )
    
    # 查询环境信息
    environment = db.query(Environment).filter(Environment.id == execution.environment_id).first()
    if not environment:
        raise HTTPException(
            status=status.HTTP_404_NOT_FOUND,
            detail=f"环境不存在：{execution.environment_id}"
        )
    
    # 聚合报告数据
    aggregator = ReportAggregator()
    report_data = aggregator.aggregate(
        scenario_id=scenario_id,
        scenario_name=scenario.name,
        environment_id=environment.id,
        environment_name=environment.name,
        execution_results=execution.results or [],
        context_variables=execution.context_variables or {},
        started_at=execution.started_at,
        finished_at=execution.finished_at
    )
    
    # 检查是否有失败节点
    if not report_data.summary.failed_node_keys:
        return {
            "code": 0,
            "message": "success",
            "data": {
                "has_failures": False,
                "message": "场景执行成功，无需进行根因分析"
            }
        }
    
    # 生成 RCA 分析
    generator = ReportGenerator()
    rca_result = await generator.generate_rca_analysis(
        report_data,
        scenario_description=scenario.description
    )
    
    if not rca_result:
        return {
            "code": 1,
            "message": "RCA 分析失败",
            "data": None
        }
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "has_failures": True,
            "rca_result": rca_result
        }
    }