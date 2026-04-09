from __future__ import annotations

from typing import Any, Dict

from app.execution.expression_evaluator import ExpressionEvaluator


class VariableResolver:
    @classmethod
    def render(cls, payload: Any, context: Dict[str, Any]) -> Any:
        if isinstance(payload, dict):
            if "dsl" in payload:
                return ExpressionEvaluator.evaluate_spec(payload, context)
            return {key: cls.render(value, context) for key, value in payload.items()}
        if isinstance(payload, list):
            return [cls.render(item, context) for item in payload]
        if isinstance(payload, str):
            return ExpressionEvaluator.render_template(payload, context)
        return payload

    @staticmethod
    def flatten_context(context: Dict[str, Any]) -> Dict[str, Any]:
        flat: Dict[str, Any] = {}

        for key, value in context.items():
            if isinstance(value, (str, int, float, bool)):
                flat[key] = value

        vars_bucket = context.get("vars")
        if isinstance(vars_bucket, dict):
            for key, value in vars_bucket.items():
                if isinstance(value, (str, int, float, bool)):
                    flat[key] = value

        node_bucket = context.get("node")
        if isinstance(node_bucket, dict):
            for _, extracted in node_bucket.items():
                if isinstance(extracted, dict):
                    for key, value in extracted.items():
                        if isinstance(value, (str, int, float, bool)):
                            flat[key] = value

        return flat
