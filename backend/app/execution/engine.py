"""
Execution engine (scenario orchestration).
"""

import asyncio
import time
import json
import logging
import re
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.platform.db.base import (
    ApiCase, ApiDefinition, ApiScenario, ScenarioNode, Environment,
    TestExecution, TestExecutionResult, AuthConfig
)
from app.core.trace import get_trace_id
from app.execution.worker import CaseExecutor, ExecutionStatus, ExecutionType, AssertionType

logger = logging.getLogger(__name__)


class ScenarioExecutor:
    """Scenario executor (DAG + Context Bus)."""

    def __init__(self):
        self.case_executor = CaseExecutor()
        self.trace_id = get_trace_id()

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
        triggered_by: str = "manual",
    ) -> Dict[str, Any]:
        """Execute scenario with DAG ordering and shared context bus."""
        trace_id = get_trace_id()
        execution_started_at = datetime.utcnow()
        started_at = time.time()
        variables = variables or {}

        scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
        if not scenario:
            raise ValueError(f"Scenario not found: {scenario_id}")

        graph = graph_data or self._build_graph_from_db_scenario(scenario)
        nodes = graph.get("nodes", [])
        if not nodes:
            raise ValueError("Scenario graph has no nodes")

        self._validate_graph(nodes)
        levels = self._build_execution_levels(nodes)

        context: Dict[str, Any] = {}
        if isinstance(scenario.context_init, dict):
            context.update(scenario.context_init)
        context.update(variables)
        context.setdefault("vars", {})
        context.setdefault("node", {})

        stop_execution = False
        node_results: List[Dict[str, Any]] = []

        logger.info(
            f"[{trace_id}] start execute_scenario: id={scenario_id}, "
            f"nodes={len(nodes)}, levels={len(levels)}"
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
                        "status": "failed",
                        "error_message": f"{type(output).__name__}: {str(output)}",
                        "result": None,
                        "extracted_variables": {},
                    }

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
        final_status = "completed"
        execution_finished_at = datetime.utcnow()

        execution_id = self._save_scenario_execution_record(
            db=db,
            scenario=scenario,
            node_results=node_results,
            result_status=result_status,
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
        )

        await self.case_executor.close()

        return {
            "scenario_id": scenario_id,
            "execution_id": execution_id,
            "status": final_status,
            "result_status": result_status,
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

    async def _execute_single_node(
        self,
        scenario: ApiScenario,
        node: Dict[str, Any],
        context: Dict[str, Any],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
        triggered_by: str,
        db: Session
    ) -> Dict[str, Any]:
        node_key = node["node_key"]
        trace_id = get_trace_id()
        try:
            case, definition, environment = self._resolve_node_target(
                scenario=scenario,
                node=node,
                context=context,
                environment_id=environment_id,
                db=db
            )

            node_input_mapping = node.get("input_mapping") or {}
            rendered_mapping = self._render_with_context(node_input_mapping, context)

            execution_variables = self._extract_flat_variables(context)
            if isinstance(rendered_mapping, dict):
                for k, v in rendered_mapping.items():
                    if isinstance(k, str):
                        execution_variables[k] = v

            result = await self.case_executor.execute_case(
                case=case,
                definition=definition,
                environment=environment,
                variables=execution_variables,
                db=db,
                project_id=scenario.project_id,
                version_id=version_id,
                operator_user_id=operator_user_id,
                triggered_by=f"scenario:{triggered_by}",
            )

            return {
                "node_key": node_key,
                "node_id": node.get("id"),
                "status": result.get("status"),
                "error_message": result.get("error_message"),
                "result": result,
                "extracted_variables": result.get("extracted_variables", {}) or {},
            }
        except Exception as e:
            logger.error(f"[{trace_id}] node execute failed: node={node_key}, error={str(e)}", exc_info=True)
            return {
                "node_key": node_key,
                "node_id": node.get("id"),
                "status": "failed",
                "error_message": str(e),
                "result": None,
                "extracted_variables": {},
            }

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

        if ref_type == "api_case":
            case = db.query(ApiCase).filter(ApiCase.id == ref_id).first()
            if not case:
                raise ValueError(f"ApiCase not found: {ref_id}")
            definition = db.query(ApiDefinition).filter(ApiDefinition.id == case.definition_id).first()
        elif ref_type == "api_definition":
            definition = db.query(ApiDefinition).filter(ApiDefinition.id == ref_id).first()
            if not definition:
                raise ValueError(f"ApiDefinition not found: {ref_id}")
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
                    "Scenario V1 requires an executable case for each node."
                )
        else:
            raise ValueError(f"Unsupported ref_type={ref_type}")

        environment_id = (
            node.get("environment_id")
            or environment_id
            or scenario.environment_id
            or case.environment_id
        )
        if not environment_id:
            raise ValueError(f"Environment is required for node={node.get('node_key')}")

        environment = db.query(Environment).filter(Environment.id == environment_id).first()
        if not environment:
            raise ValueError(f"Environment not found: {environment_id}")
        if environment.project_id != scenario.project_id:
            raise ValueError(
                f"Environment project mismatch: env_project={environment.project_id}, "
                f"scenario_project={scenario.project_id}"
            )

        if definition.project_id != scenario.project_id:
            raise ValueError(
                f"Definition project mismatch: def_project={definition.project_id}, "
                f"scenario_project={scenario.project_id}"
            )

        return case, definition, environment

    def _render_with_context(self, payload: Any, context: Dict[str, Any]) -> Any:
        if isinstance(payload, str):
            pattern = re.compile(r"\{\{\s*([a-zA-Z_][\w\.]*)\s*\}\}")

            def repl(match: re.Match) -> str:
                key_path = match.group(1)
                value = self._get_context_value(context, key_path)
                if value is None:
                    return match.group(0)
                return str(value)

            return pattern.sub(repl, payload)

        if isinstance(payload, dict):
            return {k: self._render_with_context(v, context) for k, v in payload.items()}

        if isinstance(payload, list):
            return [self._render_with_context(v, context) for v in payload]

        return payload

    def _get_context_value(self, context: Dict[str, Any], key_path: str) -> Any:
        current: Any = context
        for part in key_path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _extract_flat_variables(self, context: Dict[str, Any]) -> Dict[str, Any]:
        flat: Dict[str, Any] = {}

        for k, v in context.items():
            if isinstance(v, (str, int, float, bool)):
                flat[k] = v

        vars_bucket = context.get("vars")
        if isinstance(vars_bucket, dict):
            for k, v in vars_bucket.items():
                if isinstance(v, (str, int, float, bool)):
                    flat[k] = v

        node_bucket = context.get("node")
        if isinstance(node_bucket, dict):
            for _, extracted in node_bucket.items():
                if isinstance(extracted, dict):
                    for k, v in extracted.items():
                        if isinstance(v, (str, int, float, bool)):
                            flat[k] = v
        return flat

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
        node_results: List[Dict[str, Any]],
        result_status: str,
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
    ) -> Optional[int]:
        try:
            execution = TestExecution(
                project_id=scenario.project_id,
                version_id=version_id,
                execution_type=ExecutionType.SCENARIO,
                target_id=scenario.id,
                operator_user_id=operator_user_id,
                source_execution_id=source_execution_id,
                title=scenario.name,
                summary_json={
                    "scenario_id": scenario.id,
                    "scenario_name": scenario.name,
                    "node_count": total,
                },
                result_status=result_status,
                environment_id=environment_id,
                execution_mode=scenario.execution_mode,
                triggered_by=triggered_by,
                status=ExecutionStatus.COMPLETED,
                started_at=started_at or datetime.utcnow(),
                finished_at=finished_at or datetime.utcnow(),
                total=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                duration=duration
            )
            db.add(execution)
            db.flush()

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
