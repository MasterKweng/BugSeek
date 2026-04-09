from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.execution.expression_evaluator import ExpressionEvaluator
from app.platform.db.base import ApiScenario


class WaitNodeExecutor:
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
        del scenario, environment_id, version_id, operator_user_id, execution_id, triggered_by, db

        node_key = node["node_key"]
        extra_config = node.get("extra_config") or {}
        mode = (extra_config.get("mode") or "sleep").strip().lower()
        started_at = time.time()

        if mode == "sleep":
            sleep_seconds = float(
                extra_config.get("sleep_seconds")
                or extra_config.get("duration_seconds")
                or extra_config.get("wait_seconds")
                or 0
            )
            await asyncio.sleep(max(sleep_seconds, 0))
            elapsed_ms = int((time.time() - started_at) * 1000)
            return {
                "node_key": node_key,
                "node_id": node.get("id"),
                "status": "passed",
                "error_message": None,
                "result": {
                    "status": "passed",
                    "mode": "sleep",
                    "response_time": elapsed_ms,
                    "response_code": 200,
                },
                "extracted_variables": {extra_config.get("output_var") or f"{node_key}_waited": True},
            }

        if mode == "poll":
            interval_seconds = float(extra_config.get("interval_seconds") or 1)
            expression = extra_config.get("until") or extra_config.get("condition")
            if expression is None:
                return {
                    "node_key": node_key,
                    "node_id": node.get("id"),
                    "status": "failed",
                    "error_message": "Wait poll node requires extra_config.until",
                    "error_type": "config_error",
                    "result": None,
                    "extracted_variables": {},
                }

            while True:
                if isinstance(expression, dict) and "dsl" in expression:
                    ready = bool(ExpressionEvaluator.evaluate_spec(expression, context))
                elif isinstance(expression, dict):
                    ready = bool(ExpressionEvaluator.evaluate_jsonlogic(expression, context))
                elif isinstance(expression, str):
                    ready = bool(ExpressionEvaluator.get_context_value(context, expression))
                else:
                    ready = bool(expression)

                elapsed_ms = int((time.time() - started_at) * 1000)
                if ready:
                    return {
                        "node_key": node_key,
                        "node_id": node.get("id"),
                        "status": "passed",
                        "error_message": None,
                        "result": {
                            "status": "passed",
                            "mode": "poll",
                            "response_time": elapsed_ms,
                            "response_code": 200,
                        },
                        "extracted_variables": {extra_config.get("output_var") or f"{node_key}_ready": True},
                    }

                if elapsed_ms >= timeout_seconds * 1000:
                    return {
                        "node_key": node_key,
                        "node_id": node.get("id"),
                        "status": "failed",
                        "error_message": f"Wait poll timeout after {timeout_seconds}s",
                        "error_type": "timeout_error",
                        "result": {
                            "status": "failed",
                            "mode": "poll",
                            "response_time": elapsed_ms,
                            "response_code": 408,
                        },
                        "extracted_variables": {extra_config.get("output_var") or f"{node_key}_ready": False},
                    }

                await asyncio.sleep(max(interval_seconds, 0))

        return {
            "node_key": node_key,
            "node_id": node.get("id"),
            "status": "failed",
            "error_message": f"Unsupported wait mode: {mode}",
            "error_type": "config_error",
            "result": None,
            "extracted_variables": {},
        }
