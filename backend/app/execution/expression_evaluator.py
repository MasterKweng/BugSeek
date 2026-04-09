from __future__ import annotations

import re
from typing import Any, Dict

from jsonpath_ng import parse

try:
    import jmespath  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    jmespath = None


class ExpressionEvaluator:
    TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][\w\.\[\]]*)\s*\}\}")

    @staticmethod
    def get_context_value(context: Dict[str, Any], key_path: str) -> Any:
        current: Any = context
        for part in re.split(r"\.", key_path):
            if "[" in part and "]" in part:
                name = part.split("[", 1)[0]
                index = int(part.split("[", 1)[1].split("]", 1)[0])
                if name:
                    if not isinstance(current, dict) or name not in current:
                        return None
                    current = current[name]
                if not isinstance(current, list) or index >= len(current):
                    return None
                current = current[index]
                continue
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @classmethod
    def render_template(cls, template: str, context: Dict[str, Any]) -> str:
        def repl(match: re.Match) -> str:
            key_path = match.group(1)
            value = cls.get_context_value(context, key_path)
            if value is None:
                return match.group(0)
            return str(value)

        return cls.TEMPLATE_PATTERN.sub(repl, template)

    @staticmethod
    def evaluate_jsonpath(data: Any, expr: str) -> Any:
        jsonpath_expression = parse(expr)
        matches = jsonpath_expression.find(data)
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0].value
        return [match.value for match in matches]

    @staticmethod
    def evaluate_jmespath(data: Any, expr: str) -> Any:
        if jmespath is not None:
            return jmespath.search(expr, data)
        return ExpressionEvaluator.get_context_value(data if isinstance(data, dict) else {"value": data}, expr)

    @staticmethod
    def evaluate_jsonlogic(logic: Any, data: Any) -> Any:
        if not isinstance(logic, dict):
            return logic
        if len(logic) != 1:
            raise ValueError("jsonlogic expression must contain exactly one operator")
        operator, raw_args = next(iter(logic.items()))
        args = raw_args if isinstance(raw_args, list) else [raw_args]

        def resolve(value: Any) -> Any:
            if isinstance(value, dict):
                if "var" in value:
                    var_expr = value["var"]
                    if isinstance(var_expr, list):
                        var_expr = var_expr[0] if var_expr else None
                    if not isinstance(var_expr, str):
                        return None
                    return ExpressionEvaluator.get_context_value(
                        data if isinstance(data, dict) else {"value": data},
                        var_expr,
                    )
                return ExpressionEvaluator.evaluate_jsonlogic(value, data)
            return value

        resolved = [resolve(item) for item in args]

        if operator == "==":
            return resolved[0] == resolved[1]
        if operator == "!=":
            return resolved[0] != resolved[1]
        if operator == ">":
            return resolved[0] > resolved[1]
        if operator == ">=":
            return resolved[0] >= resolved[1]
        if operator == "<":
            return resolved[0] < resolved[1]
        if operator == "<=":
            return resolved[0] <= resolved[1]
        if operator == "and":
            return all(bool(item) for item in resolved)
        if operator == "or":
            return any(bool(item) for item in resolved)
        if operator == "!":
            return not bool(resolved[0])
        if operator == "in":
            return resolved[0] in (resolved[1] or [])
        raise ValueError(f"Unsupported jsonlogic operator: {operator}")

    @classmethod
    def evaluate_spec(cls, spec: Dict[str, Any], data: Any) -> Any:
        dsl = (spec.get("dsl") or "").strip().lower()
        expr = spec.get("expr")
        if dsl == "template":
            template = spec.get("template") if spec.get("template") is not None else expr
            if not isinstance(template, str):
                raise ValueError("template DSL requires a string template")
            return cls.render_template(template, data if isinstance(data, dict) else {"value": data})
        if dsl == "jsonpath":
            if not isinstance(expr, str):
                raise ValueError("jsonpath DSL requires expr")
            return cls.evaluate_jsonpath(data, expr)
        if dsl == "jmespath":
            if not isinstance(expr, str):
                raise ValueError("jmespath DSL requires expr")
            return cls.evaluate_jmespath(data, expr)
        if dsl == "jsonlogic":
            logic = spec.get("logic") if spec.get("logic") is not None else expr
            return cls.evaluate_jsonlogic(logic, data)
        raise ValueError(f"Unsupported DSL: {dsl}")
