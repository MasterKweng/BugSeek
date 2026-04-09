"""
Execution engine (scenario orchestration).
"""

import asyncio
import time
import json
import logging
import copy
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.dependencies import SessionLocal
from app.platform.db.base import (
    ApiCase, ApiDefinition, ApiScenario, ScenarioNode, Environment,
    TestExecution, TestExecutionResult, AuthConfig
)
from app.core.trace import get_trace_id
from app.execution.api_call_node_executor import ApiCallNodeExecutor
from app.execution.condition_node_executor import ConditionNodeExecutor
from app.execution.expression_evaluator import ExpressionEvaluator
from app.execution.node_executor_registry import NodeExecutorRegistry
from app.execution.script_node_executor import ScriptNodeExecutor
from app.execution.variable_resolver import VariableResolver
from app.execution.wait_node_executor import WaitNodeExecutor
from app.execution.worker import CaseExecutor, ExecutionStatus, ExecutionType, AssertionType
from app.services.scenario_resolution_service import (
    ScenarioResolutionError,
    ScenarioResolutionService,
)
from app.services.scenario_node_run_service import ScenarioNodeRunService
from app.services.dsl_normalizer import DslNormalizer

logger = logging.getLogger(__name__)


def create_scenario_execution(
    db: Session,
    scenario: ApiScenario,
    environment_id: int,
    operator_user_id: Optional[int],
    triggered_by: str,
    webhook_url: Optional[str] = None,
    source_execution_id: Optional[int] = None,
) -> TestExecution:
    execution = TestExecution(
        project_id=scenario.project_id,
        version_id=getattr(scenario, "version_id", None),
        execution_type=ExecutionType.SCENARIO,
        target_id=scenario.id,
        operator_user_id=operator_user_id,
        source_execution_id=source_execution_id,
        title=getattr(scenario, "name", f"Scenario {scenario.id}"),
        summary_json={
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "node_count": 0,
            "error_message": None,
        },
        result_status=None,
        environment_id=environment_id,
        execution_mode=getattr(scenario, "execution_mode", "dag"),
        triggered_by=triggered_by,
        status=ExecutionStatus.PENDING,
        started_at=None,
        finished_at=None,
        total=0,
        passed=0,
        failed=0,
        skipped=0,
        duration=0,
        webhook_url=webhook_url,
        callback_status="pending" if webhook_url else None,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


class ScenarioExecutor:
    """Scenario executor (DAG + Context Bus)."""

    def __init__(self):
        self.case_executor = CaseExecutor()
        self.trace_id = get_trace_id()
        self.node_executor_registry = NodeExecutorRegistry()
        self.node_executor_registry.register("api_call", ApiCallNodeExecutor(self))
        self.node_executor_registry.register("condition", ConditionNodeExecutor())
        self.node_executor_registry.register("wait", WaitNodeExecutor())
        self.node_executor_registry.register("script", ScriptNodeExecutor())

    async def execute_scenario(
        self,
        scenario_id: int,
        graph_data: Optional[Dict[str, Any]],
        variables: Optional[Dict[str, Any]],
        db: Session,
        environment_id: Optional[int] = None,
        version_id: Optional[int] = None,
        operator_user_id: Optional[int] = None,
        source_execution_id: Optional[int] = None,
        execution_id: Optional[int] = None,
        triggered_by: str = "manual",
    ) -> Dict[str, Any]:
        """Execute scenario with DAG ordering and shared context bus."""
        trace_id = get_trace_id()
        execution_started_at = datetime.utcnow()
        started_at = time.time()
        variables = variables or {}
        scenario: Optional[ApiScenario] = None
        context: Dict[str, Any] = {"vars": {}, "node": {}}
        node_results: List[Dict[str, Any]] = []
        execution_mode_effective = "dag"

        try:
            scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
            if not scenario:
                raise ValueError(f"Scenario not found: {scenario_id}")
            execution_mode_effective = scenario.execution_mode or "dag"

            graph = graph_data or self._build_graph_from_db_scenario(scenario)
            nodes = graph.get("nodes", [])
            if not nodes:
                raise ValueError("Scenario graph has no nodes")

            if execution_id is None:
                resolved_environment_id = environment_id or scenario.environment_id
                requires_environment = any(
                    str((node or {}).get("node_type", "api_call")).lower() == "api_call"
                    for node in nodes
                )
                if requires_environment and not resolved_environment_id:
                    raise ValueError(f"Environment is required for scenario={scenario_id}")
                execution = create_scenario_execution(
                    db=db,
                    scenario=scenario,
                    environment_id=resolved_environment_id,
                    operator_user_id=operator_user_id,
                    triggered_by=triggered_by,
                    source_execution_id=source_execution_id,
                )
                execution_id = execution.id

            self._validate_graph(nodes)
            levels, execution_mode_effective = self._get_execution_plan(scenario, nodes)

            if isinstance(scenario.context_init, dict):
                context.update(scenario.context_init)
            context.update(variables)
            context.setdefault("vars", {})
            context.setdefault("node", {})

            stop_execution = False

            logger.info(
                f"[{trace_id}] start execute_scenario: id={scenario_id}, "
                f"nodes={len(nodes)}, levels={len(levels)}, execution_id={execution_id}"
            )

            for level_index, level_nodes in enumerate(levels, start=1):
                if stop_execution:
                    break

                logger.info(
                    f"[{trace_id}] execute level {level_index}/{len(levels)} with {len(level_nodes)} nodes"
                )
                context_snapshot = json.loads(json.dumps(context, ensure_ascii=False, default=str))
                coroutines = [
                    self._execute_single_node(
                        scenario=scenario,
                        node=node,
                        context=context_snapshot,
                        environment_id=environment_id,
                        version_id=version_id or scenario.version_id,
                        operator_user_id=operator_user_id,
                        execution_id=execution_id,
                        triggered_by=triggered_by,
                        db=db
                    )
                    for node in level_nodes
                ]

                level_outputs = await asyncio.gather(*coroutines, return_exceptions=True)
                for node, output in zip(level_nodes, level_outputs):
                    if isinstance(output, Exception):
                        output = {
                            "node_key": node["node_key"],
                            "node_id": node.get("id"),
                            "node_type": node.get("node_type", "api_call"),
                            "status": "failed",
                            "error_message": f"{type(output).__name__}: {str(output)}",
                            "result": None,
                            "extracted_variables": {},
                        }

                    output.setdefault("node_type", node.get("node_type", "api_call"))
                    output.setdefault("input_snapshot", context_snapshot)

                    node_results.append(output)

                    extracted = output.get("extracted_variables") or {}
                    if extracted:
                        self._merge_context(context, node["node_key"], extracted)

                    node_continue_on_failure = bool(node.get("continue_on_failure", False))
                    scenario_continue_on_failure = bool(scenario.continue_on_failure)
                    if output.get("status") != "passed" and not (node_continue_on_failure or scenario_continue_on_failure):
                        stop_execution = True
                        logger.warning(
                            f"[{trace_id}] scenario halted at node={node['node_key']} due to failure and fail-fast policy"
                        )

            total = len(nodes)
            passed = sum(1 for r in node_results if r.get("status") == "passed")
            failed = sum(1 for r in node_results if r.get("status") != "passed")
            skipped = max(total - len(node_results), 0)
            duration = int((time.time() - started_at) * 1000)
            summed_response_time = 0
            for item in node_results:
                result_obj = item.get("result") or {}
                response_time = result_obj.get("response_time")
                if response_time is None:
                    response_time = item.get("response_time")
                if isinstance(response_time, (int, float)):
                    summed_response_time += int(response_time)
            result_status = self._aggregate_result_status(passed=passed, failed=failed, skipped=skipped)
            final_status = ExecutionStatus.FAILED if failed > 0 else ExecutionStatus.COMPLETED
            execution_finished_at = datetime.utcnow()
            success = result_status == "passed"

            saved_execution_id = self._save_scenario_execution_record(
                db=db,
                scenario=scenario,
                execution_id=execution_id,
                node_results=node_results,
                status=final_status,
                result_status=result_status,
                success=success,
                environment_id=environment_id or scenario.environment_id,
                duration=duration,
                total=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                started_at=execution_started_at,
                finished_at=execution_finished_at,
                version_id=version_id or scenario.version_id,
                operator_user_id=operator_user_id,
                source_execution_id=source_execution_id,
                triggered_by=triggered_by,
                error_message=None,
                execution_mode_effective=execution_mode_effective,
            )
            if saved_execution_id is not None:
                execution_id = saved_execution_id

            return {
                "scenario_id": scenario_id,
                "execution_id": execution_id,
                "status": final_status,
                "result_status": result_status,
                "success": success,
                "error_message": None,
                "execution_mode_effective": execution_mode_effective,
                "total_nodes": total,
                "passed_nodes": passed,
                "failed_nodes": failed,
                "total_duration_ms": summed_response_time if summed_response_time else duration,
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "duration_ms": duration,
                },
                "results": node_results,
                "context": context,
            }
        except Exception as exc:
            logger.error(f"[{trace_id}] execute_scenario failed: {exc}", exc_info=True)
            error_message = f"{type(exc).__name__}: {exc}"
            duration = int((time.time() - started_at) * 1000)
            if scenario is not None and execution_id is not None:
                self._save_scenario_execution_record(
                    db=db,
                    scenario=scenario,
                    execution_id=execution_id,
                    node_results=node_results,
                    status=ExecutionStatus.FAILED,
                    result_status="failed",
                    success=False,
                    environment_id=environment_id or scenario.environment_id,
                    duration=duration,
                    total=len(node_results),
                    passed=sum(1 for r in node_results if r.get("status") == "passed"),
                    failed=sum(1 for r in node_results if r.get("status") != "passed"),
                    skipped=0,
                    started_at=execution_started_at,
                    finished_at=datetime.utcnow(),
                    version_id=version_id or scenario.version_id,
                    operator_user_id=operator_user_id,
                    source_execution_id=source_execution_id,
                    triggered_by=triggered_by,
                    error_message=error_message,
                    execution_mode_effective=execution_mode_effective,
                )
            elif execution_id is not None:
                try:
                    execution = (
                        db.query(TestExecution)
                        .filter(
                            TestExecution.id == execution_id,
                            TestExecution.execution_type == ExecutionType.SCENARIO,
                        )
                        .first()
                    )
                    if execution:
                        execution.status = ExecutionStatus.FAILED
                        execution.result_status = "failed"
                        execution.finished_at = datetime.utcnow()
                        execution.duration = duration
                        execution.summary_json = {
                            **(execution.summary_json or {}),
                            "error_message": error_message,
                            "success": False,
                            "execution_mode_effective": execution_mode_effective,
                        }
                        db.commit()
                except Exception:
                    db.rollback()
            return {
                "scenario_id": scenario_id,
                "execution_id": execution_id,
                "status": ExecutionStatus.FAILED,
                "result_status": "failed",
                "success": False,
                "error_message": error_message,
                "execution_mode_effective": execution_mode_effective,
                "total_nodes": len(node_results),
                "passed_nodes": sum(1 for r in node_results if r.get("status") == "passed"),
                "failed_nodes": sum(1 for r in node_results if r.get("status") != "passed"),
                "total_duration_ms": duration,
                "summary": {
                    "total": len(node_results),
                    "passed": sum(1 for r in node_results if r.get("status") == "passed"),
                    "failed": sum(1 for r in node_results if r.get("status") != "passed"),
                    "skipped": 0,
                    "duration_ms": duration,
                },
                "results": node_results,
                "context": context,
            }
        finally:
            await self.case_executor.close()

    def _build_graph_from_db_scenario(self, scenario: ApiScenario) -> Dict[str, Any]:
        ordered_nodes = sorted((scenario.nodes or []), key=lambda n: (n.step_order, n.id))
        return {
            "nodes": [
                {
                    "id": node.id,
                    "node_key": node.node_key,
                    "node_name": node.node_name,
                    "node_type": node.node_type,
                    "ref_type": node.ref_type,
                    "ref_id": node.ref_id,
                    "step_order": node.step_order,
                    "depends_on": node.depends_on or [],
                    "input_mapping": node.input_mapping or {},
                    "extract_rules": node.extract_rules,
                    "assertion_overrides": node.assertion_overrides,
                    "timeout_seconds": node.timeout_seconds,
                    "retry_count": node.retry_count,
                    "continue_on_failure": node.continue_on_failure,
                    "is_enabled": node.is_enabled,
                    "extra_config": node.extra_config,
                }
                for node in ordered_nodes
                if node.is_enabled
            ]
        }

    def _validate_graph(self, nodes: List[Dict[str, Any]]) -> None:
        """
        验证场景图的合法性

        检查项：
        1. node_key 必须存在且唯一
        2. depends_on 必须是列表
        3. 依赖的节点必须存在
        4. 不允许自环（节点不能依赖自己）
        5. 检测环（Cycle Detection）
        6. 检测孤立节点（可选，发出警告）

        Args:
            nodes: 节点列表

        Raises:
            ValueError: 图结构不合法时抛出异常
        """
        # 检查 1: node_key 必须存在且唯一
        node_keys = [n.get("node_key") for n in nodes]
        if any(not key for key in node_keys):
            raise ValueError("Node key is required for all scenario nodes")

        if len(node_keys) != len(set(node_keys)):
            raise ValueError("Duplicate node_key detected in scenario graph")

        node_key_set = set(node_keys)
        indegree: Dict[str, int] = {key: 0 for key in node_keys}
        outdegree: Dict[str, int] = {key: 0 for key in node_keys}
        adjacency: Dict[str, List[str]] = defaultdict(list)

        # 检查 2, 3, 4: depends_on 格式、依赖存在性、自环检测
        for node in nodes:
            key = node["node_key"]
            deps = node.get("depends_on") or []
            
            # 检查 depends_on 必须是列表
            if not isinstance(deps, list):
                raise ValueError(f"depends_on must be list: node={key}")
            
            for dep in deps:
                # 检查依赖的节点必须存在
                if dep not in node_key_set:
                    raise ValueError(f"Unknown dependency '{dep}' referenced by node '{key}'")
                
                # 检查 4: 不允许自环
                if dep == key:
                    raise ValueError(f"Self-dependency detected: node '{key}' cannot depend on itself")
                
                # 构建邻接表和度数
                adjacency[dep].append(key)
                indegree[key] += 1
                outdegree[dep] += 1

        # 检查 5: 检测环（使用拓扑排序）
        queue = [k for k, d in indegree.items() if d == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for nxt in adjacency.get(current, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        if visited != len(nodes):
            raise ValueError("Cycle detected in scenario graph")

        isolated_nodes = [
            key for key in node_key_set
            if indegree.get(key, 0) == 0 and outdegree.get(key, 0) == 0
        ]

        if isolated_nodes:
            logger.warning(
                f"[{self.trace_id}] Detected isolated nodes (no dependencies and no dependents): "
                f"{isolated_nodes}. These nodes will execute independently."
            )

    def _aggregate_result_status(self, passed: int, failed: int, skipped: int) -> str:
        if failed > 0 and passed > 0:
            return "partial_failed"
        if failed > 0:
            return "failed"
        if passed > 0:
            return "passed"
        if skipped > 0:
            return "skipped"
        return "unknown"

        # 检查 6: 检测孤立节点（可选，发出警告）
        isolated_nodes = [
            key for key in node_key_set 
            if indegree.get(key, 0) == 0 and outdegree.get(key, 0) == 0
        ]
        
        if isolated_nodes:
            logger.warning(
                f"[{self.trace_id}] Detected isolated nodes (no dependencies and no dependents): "
                f"{isolated_nodes}. These nodes will execute independently."
            )

    def _build_execution_levels(self, nodes: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        node_map = {node["node_key"]: node for node in nodes}
        indegree = {key: 0 for key in node_map.keys()}
        adjacency: Dict[str, List[str]] = defaultdict(list)

        for node in nodes:
            key = node["node_key"]
            for dep in (node.get("depends_on") or []):
                adjacency[dep].append(key)
                indegree[key] += 1

        current_level = [k for k, d in indegree.items() if d == 0]
        levels: List[List[Dict[str, Any]]] = []
        visited = 0

        while current_level:
            level_nodes = [node_map[key] for key in current_level]
            levels.append(level_nodes)
            next_level: List[str] = []

            for key in current_level:
                visited += 1
                for nxt in adjacency.get(key, []):
                    indegree[nxt] -= 1
                    if indegree[nxt] == 0:
                        next_level.append(nxt)

            current_level = next_level

        if visited != len(nodes):
            raise ValueError("Cannot build execution levels due to graph cycle")

        return levels

    def _get_execution_plan(
        self,
        scenario: ApiScenario,
        nodes: List[Dict[str, Any]],
    ) -> tuple[List[List[Dict[str, Any]]], str]:
        raw_mode = (scenario.execution_mode or "dag").strip().lower()
        if raw_mode == "sequential":
            ordered_nodes = sorted(
                nodes,
                key=lambda item: (item.get("step_order", 0), item.get("id") or 0),
            )
            return [[node] for node in ordered_nodes], "sequential"

        return self._build_execution_levels(nodes), "dag"

    async def _execute_single_node(
        self,
        scenario: ApiScenario,
        node: Dict[str, Any],
        context: Dict[str, Any],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
        execution_id: int,
        triggered_by: str,
        db: Session
    ) -> Dict[str, Any]:
        return await self._run_node_with_retry(
            scenario=scenario,
            node=node,
            context=context,
            environment_id=environment_id,
            version_id=version_id,
            operator_user_id=operator_user_id,
            execution_id=execution_id,
            triggered_by=triggered_by,
            db=db,
        )

    async def _run_node_with_retry(
        self,
        scenario: ApiScenario,
        node: Dict[str, Any],
        context: Dict[str, Any],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
        execution_id: int,
        triggered_by: str,
        db: Session,
    ) -> Dict[str, Any]:
        node_key = node["node_key"]
        trace_id = get_trace_id()
        timeout_seconds = self._get_effective_timeout_seconds(scenario, node)
        retry_count = self._get_effective_retry_count(scenario, node)
        max_attempts = max(retry_count, 0) + 1
        last_output: Optional[Dict[str, Any]] = None
        attempt_history: List[Dict[str, Any]] = []

        for attempt in range(1, max_attempts + 1):
            attempt_started_at = datetime.utcnow()
            logger.info(
                f"[{trace_id}] execute node={node_key}, attempt={attempt}/{max_attempts}, timeout={timeout_seconds}s"
            )
            output = await self._execute_single_node_once(
                scenario=scenario,
                node=node,
                context=context,
                environment_id=environment_id,
                version_id=version_id,
                operator_user_id=operator_user_id,
                execution_id=execution_id,
                triggered_by=triggered_by,
                db=db,
                timeout_seconds=timeout_seconds,
            )
            output["started_at"] = output.get("started_at") or attempt_started_at
            output["finished_at"] = output.get("finished_at") or datetime.utcnow()
            output["attempt"] = attempt
            output["max_attempts"] = max_attempts
            output["timeout_seconds"] = timeout_seconds
            output["retry_count_effective"] = retry_count
            attempt_history.append(copy.deepcopy(output))
            last_output = output

            if output.get("status") == "passed":
                output["attempt_history"] = attempt_history
                return output

            if attempt >= max_attempts or not self._is_retryable_node_output(output):
                output["attempt_history"] = attempt_history
                return output

            logger.warning(
                f"[{trace_id}] retry node={node_key} after attempt={attempt}, error={output.get('error_message')}"
            )

        fallback_output = last_output or {
            "node_key": node_key,
            "node_id": node.get("id"),
            "status": "failed",
            "error_message": "Node execution failed without output",
            "result": None,
            "extracted_variables": {},
            "attempt": max_attempts,
            "max_attempts": max_attempts,
            "timeout_seconds": timeout_seconds,
            "retry_count_effective": retry_count,
        }
        fallback_output["attempt_history"] = attempt_history or [copy.deepcopy(fallback_output)]
        return fallback_output

    async def _execute_single_node_once(
        self,
        scenario: ApiScenario,
        node: Dict[str, Any],
        context: Dict[str, Any],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
        execution_id: int,
        triggered_by: str,
        db: Session,
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        executor = self.node_executor_registry.get_executor(node.get("node_type", "api_call"))
        return await executor.execute(
            scenario=scenario,
            node=node,
            context=context,
            environment_id=environment_id,
            version_id=version_id,
            operator_user_id=operator_user_id,
            execution_id=execution_id,
            triggered_by=triggered_by,
            db=db,
            timeout_seconds=timeout_seconds,
        )

    def _build_execution_case(self, case: ApiCase, node: Dict[str, Any]) -> ApiCase:
        execution_case = copy.copy(case)

        if hasattr(case, "assertion_rules"):
            execution_case.assertion_rules = copy.deepcopy(case.assertion_rules)
        if hasattr(case, "extraction_rules"):
            execution_case.extraction_rules = copy.deepcopy(case.extraction_rules)

        assertion_overrides = node.get("assertion_overrides")
        if assertion_overrides:
            execution_case.assertion_rules = copy.deepcopy(assertion_overrides)

        extract_rules = node.get("extract_rules")
        if extract_rules:
            execution_case.extraction_rules = DslNormalizer.normalize_extract_rules(copy.deepcopy(extract_rules))

        return execution_case

    def _get_effective_timeout_seconds(self, scenario: ApiScenario, node: Dict[str, Any]) -> int:
        timeout_value = node.get("timeout_seconds")
        if timeout_value is None:
            timeout_value = scenario.timeout_seconds
        if not isinstance(timeout_value, int) or timeout_value <= 0:
            return 600
        return timeout_value

    def _get_effective_retry_count(self, scenario: ApiScenario, node: Dict[str, Any]) -> int:
        retry_value = node.get("retry_count")
        if retry_value is None:
            retry_value = scenario.retry_count
        if not isinstance(retry_value, int) or retry_value < 0:
            return 0
        return retry_value

    def _is_retryable_node_output(self, output: Dict[str, Any]) -> bool:
        error_type = output.get("error_type")
        if error_type in {"timeout_error", "network_error"}:
            return True

        result = output.get("result") or {}
        response_code = result.get("response_code")
        if response_code in {0, 429}:
            return True
        if isinstance(response_code, int) and response_code >= 500:
            return True

        error_message = (output.get("error_message") or "").lower()
        retryable_fragments = [
            "timeout",
            "timed out",
            "connect",
            "connection",
            "network",
            "temporarily unavailable",
        ]
        return any(fragment in error_message for fragment in retryable_fragments)

    def _classify_exception_type(self, exc: Exception) -> str:
        message = str(exc).lower()
        if "timeout" in message or "timed out" in message:
            return "timeout_error"
        if any(fragment in message for fragment in ("connect", "connection", "network")):
            return "network_error"
        return "system_error"

    def _resolve_node_target(
        self,
        scenario: ApiScenario,
        node: Dict[str, Any],
        context: Dict[str, Any],
        environment_id: Optional[int],
        db: Session
    ) -> Any:
        ref_type = (node.get("ref_type") or "api_case").lower()
        ref_id = node.get("ref_id")
        if not isinstance(ref_id, int):
            raise ValueError(f"Invalid ref_id for node={node.get('node_key')}")

        case: Optional[ApiCase] = None
        definition: Optional[ApiDefinition] = None

        try:
            return ScenarioResolutionService.resolve_node_runtime_target(
                db,
                scenario=scenario,
                node=node,
                override_environment_id=node.get("environment_id") or environment_id,
            )
        except ScenarioResolutionError as exc:
            raise ValueError(str(exc)) from exc

    def _select_case_for_definition(
        self,
        scenario: ApiScenario,
        node: Dict[str, Any],
        definition: ApiDefinition,
        db: Session,
    ) -> ApiCase:
        extra_config = node.get("extra_config") or {}
        case_selection = extra_config.get("case_selection")
        node_key = node.get("node_key")

        if not isinstance(case_selection, dict):
            raise ValueError(
                f"Node '{node_key}' with ref_type=api_definition must declare "
                "extra_config.case_selection"
            )

        strategy = case_selection.get("strategy")
        if strategy == "case_id":
            case_id = case_selection.get("case_id")
            if not isinstance(case_id, int):
                raise ValueError(
                    f"Node '{node_key}' with strategy=case_id must provide "
                    "extra_config.case_selection.case_id"
                )
            case = db.query(ApiCase).filter(ApiCase.id == case_id).first()
            if not case:
                raise ValueError(f"ApiCase not found for node '{node_key}': {case_id}")
            if case.project_id != scenario.project_id:
                raise ValueError(
                    f"ApiCase project mismatch for node '{node_key}': "
                    f"case_project={case.project_id}, scenario_project={scenario.project_id}"
                )
            if case.definition_id != definition.id:
                raise ValueError(
                    f"ApiCase definition mismatch for node '{node_key}': "
                    f"case_definition={case.definition_id}, definition={definition.id}"
                )
            if case.status != "active":
                raise ValueError(
                    f"ApiCase selected by node '{node_key}' is not active: {case_id}"
                )
            return case

        if strategy == "first_active":
            case = (
                db.query(ApiCase)
                .filter(
                    ApiCase.definition_id == definition.id,
                    ApiCase.project_id == scenario.project_id,
                    ApiCase.status == "active",
                )
                .order_by(ApiCase.id.asc())
                .first()
            )
            if not case:
                raise ValueError(
                    f"No active ApiCase found for definition={definition.id}, "
                    f"node='{node_key}'"
                )
            return case

        raise ValueError(
            f"Unsupported case selection strategy for node '{node_key}': {strategy}"
        )

    def _render_with_context(self, payload: Any, context: Dict[str, Any]) -> Any:
        return VariableResolver.render(payload, context)

    def _get_context_value(self, context: Dict[str, Any], key_path: str) -> Any:
        return ExpressionEvaluator.get_context_value(context, key_path)

    def _extract_flat_variables(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return VariableResolver.flatten_context(context)

    def _merge_context(self, context: Dict[str, Any], node_key: str, extracted_variables: Dict[str, Any]) -> None:
        context.setdefault("node", {})
        context.setdefault("vars", {})

        context["node"][node_key] = extracted_variables
        if isinstance(extracted_variables, dict):
            for key, value in extracted_variables.items():
                context["vars"][key] = value
                if isinstance(value, (str, int, float, bool)):
                    context[key] = value

    def _save_scenario_execution_record(
        self,
        db: Session,
        scenario: ApiScenario,
        execution_id: int,
        node_results: List[Dict[str, Any]],
        status: str,
        result_status: str,
        success: bool,
        environment_id: Optional[int],
        duration: int,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        version_id: Optional[int] = None,
        operator_user_id: Optional[int] = None,
        source_execution_id: Optional[int] = None,
        triggered_by: str = "manual",
        error_message: Optional[str] = None,
        execution_mode_effective: Optional[str] = None,
    ) -> Optional[int]:
        try:
            execution = (
                db.query(TestExecution)
                .filter(
                    TestExecution.id == execution_id,
                    TestExecution.execution_type == ExecutionType.SCENARIO,
                )
                .first()
            )
            if not execution:
                raise ValueError(f"Scenario execution not found: {execution_id}")

            execution.project_id = scenario.project_id
            execution.version_id = version_id
            execution.target_id = scenario.id
            execution.operator_user_id = operator_user_id
            execution.source_execution_id = source_execution_id
            execution.title = scenario.name
            execution.summary_json = {
                **(execution.summary_json or {}),
                "scenario_id": scenario.id,
                "scenario_name": scenario.name,
                "node_count": total,
                "success": success,
                "error_message": error_message,
                "execution_mode_effective": execution_mode_effective or scenario.execution_mode,
            }
            execution.result_status = result_status
            execution.environment_id = environment_id
            execution.execution_mode = execution_mode_effective or scenario.execution_mode
            execution.triggered_by = triggered_by
            execution.status = status
            execution.started_at = started_at or execution.started_at or datetime.utcnow()
            execution.finished_at = finished_at or datetime.utcnow()
            execution.total = total
            execution.passed = passed
            execution.failed = failed
            execution.skipped = skipped
            execution.duration = duration

            db.query(TestExecutionResult).filter(
                TestExecutionResult.execution_id == execution.id
            ).delete(synchronize_session=False)

            for item in node_results:
                result = item.get("result") or {}
                execution_result = TestExecutionResult(
                    execution_id=execution.id,
                    target_type="scenario_node",
                    target_id=item.get("node_id") or 0,
                    status=item.get("status"),
                    response_time=result.get("response_time"),
                    response_code=result.get("response_code"),
                    response_body={"raw": result.get("response_body")} if result else None,
                    request_body={"raw": result.get("request_body")} if result else None,
                    assertion_results=result.get("assertion_results") if result else None,
                    extracted_variables=item.get("extracted_variables", {}),
                    error_message=item.get("error_message"),
                )
                db.add(execution_result)

            revision_id = (execution.summary_json or {}).get("scenario_revision_id")
            if revision_id is not None:
                ScenarioNodeRunService.replace_execution_node_runs(
                    db,
                    execution_id=execution.id,
                    scenario_id=scenario.id,
                    revision_id=revision_id,
                    node_results=node_results,
                )

            db.commit()
            self._sync_graph_from_execution(db, node_results)
            return execution.id
        except Exception as e:
            db.rollback()
            logger.error(
                f"[{self.trace_id}] save scenario execution record failed: scenario_id={scenario.id}, error={str(e)}",
                exc_info=True
            )
            return None

    def _sync_graph_from_execution(self, db: Session, node_results: List[Dict[str, Any]]) -> None:
        """Sync knowledge graph from execution logs if impact info is available."""
        try:
            from app.platform.db.base import ScenarioNode
            from app.domains.knowledge_graph.graph_service import KnowledgeGraphService

            node_ids = [item.get("node_id") for item in node_results if item.get("node_id")]
            if not node_ids:
                return

            nodes = db.query(ScenarioNode).filter(ScenarioNode.id.in_(node_ids)).all()
            node_map = {n.id: n for n in nodes}

            impacts: List[Dict[str, Any]] = []
            for item in node_results:
                node_id = item.get("node_id")
                if not node_id:
                    continue
                node = node_map.get(node_id)
                if not node or node.ref_type != "api_definition":
                    continue

                definition_id = node.ref_id
                result = item.get("result") or {}

                table_names = []
                for key in ("impacted_tables", "db_tables", "tables"):
                    value = result.get(key) or item.get(key)
                    if isinstance(value, list):
                        table_names.extend([v for v in value if isinstance(v, str)])

                table_impacts = result.get("table_impacts") or item.get("table_impacts")
                if isinstance(table_impacts, list):
                    for entry in table_impacts:
                        if not isinstance(entry, dict):
                            continue
                        table_name = entry.get("table") or entry.get("table_name")
                        if not table_name:
                            continue
                        impacts.append({
                            "definition_id": definition_id,
                            "table_name": table_name,
                            "count": entry.get("count", 1),
                        })

                for table_name in set(table_names):
                    impacts.append({
                        "definition_id": definition_id,
                        "table_name": table_name,
                        "count": 1,
                    })

            if impacts:
                KnowledgeGraphService(db).build_from_execution_logs(impacts)
        except Exception as e:
            logger.warning(f"[{self.trace_id}] Graph sync failed (ignored): {e}")


# ==================== AI 增强执行器（预留） ====================

class AIAssistedExecutor(CaseExecutor):
    """AI 增强执行器（预留）
    
    V2.0 第三阶段（AI 增强）核心组件
    支持智能断言生成、智能参数映射等 AI 功能
    
    TODO: 待实现
    """

    async def auto_generate_assertions(
        self,
        response: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        AI ????????
        """
        from app.domains.ai_testing.assertion_generator import AssertionGenerator

        project_id = context.get("project_id") if isinstance(context, dict) else None
        payload = {
            "response": response,
            "response_sample": response.get("body") if isinstance(response.get("body"), dict) else None,
            "status_code": response.get("status_code"),
        }
        result = await AssertionGenerator().generate(project_id, payload)
        return result.get("assertion_rules", [])

    async def auto_map_variables(
        self,
        source_output: Dict[str, Any],
        target_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        AI ?????????????
        """
        from app.domains.ai_testing.variable_mapper import VariableMapper

        project_id = context.get("project_id") if isinstance(context, dict) else None
        report = await VariableMapper().suggest(
            project_id,
            {
                "source_output": source_output,
                "target_input": target_input,
            },
        )
        return report.model_dump()

    async def analyze_test_failure(
        self,
        execution_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        AI ????????
        """
        from app.domains.ai_testing.failure_analyzer import FailureAnalyzer

        project_id = context.get("project_id") if isinstance(context, dict) else None
        report = await FailureAnalyzer().analyze(project_id, execution_result)
        return report.model_dump()

    async def generate_test_cases(
        self,
        api_definition: Dict[str, Any],
        num_cases: int = 5,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        AI 自动生成测试用例
        
        Args:
            api_definition: API 定义
            num_cases: 生成用例数量
            context: 上下文信息（可选）
            
        Returns:
            List[Dict]: 生成的测试用例列表
                [
                    {
                        "name": "正常登录",
                        "request_data": {...},
                        "assertion_rules": {...}
                    }
                ]
        """
        # 调用 AI 服务生成用例（基准用例模板）
        from app.ai.service import AIService

        ai_service = AIService()
        total = max(1, int(num_cases))
        results: List[Dict[str, Any]] = []

        method = api_definition.get("method", "GET")
        path = api_definition.get("path", "/")
        summary = api_definition.get("summary")
        description = api_definition.get("description")
        request_schema = api_definition.get("request_schema")
        response_schema = api_definition.get("response_schema")

        for _ in range(total):
            case = await ai_service.generate_base_case(
                method=method,
                path=path,
                summary=summary,
                description=description,
                request_schema=request_schema,
                response_schema=response_schema
            )

            # 兼容模型返回列表或单对象
            if isinstance(case, list):
                results.extend(case)
            else:
                results.append(case)

        return results
