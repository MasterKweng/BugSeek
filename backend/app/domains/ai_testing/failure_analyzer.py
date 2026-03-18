"""Failure analyzer."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.service import AIService
from app.dependencies import get_db
from app.platform.db.base import TestExecution, TestExecutionResult
from .scenario_generator import _parse_ai_response
from .schemas import FailureReport


class FailureAnalyzer:
    async def analyze(self, project_id: Optional[int], payload: Dict[str, Any]) -> FailureReport:
        enriched = dict(payload or {})
        execution_id = enriched.get("execution_id")
        if execution_id:
            self._attach_execution_context(execution_id, enriched)

        base_report = self._build_rule_based_report(enriched)

        try:
            ai_service = AIService()
            result = await ai_service.execute(
                task_type="scenario_failure_rca",
                project_id=project_id,
                input_data=enriched,
            )
            if result.get("success"):
                ai_payload = _parse_ai_response(result.get("result"))
                if isinstance(ai_payload, dict):
                    merged = {
                        "failure_type": ai_payload.get("failure_type") or base_report.failure_type,
                        "root_cause": ai_payload.get("root_cause") or base_report.root_cause,
                        "suggested_fix": ai_payload.get("suggested_fix") or base_report.suggested_fix,
                        "confidence": ai_payload.get("confidence") or base_report.confidence,
                        "evidence": base_report.evidence,
                    }
                    return FailureReport(**merged)
        except Exception:
            pass

        return base_report

    def _attach_execution_context(self, execution_id: int, payload: Dict[str, Any]) -> None:
        db: Session = next(get_db())
        try:
            execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
            if not execution:
                return
            results = (
                db.query(TestExecutionResult)
                .filter(TestExecutionResult.execution_id == execution_id)
                .all()
            )
            payload["execution"] = {
                "id": execution.id,
                "status": execution.status,
                "duration": execution.duration,
                "total": execution.total,
                "passed": execution.passed,
                "failed": execution.failed,
            }
            payload["results"] = [
                {
                    "target_id": r.target_id,
                    "status": r.status,
                    "response_code": r.response_code,
                    "response_body": r.response_body,
                    "error_message": r.error_message,
                    "assertion_results": r.assertion_results,
                    "extracted_variables": r.extracted_variables,
                }
                for r in results
            ]
        finally:
            db.close()

    def _build_rule_based_report(self, payload: Dict[str, Any]) -> FailureReport:
        results = payload.get("results")
        failed_result = self._pick_failed_result(results)
        if failed_result:
            report = self._analyze_result_failure(failed_result)
            if report:
                return report

        execution = payload.get("execution") or {}
        if execution.get("status") == "failed":
            return FailureReport(
                failure_type="scenario_failed",
                root_cause="场景执行失败，但缺少更细粒度的失败明细。",
                suggested_fix="补充节点级执行结果和断言结果，便于继续定位问题。",
                confidence=0.45,
                evidence={"execution": execution},
            )

        raw_error = payload.get("error_message") or payload.get("error")
        if raw_error:
            return self._report_from_error(str(raw_error), {"payload": payload})

        return FailureReport(
            failure_type="unknown",
            root_cause="未识别到明确失败信号。",
            suggested_fix="补充执行结果、响应码、断言结果或错误日志后重试分析。",
            confidence=0.2,
            evidence={"payload": payload},
        )

    def _pick_failed_result(self, results: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(results, list):
            return None
        for item in results:
            if not isinstance(item, dict):
                continue
            if str(item.get("status")).lower() not in ("passed", "completed", "success"):
                return item
            if item.get("error_message"):
                return item
            code = item.get("response_code")
            if isinstance(code, int) and code >= 400:
                return item
            if self._extract_failed_assertion(item.get("assertion_results")):
                return item
        return None

    def _analyze_result_failure(self, result: Dict[str, Any]) -> Optional[FailureReport]:
        error_message = result.get("error_message")
        response_code = result.get("response_code")
        failed_assertion = self._extract_failed_assertion(result.get("assertion_results"))

        if error_message:
            return self._report_from_error(str(error_message), {"result": result})

        if isinstance(response_code, int) and response_code >= 400:
            return FailureReport(
                failure_type="status_code_abnormal",
                root_cause=f"接口返回异常状态码 {response_code}。",
                suggested_fix="检查请求参数、测试数据和接口预期状态码，确认是否应允许该响应码。",
                confidence=0.9,
                evidence={"response_code": response_code, "result": result},
            )

        if failed_assertion:
            field = failed_assertion.get("field") or failed_assertion.get("property") or failed_assertion.get("source")
            operator = failed_assertion.get("operator")
            return FailureReport(
                failure_type="assertion_failed",
                root_cause=f"断言失败：字段 {field} 未满足 {operator} 条件。",
                suggested_fix="检查断言规则与接口真实响应是否仍一致，必要时更新断言或修复接口返回。",
                confidence=0.88,
                evidence={"failed_assertion": failed_assertion, "result": result},
            )

        return None

    def _report_from_error(self, error_message: str, evidence: Dict[str, Any]) -> FailureReport:
        normalized = error_message.lower()
        if "missing placeholders" in normalized or "missing variable" in normalized or "missing placeholders" in normalized:
            return FailureReport(
                failure_type="variable_missing",
                root_cause=error_message,
                suggested_fix="补充前置节点提取规则，或在执行前显式注入缺失变量。",
                confidence=0.95,
                evidence=evidence,
            )
        if "timeout" in normalized or "connect" in normalized or "connection" in normalized:
            return FailureReport(
                failure_type="request_send_failed",
                root_cause=error_message,
                suggested_fix="检查环境连通性、鉴权配置和接口可用性，必要时提高超时时间。",
                confidence=0.9,
                evidence=evidence,
            )
        if "upstream" in normalized or "dependency" in normalized:
            return FailureReport(
                failure_type="upstream_dependency_failed",
                root_cause=error_message,
                suggested_fix="优先修复上游节点失败，再重新执行当前场景。",
                confidence=0.82,
                evidence=evidence,
            )
        return FailureReport(
            failure_type="execution_error",
            root_cause=error_message,
            suggested_fix="根据错误日志补充上下文并定位执行链路中的异常点。",
            confidence=0.65,
            evidence=evidence,
        )

    def _extract_failed_assertion(self, assertion_results: Any) -> Optional[Dict[str, Any]]:
        if isinstance(assertion_results, dict):
            assertions = assertion_results.get("assertions")
            if isinstance(assertions, list):
                for item in assertions:
                    if isinstance(item, dict) and not item.get("passed", False):
                        return item
            if assertion_results.get("passed") is False:
                return assertion_results
        if isinstance(assertion_results, list):
            for item in assertion_results:
                if isinstance(item, dict) and not item.get("passed", False):
                    return item
        return None
