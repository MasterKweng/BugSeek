from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.execution.expression_evaluator import ExpressionEvaluator
from app.platform.db.base import ApiScenario


class ConditionNodeExecutor:
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
        del scenario, environment_id, version_id, operator_user_id, execution_id, triggered_by, db, timeout_seconds

        node_key = node["node_key"]
        extra_config = node.get("extra_config") or {}
        expression = extra_config.get("expression") or extra_config.get("condition")
        if expression is None:
            return {
                "node_key": node_key,
                "node_id": node.get("id"),
                "status": "failed",
                "error_message": "Condition node requires extra_config.expression",
                "error_type": "config_error",
                "result": None,
                "extracted_variables": {},
            }

        if isinstance(expression, dict) and "dsl" in expression:
            result_value = ExpressionEvaluator.evaluate_spec(expression, context)
        elif isinstance(expression, dict):
            result_value = ExpressionEvaluator.evaluate_jsonlogic(expression, context)
        elif isinstance(expression, str):
            if "{{" in expression and "}}" in expression:
                rendered = ExpressionEvaluator.render_template(expression, context)
                result_value = rendered not in {"", "0", "false", "False", "None"}
            else:
                result_value = ExpressionEvaluator.get_context_value(context, expression)
        else:
            result_value = expression

        passed = bool(result_value)
        fail_on_false = bool(extra_config.get("fail_on_false", False))
        output_var = extra_config.get("output_var") or f"{node_key}_result"
        status_value = "failed" if (fail_on_false and not passed) else "passed"

        return {
            "node_key": node_key,
            "node_id": node.get("id"),
            "status": status_value,
            "error_message": None if status_value == "passed" else f"Condition evaluated to false: {node_key}",
            "result": {
                "status": status_value,
                "condition_result": passed,
                "response_time": 0,
                "response_code": 200,
            },
            "extracted_variables": {output_var: passed},
        }
