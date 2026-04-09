from __future__ import annotations

from typing import Any, Dict, List, Tuple


class DslNormalizer:
    SUPPORTED_DSLS = {"template", "jsonpath", "jmespath", "jsonlogic"}

    @classmethod
    def normalize_extract_rules(cls, extract_rules: Any) -> List[Dict[str, Any]]:
        if not extract_rules:
            return []
        if isinstance(extract_rules, list):
            normalized: List[Dict[str, Any]] = []
            for rule in extract_rules:
                if not isinstance(rule, dict):
                    continue
                normalized.append(rule)
            return normalized
        if isinstance(extract_rules, dict):
            normalized = []
            for var_name, rule in extract_rules.items():
                if isinstance(rule, str):
                    normalized.append({"var_name": var_name, "field": rule, "dsl": "jsonpath" if rule.startswith("$") else "path"})
                elif isinstance(rule, dict):
                    dsl = (rule.get("dsl") or "").strip().lower()
                    expr = rule.get("expr")
                    if dsl in {"jsonpath", "jmespath"} and isinstance(expr, str):
                        normalized.append({"var_name": var_name, "field": expr, "dsl": dsl})
                    elif dsl == "template":
                        template = rule.get("template") if rule.get("template") is not None else expr
                        normalized.append({"var_name": var_name, "field": template, "dsl": "template"})
            return normalized
        return []

    @classmethod
    def validate_node(cls, node: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        node_type = str(node.get("node_type", "api_call")).lower()
        extra_config = node.get("extra_config") or {}

        def validate_value(value: Any, field: str) -> None:
            if isinstance(value, dict):
                if "dsl" in value:
                    dsl = (value.get("dsl") or "").strip().lower()
                    if dsl not in cls.SUPPORTED_DSLS:
                        errors.append({"field": field, "message": f"unsupported dsl: {dsl}"})
                        return
                    if dsl == "template":
                        template = value.get("template") if value.get("template") is not None else value.get("expr")
                        if not isinstance(template, str):
                            errors.append({"field": field, "message": "template dsl requires template string"})
                    elif dsl in {"jsonpath", "jmespath"}:
                        if not isinstance(value.get("expr"), str):
                            errors.append({"field": field, "message": f"{dsl} dsl requires expr string"})
                    elif dsl == "jsonlogic":
                        logic = value.get("logic") if value.get("logic") is not None else value.get("expr")
                        if not isinstance(logic, dict):
                            errors.append({"field": field, "message": "jsonlogic dsl requires object logic"})
                    return
                for key, child in value.items():
                    validate_value(child, f"{field}.{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    validate_value(child, f"{field}[{index}]")

        validate_value(node.get("input_mapping") or {}, "input_mapping")

        extract_rules = node.get("extract_rules")
        if isinstance(extract_rules, dict):
            for var_name, rule in extract_rules.items():
                if isinstance(rule, str):
                    continue
                if isinstance(rule, dict):
                    dsl = (rule.get("dsl") or "").strip().lower()
                    if dsl not in {"jsonpath", "jmespath", "template"}:
                        errors.append({"field": f"extract_rules.{var_name}", "message": f"unsupported extraction dsl: {dsl}"})
                    elif dsl == "template":
                        warnings.append({"field": f"extract_rules.{var_name}", "message": "template extraction is supported but less stable than jsonpath/jmespath"})
                    elif not isinstance(rule.get("expr"), str):
                        errors.append({"field": f"extract_rules.{var_name}", "message": "extraction dsl requires expr string"})
                else:
                    errors.append({"field": f"extract_rules.{var_name}", "message": "extract rule must be string or object"})
        elif extract_rules not in (None, {}):
            errors.append({"field": "extract_rules", "message": "extract_rules must be an object"})

        if node_type == "condition":
            expression = extra_config.get("expression") or extra_config.get("condition")
            if expression is None:
                errors.append({"field": "extra_config.expression", "message": "condition node requires expression"})
            elif isinstance(expression, dict) and "dsl" in expression:
                validate_value(expression, "extra_config.expression")
        elif node_type == "wait":
            mode = str(extra_config.get("mode", "sleep")).lower()
            if mode not in {"sleep", "poll"}:
                errors.append({"field": "extra_config.mode", "message": f"unsupported wait mode: {mode}"})
            if mode == "poll":
                expression = extra_config.get("until") or extra_config.get("condition")
                if expression is None:
                    errors.append({"field": "extra_config.until", "message": "wait poll node requires until"})
                elif isinstance(expression, dict) and "dsl" in expression:
                    validate_value(expression, "extra_config.until")
        elif node_type == "script":
            outputs = extra_config.get("outputs")
            if not isinstance(outputs, dict):
                outputs = extra_config.get("set_vars")
            if not isinstance(outputs, dict) or not outputs:
                errors.append({"field": "extra_config.outputs", "message": "script node requires outputs"})
            else:
                validate_value(outputs, "extra_config.outputs")

        return errors, warnings

    @classmethod
    def lint_snapshot(cls, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        for node in snapshot.get("nodes") or []:
            node_key = node.get("node_key") or "<unknown>"
            node_errors, node_warnings = cls.validate_node(node)
            for item in node_errors:
                errors.append({"node_key": node_key, **item})
            for item in node_warnings:
                warnings.append({"node_key": node_key, **item})
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
