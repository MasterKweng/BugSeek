"""Assertion generator."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from app.ai.service import AIService

from .scenario_generator import _parse_ai_response


class AssertionGenerator:
    async def generate(self, project_id: Optional[int], payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized_payload = dict(payload or {})
        fallback_rules = self._build_rule_based_assertions(normalized_payload)

        ai_rules: List[Dict[str, Any]] = []
        ai_confidence = None

        try:
            ai_service = AIService()
            result = await ai_service.execute(
                task_type="assertion_generation",
                project_id=project_id,
                input_data=normalized_payload,
            )
            if result.get("success"):
                ai_payload = _parse_ai_response(result.get("result"))
                ai_rules, ai_confidence = self._normalize_ai_assertions(ai_payload)
        except Exception:
            ai_rules = []
            ai_confidence = None

        merged_rules = self._merge_rules(fallback_rules, ai_rules)
        return {
            "assertion_rules": merged_rules,
            "ai_confidence": ai_confidence,
            "strategy": "rule_based+ai" if ai_rules else "rule_based",
        }

    def _build_rule_based_assertions(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        method = str(payload.get("method") or "GET").upper()
        response_schema = payload.get("response_schema") or {}
        response_sample = self._normalize_response_sample(payload)
        rules: List[Dict[str, Any]] = []

        expected_status = payload.get("status_code")
        if expected_status is None:
            expected_status = 201 if method == "POST" else 200
        rules.append({
            "source": "status",
            "operator": "==",
            "value": expected_status,
            "description": "响应状态码符合成功预期",
        })

        rules.append({
            "source": "header",
            "property": "content-type",
            "operator": "contains",
            "value": "json",
            "description": "响应头返回 JSON 内容",
        })

        rules.append({
            "source": "time",
            "operator": "<=",
            "value": int(payload.get("max_response_time_ms") or 1000),
            "description": "响应时间不超过阈值",
        })

        body_rules = self._build_body_rules(response_schema, response_sample)
        return self._dedupe_rules(rules + body_rules)

    def _normalize_response_sample(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sample = payload.get("response_sample")
        if isinstance(sample, dict):
            return sample

        response = payload.get("response")
        if isinstance(response, dict):
            body = response.get("body", response)
            if isinstance(body, dict):
                return body
            if isinstance(body, str):
                try:
                    loaded = json.loads(body)
                    if isinstance(loaded, dict):
                        return loaded
                except Exception:
                    return {}
        return {}

    def _build_body_rules(self, schema: Dict[str, Any], sample: Dict[str, Any]) -> List[Dict[str, Any]]:
        rules: List[Dict[str, Any]] = []
        required_fields = []
        properties = {}
        if isinstance(schema, dict):
            required_fields = schema.get("required") or []
            properties = schema.get("properties") or {}

        for field in required_fields[:8]:
            path = f"$.{field}"
            rules.append({
                "source": "body",
                "property": path,
                "operator": "not_null",
                "description": f"必填字段 {field} 存在",
            })
            schema_type = self._schema_type(properties.get(field))
            if schema_type:
                rules.append({
                    "source": "body",
                    "property": path,
                    "operator": "type",
                    "value": schema_type,
                    "description": f"字段 {field} 类型正确",
                })

        flattened_sample = self._flatten(sample)
        important_fields = ("code", "success", "status", "message")
        for path, value in flattened_sample:
            json_path = f"$.{path}"
            rules.append({
                "source": "body",
                "property": json_path,
                "operator": "not_null",
                "description": f"字段 {path} 存在",
            })
            inferred_type = self._python_type_name(value)
            if inferred_type:
                rules.append({
                    "source": "body",
                    "property": json_path,
                    "operator": "type",
                    "value": inferred_type,
                    "description": f"字段 {path} 类型稳定",
                })

            leaf_name = path.split(".")[-1]
            if leaf_name in important_fields and isinstance(value, (str, int, float, bool)):
                rules.append({
                    "source": "body",
                    "property": json_path,
                    "operator": "==",
                    "value": value,
                    "description": f"关键字段 {path} 值符合样本",
                })

        return rules[:20]

    def _flatten(self, value: Any, prefix: str = "") -> List[Tuple[str, Any]]:
        items: List[Tuple[str, Any]] = []
        if isinstance(value, dict):
            for key, item in value.items():
                child_prefix = f"{prefix}.{key}" if prefix else key
                items.extend(self._flatten(item, child_prefix))
        elif isinstance(value, list):
            if value:
                items.extend(self._flatten(value[0], f"{prefix}[0]"))
            else:
                items.append((prefix, value))
        else:
            if prefix:
                items.append((prefix, value))
        return items

    def _schema_type(self, schema: Any) -> Optional[str]:
        if not isinstance(schema, dict):
            return None
        value = schema.get("type")
        if isinstance(value, list):
            for item in value:
                if item != "null":
                    return str(item)
            return None
        if isinstance(value, str):
            return value
        return None

    def _python_type_name(self, value: Any) -> Optional[str]:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int) and not isinstance(value, bool):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return None

    def _normalize_ai_assertions(self, payload: Any) -> Tuple[List[Dict[str, Any]], Optional[float]]:
        if isinstance(payload, dict):
            rules = payload.get("assertion_rules") or payload.get("rules") or payload.get("assertions") or []
            confidence = payload.get("ai_confidence")
        elif isinstance(payload, list):
            rules = payload
            confidence = None
        else:
            rules = []
            confidence = None

        normalized: List[Dict[str, Any]] = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            normalized_rule = {
                "source": rule.get("source", "body"),
                "property": rule.get("property") or rule.get("field") or rule.get("json_path"),
                "operator": rule.get("operator", "=="),
                "value": rule.get("value"),
                "description": rule.get("description"),
            }
            if normalized_rule["source"] == "status_code":
                normalized_rule["source"] = "status"
            normalized.append({k: v for k, v in normalized_rule.items() if v is not None})
        return normalized, confidence

    def _merge_rules(self, fallback_rules: List[Dict[str, Any]], ai_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._dedupe_rules(fallback_rules + ai_rules)

    def _dedupe_rules(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        result = []
        for rule in rules:
            key = (
                rule.get("source"),
                rule.get("property"),
                rule.get("operator"),
                json.dumps(rule.get("value"), ensure_ascii=False, sort_keys=True, default=str),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(rule)
        return result
