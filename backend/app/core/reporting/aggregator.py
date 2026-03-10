"""
报告聚合服务

BSK-SC-028: 报告聚合服务

功能：
1. 聚合场景执行结果
2. 生成执行摘要
3. 收集失败节点信息
4. 提取关键指标
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class NodeResult:
    """节点执行结果"""
    node_key: str
    node_name: str
    node_type: str
    status: str  # passed/failed
    response_time: int
    response_code: int
    request_body: Optional[Dict[str, Any]] = None
    response_body: Optional[Dict[str, Any]] = None
    assertion_results: Optional[Dict[str, Any]] = None
    extracted_variables: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class ExecutionSummary:
    """执行摘要"""
    scenario_id: int
    scenario_name: str
    environment_id: int
    environment_name: str
    status: str  # completed/failed/running
    total_nodes: int
    passed_nodes: int
    failed_nodes: int
    skipped_nodes: int
    total_duration_ms: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    failed_node_keys: List[str] = field(default_factory=list)
    rca_available: bool = False


@dataclass
class ReportData:
    """报告数据"""
    summary: ExecutionSummary
    node_results: List[NodeResult]
    context_variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReportAggregator:
    """报告聚合器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def aggregate(
        self,
        scenario_id: int,
        scenario_name: str,
        environment_id: int,
        environment_name: str,
        execution_results: List[Dict[str, Any]],
        context_variables: Dict[str, Any],
        started_at: datetime,
        finished_at: Optional[datetime] = None
    ) -> ReportData:
        """
        聚合执行结果
        
        Args:
            scenario_id: 场景 ID
            scenario_name: 场景名称
            environment_id: 环境 ID
            environment_name: 环境名称
            execution_results: 执行结果列表
            context_variables: 上下文变量
            started_at: 开始时间
            finished_at: 结束时间
            
        Returns:
            ReportData: 聚合的报告数据
        """
        logger.info(f"开始聚合报告数据: scenario_id={scenario_id}")
        
        # 解析节点结果
        node_results = []
        for result in execution_results:
            node_result = NodeResult(
                node_key=result.get('node_key', ''),
                node_name=result.get('node_name', ''),
                node_type=result.get('node_type', ''),
                status=result.get('status', 'unknown'),
                response_time=result.get('response_time', 0),
                response_code=result.get('response_code', 0),
                request_body=result.get('request_body'),
                response_body=result.get('response_body'),
                assertion_results=result.get('assertion_results'),
                extracted_variables=result.get('extracted_variables'),
                error_message=result.get('error_message')
            )
            node_results.append(node_result)
        
        # 计算摘要统计
        total_nodes = len(node_results)
        passed_nodes = sum(1 for n in node_results if n.status == 'passed')
        failed_nodes = sum(1 for n in node_results if n.status == 'failed')
        skipped_nodes = total_nodes - passed_nodes - failed_nodes
        total_duration_ms = sum(n.response_time for n in node_results)
        
        # 判断整体状态
        if failed_nodes > 0:
            status = 'failed'
        else:
            status = 'completed'
        
        # 收集失败节点
        failed_node_keys = [n.node_key for n in node_results if n.status == 'failed']
        
        # 判断是否可以进行 RCA（有失败节点且有错误信息）
        rca_available = any(n.error_message for n in node_results if n.status == 'failed')
        
        # 创建执行摘要
        summary = ExecutionSummary(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            environment_id=environment_id,
            environment_name=environment_name,
            status=status,
            total_nodes=total_nodes,
            passed_nodes=passed_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            total_duration_ms=total_duration_ms,
            started_at=started_at,
            finished_at=finished_at,
            failed_node_keys=failed_node_keys,
            rca_available=rca_available
        )
        
        # 创建报告数据
        report_data = ReportData(
            summary=summary,
            node_results=node_results,
            context_variables=context_variables,
            metadata={
                'generated_at': datetime.now().isoformat(),
                'node_count': total_nodes,
                'pass_rate': (passed_nodes / total_nodes * 100) if total_nodes > 0 else 0
            }
        )
        
        logger.info(
            f"报告聚合完成: "
            f"status={status}, passed={passed_nodes}, failed={failed_nodes}, "
            f"duration={total_duration_ms}ms"
        )
        
        return report_data
    
    def generate_report_summary(self, report_data: ReportData) -> Dict[str, Any]:
        """
        生成报告摘要
        
        Args:
            report_data: 报告数据
            
        Returns:
            Dict: 报告摘要
        """
        summary = report_data.summary
        
        return {
            'scenario': {
                'id': summary.scenario_id,
                'name': summary.scenario_name,
            },
            'environment': {
                'id': summary.environment_id,
                'name': summary.environment_name,
            },
            'execution': {
                'status': summary.status,
                'total_nodes': summary.total_nodes,
                'passed_nodes': summary.passed_nodes,
                'failed_nodes': summary.failed_nodes,
                'skipped_nodes': summary.skipped_nodes,
                'pass_rate': report_data.metadata.get('pass_rate', 0),
                'total_duration_ms': summary.total_duration_ms,
                'started_at': summary.started_at.isoformat(),
                'finished_at': summary.finished_at.isoformat() if summary.finished_at else None,
            },
            'failed_nodes': summary.failed_node_keys,
            'rca_available': summary.rca_available,
            'metadata': report_data.metadata
        }
    
    def extract_failure_context(self, report_data: ReportData) -> Dict[str, Any]:
        """
        提取失败节点上下文
        
        Args:
            report_data: 报告数据
            
        Returns:
            Dict: 失败上下文
        """
        failure_context = {
            'failed_nodes': [],
            'total_failed': len(report_data.summary.failed_node_keys)
        }
        
        for node in report_data.node_results:
            if node.status == 'failed':
                failure_context['failed_nodes'].append({
                    'node_key': node.node_key,
                    'node_name': node.node_name,
                    'error_message': node.error_message,
                    'response_code': node.response_code,
                    'response_body': node.response_body,
                    'assertion_results': node.assertion_results,
                    'request_body': node.request_body,
                    'extracted_variables': node.extracted_variables,
                })
        
        return failure_context