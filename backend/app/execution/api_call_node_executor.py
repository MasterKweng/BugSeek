from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.trace import get_trace_id
from app.dependencies import SessionLocal
from app.execution.variable_resolver import VariableResolver
from app.platform.db.base import ApiScenario

logger = logging.getLogger(__name__)


class ApiCallNodeExecutor:
    def __init__(self, runtime: Any):
        self.runtime = runtime

    async def execute(
        self,
        *,
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
        del db
        node_key = node["node_key"]
        trace_id = get_trace_id()
        node_db: Optional[Session] = None
        execution_case = None
        resolved_ref_snapshot: Optional[Dict[str, Any]] = None

        try:
            node_db = SessionLocal()
            case, definition, environment = self.runtime._resolve_node_target(
                scenario=scenario,
                node=node,
                context=context,
                environment_id=environment_id,
                db=node_db,
            )
            resolved_ref_snapshot = {
                "case_id": getattr(case, "id", None),
                "definition_id": getattr(definition, "id", None),
                "environment_id": getattr(environment, "id", None),
                "ref_type": node.get("ref_type"),
                "ref_id": node.get("ref_id"),
            }

            node_input_mapping = node.get("input_mapping") or {}
            rendered_mapping = VariableResolver.render(node_input_mapping, context)

            execution_variables = VariableResolver.flatten_context(context)
            if isinstance(rendered_mapping, dict):
                for key, value in rendered_mapping.items():
                    if isinstance(key, str):
                        execution_variables[key] = value

            execution_case = self.runtime._build_execution_case(case, node)

            result = await asyncio.wait_for(
                self.runtime.case_executor.execute_case(
                    case=execution_case,
                    definition=definition,
                    environment=environment,
                    variables=execution_variables,
                    db=node_db,
                    project_id=scenario.project_id,
                    version_id=version_id,
                    operator_user_id=operator_user_id,
                    parent_execution_id=execution_id,
                    triggered_by=f"scenario:{triggered_by}",
                ),
                timeout=timeout_seconds,
            )

            return {
                "node_key": node_key,
                "node_id": node.get("id"),
                "status": result.get("status"),
                "error_message": result.get("error_message"),
                "effective_assertion_rules": getattr(execution_case, "assertion_rules", None),
                "effective_extraction_rules": getattr(execution_case, "extraction_rules", None),
                "resolved_ref_snapshot": resolved_ref_snapshot,
                "result": result,
                "extracted_variables": result.get("extracted_variables", {}) or {},
            }
        except asyncio.TimeoutError:
            if node_db is not None:
                node_db.rollback()
            logger.error(f"[{trace_id}] node execute timeout: node={node_key}, timeout={timeout_seconds}s")
            return {
                "node_key": node_key,
                "node_id": node.get("id"),
                "status": "failed",
                "error_message": f"Node execution timeout after {timeout_seconds}s",
                "error_type": "timeout_error",
                "effective_assertion_rules": getattr(execution_case, "assertion_rules", None),
                "effective_extraction_rules": getattr(execution_case, "extraction_rules", None),
                "resolved_ref_snapshot": resolved_ref_snapshot,
                "result": {
                    "status": "failed",
                    "error_message": f"Node execution timeout after {timeout_seconds}s",
                    "response_code": 0,
                    "response_time": timeout_seconds * 1000,
                },
                "extracted_variables": {},
            }
        except Exception as exc:
            if node_db is not None:
                node_db.rollback()
            logger.error(f"[{trace_id}] node execute failed: node={node_key}, error={str(exc)}", exc_info=True)
            return {
                "node_key": node_key,
                "node_id": node.get("id"),
                "status": "failed",
                "error_message": str(exc),
                "error_type": self.runtime._classify_exception_type(exc),
                "effective_assertion_rules": getattr(execution_case, "assertion_rules", None),
                "effective_extraction_rules": getattr(execution_case, "extraction_rules", None),
                "resolved_ref_snapshot": resolved_ref_snapshot,
                "result": None,
                "extracted_variables": {},
            }
        finally:
            if node_db is not None:
                node_db.close()
