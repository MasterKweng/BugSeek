from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.execution.variable_resolver import VariableResolver
from app.platform.db.base import ApiScenario


class ScriptNodeExecutor:
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
        outputs = extra_config.get("outputs")
        if not isinstance(outputs, dict):
            outputs = extra_config.get("set_vars")

        if not isinstance(outputs, dict):
            return {
                "node_key": node_key,
                "node_id": node.get("id"),
                "status": "failed",
                "error_message": "Script node requires extra_config.outputs or extra_config.set_vars",
                "error_type": "config_error",
                "result": None,
                "extracted_variables": {},
            }

        resolved_outputs = {key: VariableResolver.render(value, context) for key, value in outputs.items()}

        return {
            "node_key": node_key,
            "node_id": node.get("id"),
            "status": "passed",
            "error_message": None,
            "result": {
                "status": "passed",
                "response_time": 0,
                "response_code": 200,
                "outputs": resolved_outputs,
            },
            "extracted_variables": resolved_outputs,
        }
