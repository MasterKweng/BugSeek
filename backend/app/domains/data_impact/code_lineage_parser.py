"""Helpers for extracting code assignment lineage edges."""

from __future__ import annotations

import re
from typing import Any, Dict, List


class CodeLineageParser:
    """Parse assignment-like metadata into normalized lineage edges."""

    _SETTER_NAME_RE = re.compile(r"set(?P<target>[A-Z][A-Za-z0-9_]*)\s*\(")
    _ASSIGNMENT_RE = re.compile(
        r"(?P<target>[A-Za-z_][A-Za-z0-9_\.]+)\s*=\s*(?P<source>[^;]+)"
    )
    _MAPSTRUCT_RE = re.compile(
        r'target\s*=\s*"(?P<target>[A-Za-z0-9_\.]+)"\s*,\s*source\s*=\s*"(?P<source>[A-Za-z0-9_\.]+)"'
    )
    _GETTER_CALL_RE = re.compile(r"\.get([A-Z][A-Za-z0-9_]*)\s*\(\s*\)")
    _IS_CALL_RE = re.compile(r"\.is([A-Z][A-Za-z0-9_]*)\s*\(\s*\)")
    _NOARG_CALL_RE = re.compile(r"\.(?P<name>[a-z][A-Za-z0-9_]*)\s*\(\s*\)")
    _BUILDER_STEP_RE = re.compile(r"\.(?P<target>[a-z][A-Za-z0-9_]*)\s*\(\s*(?P<source>[^()]+(?:\([^)]*\)[^()]*)*)\s*\)")
    _VAR_DECL_RE = re.compile(
        r"^(?:(?:final|var|val|[A-Z][A-Za-z0-9_<>, ?]+)\s+)?(?P<name>[a-z_][A-Za-z0-9_]*)\s*=\s*(?P<source>[^;]+)$"
    )
    _BEAN_COPY_RE = re.compile(
        r"(?:(?P<owner>BeanUtils|org\.springframework\.beans\.BeanUtils|BeanCopier|[A-Za-z_][A-Za-z0-9_\.]*?)\.)?"
        r"(?P<method>copyProperties|copyIncludedProperties|copySelectedProperties|copySelectiveProperties|copyOnlyProperties|copyIncludeFields)"
        r"\s*\(\s*(?P<source>[A-Za-z_][A-Za-z0-9_\.]*)\s*,\s*(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)(?P<extra>[^)]*)\)"
    )
    _CONVERTER_CALL_RE = re.compile(
        r"(?P<prefix>(?:[A-Za-z_][A-Za-z0-9_]*\.)?)(?P<converter>(?:format|convert|map|transform|to[A-Z][A-Za-z0-9_]*|from[A-Z][A-Za-z0-9_]*))\s*\("
    )
    _COLLECTION_CONSTRUCTOR_RE = re.compile(
        r"new\s+[A-Z][A-Za-z0-9_<>]*\s*\(\s*(?P<source>[A-Za-z_][A-Za-z0-9_\.()]+)\s*\)"
    )
    _ADD_ALL_RE = re.compile(
        r"(?P<target>[A-Za-z_][A-Za-z0-9_\.]+)\.addAll\s*\(\s*(?P<source>[A-Za-z_][A-Za-z0-9_\.()]+)\s*\)"
    )
    _ADD_RE = re.compile(
        r"(?P<target>[A-Za-z_][A-Za-z0-9_\.]+)\.add\s*\(\s*(?P<source>[^;]+?)\s*\)$"
    )

    def parse_assignment_chain(
        self,
        *,
        source_payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        assignments = source_payload.get("assignments") or []
        edges: List[Dict[str, Any]] = []
        variable_map: Dict[str, str] = {}
        for assignment in assignments:
            if isinstance(assignment, dict):
                edge = self._parse_assignment_dict(assignment)
                if edge:
                    edges.append(edge)
                continue
            parsed_edges = self._parse_assignment_or_builder_text(str(assignment), variable_map=variable_map)
            edges.extend(parsed_edges)
        return self._dedupe_edges(edges)

    def parse_source_text(
        self,
        *,
        source_text: str,
        default_api_prefix: str = "body",
    ) -> List[Dict[str, Any]]:
        edges: List[Dict[str, Any]] = []
        if not source_text:
            return edges

        variable_map: Dict[str, str] = {}
        for raw_line in source_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue
            for edge in self._parse_assignment_or_builder_text(line, variable_map=variable_map):
                api_field_path = str(edge.get("api_field_path") or edge.get("target_field") or "")
                if api_field_path and "." not in api_field_path:
                    edge["api_field_path"] = f"{default_api_prefix}.{api_field_path}"
                edges.append(edge)
        return self._dedupe_edges(edges)

    def _parse_assignment_dict(self, assignment: Dict[str, Any]) -> Dict[str, Any] | None:
        target_field = str(assignment.get("target_field") or "").strip()
        source_field = str(assignment.get("source_field") or "").strip()
        if not target_field or not source_field:
            return None
        normalized_source = self._normalize_source_expression(source_field)
        source_object, source_leaf = self._split_ref(normalized_source)
        target_object, target_leaf = self._split_ref(target_field)
        return {
            "api_field_path": str(assignment.get("api_field_path") or target_leaf),
            "target_field": target_leaf,
            "target_object": target_object,
            "target_chain": target_field,
            "source_field": source_leaf,
            "source_object": source_object,
            "source_chain": normalized_source,
            "db_table": assignment.get("db_table"),
            "db_column": assignment.get("db_column"),
            "chain_depth": max(normalized_source.count(".") + 1, 1),
            "assignment_kind": str(assignment.get("assignment_kind") or "direct"),
            "transform_hint": str(assignment.get("transform_hint") or ""),
            "intermediate_variable_hit": bool(assignment.get("intermediate_variable_hit")),
            "evidence_type": str(assignment.get("evidence_type") or "code_assignment"),
            "confidence": float(assignment.get("confidence", 0.93) or 0.93),
            "payload": assignment,
        }

    def _parse_assignment_or_builder_text(
        self,
        assignment: str,
        *,
        variable_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        edges: List[Dict[str, Any]] = []
        line = str(assignment or "").strip().rstrip(";")
        if not line:
            return edges

        if self._looks_like_variable_definition(line):
            variable_name, source_ref = self._parse_variable_definition(line)
            if variable_name and source_ref:
                variable_map[variable_name] = source_ref

        if ".builder()" in line and ".build()" in line:
            edges.extend(self._parse_builder_chain(line, variable_map=variable_map))

        bean_copy_edge = self._parse_bean_copy(line, variable_map=variable_map)
        if bean_copy_edge:
            edges.append(bean_copy_edge)

        collection_edge = self._parse_collection_add_all(line, variable_map=variable_map)
        if collection_edge:
            edges.append(collection_edge)

        foreach_edge = self._parse_foreach_add(line, variable_map=variable_map)
        if foreach_edge:
            edges.append(foreach_edge)

        simple_edge = self._parse_assignment_text(line, variable_map=variable_map)
        if simple_edge:
            edges.append(simple_edge)
        return edges

    def _parse_assignment_text(
        self,
        assignment: str,
        *,
        variable_map: Dict[str, str],
    ) -> Dict[str, Any] | None:
        setter_edge = self._parse_setter_assignment(assignment, variable_map=variable_map)
        if setter_edge:
            return setter_edge

        for pattern_name, pattern in (
            ("mapper_annotation", self._MAPSTRUCT_RE),
            ("property_assignment", self._ASSIGNMENT_RE),
        ):
            match = pattern.search(assignment or "")
            if not match:
                continue
            target_field = match.group("target")
            source_ref = match.group("source")
            return self._build_edge(
                target_field=target_field,
                source_ref=source_ref,
                variable_map=variable_map,
                evidence_type="mapper_annotation" if pattern_name == "mapper_annotation" else "code_assignment",
                assignment_kind="nested" if self._is_nested_expression(source_ref) else "direct",
                raw_assignment=assignment,
            )
        return None

    def _parse_setter_assignment(
        self,
        assignment: str,
        *,
        variable_map: Dict[str, str],
    ) -> Dict[str, Any] | None:
        match = self._SETTER_NAME_RE.search(assignment or "")
        if not match:
            return None
        target_field = self._camel_to_snake(match.group("target"))
        source_ref = self._extract_call_argument(assignment, match.end() - 1)
        if not source_ref:
            return None
        return self._build_edge(
            target_field=target_field,
            source_ref=source_ref,
            variable_map=variable_map,
            evidence_type="code_assignment",
            assignment_kind="nested" if self._is_nested_expression(source_ref) else "direct",
            raw_assignment=assignment,
        )

    def _parse_builder_chain(
        self,
        assignment: str,
        *,
        variable_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        edges: List[Dict[str, Any]] = []
        for match in self._BUILDER_STEP_RE.finditer(assignment):
            target_name = str(match.group("target") or "").strip()
            if target_name in {"builder", "build"}:
                continue
            source_ref = str(match.group("source") or "").strip()
            if not source_ref or "," in source_ref:
                continue
            edge = self._build_edge(
                target_field=target_name,
                source_ref=source_ref,
                variable_map=variable_map,
                evidence_type="code_assignment",
                assignment_kind="builder",
                raw_assignment=assignment,
            )
            if edge:
                edges.append(edge)
        return edges

    def _build_edge(
        self,
        *,
        target_field: str,
        source_ref: str,
        variable_map: Dict[str, str],
        evidence_type: str,
        assignment_kind: str,
        raw_assignment: str,
    ) -> Dict[str, Any] | None:
        collection_source = self._extract_collection_source(source_ref)
        if collection_source:
            normalized_source = self._normalize_source_expression(collection_source)
            resolved_source, intermediate_hit = self._resolve_variable_reference(normalized_source, variable_map)
            if not resolved_source:
                return None
            source_object, source_leaf = self._split_ref(resolved_source)
            target_object, target_leaf = self._split_ref(target_field)
            return {
                "api_field_path": target_leaf,
                "target_field": target_leaf,
                "target_object": target_object,
                "target_chain": target_field,
                "source_field": source_leaf,
                "source_object": source_object,
                "source_chain": resolved_source,
                "db_table": None,
                "db_column": source_leaf,
                "chain_depth": max(resolved_source.count(".") + 1, 1),
                "assignment_kind": "collection_copy",
                "transform_hint": "collection.copy",
                "intermediate_variable_hit": intermediate_hit,
                "evidence_type": evidence_type,
                "confidence": 0.88,
                "payload": {"assignment": raw_assignment, "transform_hint": "collection.copy"},
            }

        stream_transform = self._extract_stream_map_transform(source_ref)
        if stream_transform:
            resolved_source, intermediate_hit = self._resolve_variable_reference(
                self._normalize_source_expression(stream_transform["source_chain"]),
                variable_map,
            )
            if not resolved_source:
                return None
            source_object, source_leaf = self._split_ref(resolved_source)
            target_object, target_leaf = self._split_ref(target_field)
            return {
                "api_field_path": target_leaf,
                "target_field": target_leaf,
                "target_object": target_object,
                "target_chain": target_field,
                "source_field": source_leaf,
                "source_object": source_object,
                "source_chain": resolved_source,
                "db_table": None,
                "db_column": source_leaf,
                "chain_depth": max(resolved_source.count(".") + 1, 1),
                "assignment_kind": "stream_map",
                "transform_hint": stream_transform["transform_hint"],
                "intermediate_variable_hit": intermediate_hit,
                "evidence_type": evidence_type,
                "confidence": 0.89,
                "payload": {"assignment": raw_assignment, "transform_hint": stream_transform["transform_hint"]},
            }

        normalized_source, transform_hints = self._normalize_source_expression_with_hints(source_ref)
        resolved_source, intermediate_hit = self._resolve_variable_reference(normalized_source, variable_map)
        if not resolved_source:
            return None
        source_object, source_leaf = self._split_ref(resolved_source)
        target_object, target_leaf = self._split_ref(target_field)
        final_kind = assignment_kind
        transform_hint = "|".join(transform_hints)
        if transform_hint:
            final_kind = "converter"
        elif assignment_kind == "direct" and self._is_nested_expression(resolved_source):
            final_kind = "nested"
        return {
            "api_field_path": target_leaf,
            "target_field": target_leaf,
            "target_object": target_object,
            "target_chain": target_field,
            "source_field": source_leaf,
            "source_object": source_object,
            "source_chain": resolved_source,
            "db_table": None,
            "db_column": source_leaf,
            "chain_depth": max(resolved_source.count(".") + 1, 1),
            "assignment_kind": final_kind,
            "transform_hint": transform_hint,
            "intermediate_variable_hit": intermediate_hit,
            "evidence_type": evidence_type,
            "confidence": 0.94 if evidence_type == "mapper_annotation" else 0.9,
            "payload": {"assignment": raw_assignment, "transform_hint": transform_hint},
        }

    def _parse_bean_copy(
        self,
        assignment: str,
        *,
        variable_map: Dict[str, str],
    ) -> Dict[str, Any] | None:
        match = self._BEAN_COPY_RE.search(assignment or "")
        if not match:
            return None
        source_ref = self._normalize_source_expression(str(match.group("source") or ""))
        target_ref = self._normalize_source_expression(str(match.group("target") or ""))
        resolved_source, intermediate_hit = self._resolve_variable_reference(source_ref, variable_map)
        if not resolved_source or not target_ref:
            return None
        target_object, _ = self._split_ref(target_ref)
        ignore_fields, include_fields = self._parse_bean_copy_field_rules(
            str(match.group("extra") or ""),
            method_name=str(match.group("method") or ""),
        )
        return {
            "api_field_path": "*",
            "target_field": "*",
            "target_object": target_object or target_ref,
            "target_chain": target_ref,
            "source_field": "*",
            "source_object": self._split_ref(resolved_source)[0],
            "source_chain": resolved_source,
            "db_table": None,
            "db_column": "*",
            "chain_depth": max(resolved_source.count(".") + 1, 1),
            "assignment_kind": "bean_copy",
            "transform_hint": "",
            "intermediate_variable_hit": intermediate_hit,
            "evidence_type": "bean_copy",
            "confidence": 0.82,
            "payload": {
                "assignment": assignment,
                "copy_mode": "same_name_field_copy",
                "ignore_fields": ignore_fields,
                "include_fields": include_fields,
            },
        }

    def _parse_collection_add_all(
        self,
        assignment: str,
        *,
        variable_map: Dict[str, str],
    ) -> Dict[str, Any] | None:
        match = self._ADD_ALL_RE.search(assignment or "")
        if not match:
            return None
        return self._build_edge(
            target_field=str(match.group("target") or ""),
            source_ref=str(match.group("source") or ""),
            variable_map=variable_map,
            evidence_type="code_assignment",
            assignment_kind="collection_copy",
            raw_assignment=assignment,
        )

    def _parse_foreach_add(
        self,
        assignment: str,
        *,
        variable_map: Dict[str, str],
    ) -> Dict[str, Any] | None:
        text = str(assignment or "").strip().rstrip(";")
        foreach_index = text.find(".forEach(")
        if foreach_index <= 0:
            return None
        root = text[:foreach_index].strip()
        lambda_payload = self._extract_call_argument(text, foreach_index + len(".forEach"))
        if "->" not in lambda_payload:
            return None
        lambda_var, lambda_body = [part.strip() for part in lambda_payload.split("->", 1)]
        if not lambda_var or not lambda_body:
            return None
        lambda_body = lambda_body.strip()
        if lambda_body.startswith("{") and lambda_body.endswith("}"):
            lambda_body = lambda_body[1:-1].strip()

        normalized_root = self._normalize_source_expression(root)
        local_variable_map: Dict[str, str] = {}
        add_target = ""
        add_source = ""
        intermediate_hit = False
        for statement in [segment.strip() for segment in lambda_body.split(";") if segment.strip()]:
            variable_name, source_ref = self._parse_variable_definition(statement)
            if variable_name and source_ref:
                expanded_source = self._expand_lambda_source(
                    base_chain=normalized_root,
                    lambda_var=lambda_var,
                    expression=source_ref,
                    local_variable_map=local_variable_map,
                )
                if expanded_source:
                    local_variable_map[variable_name] = expanded_source
                continue
            add_match = self._ADD_RE.search(statement)
            if not add_match:
                continue
            add_target = str(add_match.group("target") or "").strip()
            add_source = str(add_match.group("source") or "").strip()
            intermediate_hit = add_source in local_variable_map
        if not add_target or not add_source:
            return None

        resolved_source = self._expand_lambda_source(
            base_chain=normalized_root,
            lambda_var=lambda_var,
            expression=add_source,
            local_variable_map=local_variable_map,
        )
        if not resolved_source:
            return None
        target_object, target_leaf = self._split_ref(add_target)
        source_object, source_leaf = self._split_ref(resolved_source)
        return {
            "api_field_path": target_leaf,
            "target_field": target_leaf,
            "target_object": target_object,
            "target_chain": add_target,
            "source_field": source_leaf,
            "source_object": source_object,
            "source_chain": resolved_source,
            "db_table": None,
            "db_column": source_leaf,
            "chain_depth": max(resolved_source.count(".") + 1, 1),
            "assignment_kind": "foreach_add",
            "transform_hint": "foreach.add",
            "intermediate_variable_hit": intermediate_hit,
            "evidence_type": "code_assignment",
            "confidence": 0.88,
            "payload": {"assignment": assignment, "transform_hint": "foreach.add"},
        }

    def _looks_like_variable_definition(self, line: str) -> bool:
        return bool(self._VAR_DECL_RE.match(line)) and ".builder()" not in line and line.count("=") == 1

    def _parse_variable_definition(self, line: str) -> tuple[str | None, str | None]:
        match = self._VAR_DECL_RE.match(line)
        if not match:
            return None, None
        variable_name = str(match.group("name") or "").strip()
        source_ref = self._normalize_source_expression(str(match.group("source") or "").strip())
        if not variable_name or not source_ref:
            return None, None
        return variable_name, source_ref

    def _resolve_variable_reference(self, source_ref: str, variable_map: Dict[str, str]) -> tuple[str, bool]:
        parts = [part for part in str(source_ref or "").split(".") if part]
        if not parts:
            return "", False
        root = parts[0]
        resolved_root = variable_map.get(root)
        if not resolved_root:
            return ".".join(parts), False
        suffix = ".".join(parts[1:])
        resolved = f"{resolved_root}.{suffix}" if suffix else resolved_root
        return resolved, True

    def _normalize_source_expression(self, source_ref: str) -> str:
        normalized, _ = self._normalize_source_expression_with_hints(source_ref)
        return normalized

    def _normalize_source_expression_with_hints(self, source_ref: str) -> tuple[str, List[str]]:
        normalized = str(source_ref or "").strip().rstrip(";")
        normalized, transform_hints = self._unwrap_converter_chain(normalized)
        normalized = self._GETTER_CALL_RE.sub(lambda m: f".{self._lower_camel(m.group(1))}", normalized)
        normalized = self._IS_CALL_RE.sub(lambda m: f".{self._lower_camel(m.group(1))}", normalized)
        normalized = self._NOARG_CALL_RE.sub(lambda m: f".{m.group('name')}", normalized)
        normalized = normalized.replace("(", "").replace(")", "")
        normalized = normalized.replace("?.", ".")
        normalized = re.sub(r"\s+", "", normalized)
        normalized = re.sub(r"\.+", ".", normalized).strip(".")
        return normalized, transform_hints

    def _unwrap_converter_chain(self, value: str) -> tuple[str, List[str]]:
        normalized = str(value or "").strip()
        transform_hints: List[str] = []
        while True:
            match = self._CONVERTER_CALL_RE.search(normalized)
            if not match:
                return normalized, transform_hints
            prefix = str(match.group("prefix") or "").strip(".")
            converter = str(match.group("converter") or "")
            transform_hint = ".".join(part for part in (prefix, converter) if part)
            if transform_hint:
                transform_hints.append(transform_hint)
            open_paren_index = match.end() - 1
            inner = self._extract_call_argument(normalized, open_paren_index)
            if not inner:
                return normalized, transform_hints
            normalized = inner

    def _extract_call_argument(self, text: str, open_paren_index: int) -> str:
        depth = 0
        argument_chars: List[str] = []
        for index in range(open_paren_index, len(text)):
            char = text[index]
            if char == "(":
                depth += 1
                if depth == 1:
                    continue
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            if depth >= 1:
                argument_chars.append(char)
        return "".join(argument_chars).strip()

    def _extract_collection_source(self, source_ref: str) -> str:
        match = self._COLLECTION_CONSTRUCTOR_RE.search(str(source_ref or ""))
        if not match:
            return ""
        return str(match.group("source") or "").strip()

    def _extract_stream_map_transform(self, source_ref: str) -> Dict[str, str] | None:
        text = str(source_ref or "").strip()
        stream_index = text.find(".stream()")
        if stream_index <= 0:
            return None
        root = text[:stream_index].strip()
        current_chain = self._normalize_source_expression(root)

        flat_map_index = text.find(".flatMap(", stream_index)
        map_index = text.find(".map(", stream_index)
        if flat_map_index > 0 and (map_index < 0 or flat_map_index < map_index):
            flatmap_payload = self._extract_call_argument(text, flat_map_index + len(".flatMap"))
            expanded_flatmap = self._expand_lambda_source(
                base_chain=current_chain,
                lambda_var="",
                expression=flatmap_payload,
                local_variable_map={},
                allow_raw_lambda=True,
            )
            if expanded_flatmap:
                current_chain = expanded_flatmap
            map_index = text.find(".map(", flat_map_index)
        if map_index <= 0:
            return None
        lambda_payload = self._extract_call_argument(text, map_index + len(".map"))
        normalized_chain = self._expand_lambda_source(
            base_chain=current_chain,
            lambda_var="",
            expression=lambda_payload,
            local_variable_map={},
            allow_raw_lambda=True,
        )
        if not normalized_chain:
            return None
        transform_hint = "stream.map"
        if ".filter(" in text:
            transform_hint = "stream.filter.map"
        if ".flatMap(" in text:
            transform_hint = f"{transform_hint}.flatMap"
        if ".collect(" in text:
            transform_hint = "stream.map.collect"
        elif ".toList(" in text or text.endswith(".toList()"):
            transform_hint = "stream.map.toList"
        elif ".toSet(" in text or text.endswith(".toSet()"):
            transform_hint = "stream.map.toSet"
        return {"source_chain": normalized_chain, "transform_hint": transform_hint}

    def _expand_lambda_source(
        self,
        *,
        base_chain: str,
        lambda_var: str,
        expression: str,
        local_variable_map: Dict[str, str],
        allow_raw_lambda: bool = False,
    ) -> str:
        payload = str(expression or "").strip()
        effective_lambda_var = lambda_var
        effective_expression = payload
        if allow_raw_lambda and "->" in payload:
            effective_lambda_var, effective_expression = [part.strip() for part in payload.split("->", 1)]
        normalized_expr = self._normalize_source_expression(effective_expression)
        if normalized_expr in local_variable_map:
            return local_variable_map[normalized_expr]
        if normalized_expr.endswith(".stream"):
            normalized_expr = normalized_expr[: -len(".stream")]
        if effective_lambda_var and normalized_expr == effective_lambda_var:
            return base_chain
        if effective_lambda_var and normalized_expr.startswith(f"{effective_lambda_var}."):
            suffix = normalized_expr[len(effective_lambda_var) + 1 :]
            return f"{base_chain}.{suffix}" if suffix else base_chain
        return normalized_expr or base_chain

    def _is_nested_expression(self, source_ref: str) -> bool:
        return str(source_ref or "").count(".") >= 1

    def _split_ref(self, ref: str) -> tuple[str | None, str]:
        parts = [part for part in str(ref or "").split(".") if part]
        if not parts:
            return None, ""
        if len(parts) == 1:
            return None, parts[0]
        return ".".join(parts[:-1]), parts[-1]

    def _camel_to_snake(self, value: str) -> str:
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
        return normalized.lower()

    def _lower_camel(self, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            return cleaned
        return cleaned[0].lower() + cleaned[1:]

    def _parse_bean_copy_field_rules(self, extra: str, *, method_name: str = "") -> tuple[List[str], List[str]]:
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', str(extra or ""))
        fields = [item[0] or item[1] for item in quoted if item[0] or item[1]]
        method = str(method_name or "").lower()
        if any(keyword in method for keyword in ("include", "selected", "selective", "only")):
            return [], fields
        return fields, []

    def _extract_transform_hint(self, source_ref: str) -> str:
        _, transform_hints = self._normalize_source_expression_with_hints(source_ref)
        return "|".join(transform_hints)

    def _dedupe_edges(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for edge in edges:
            dedupe_key = (
                str(edge.get("target_field") or ""),
                str(edge.get("source_chain") or edge.get("source_field") or ""),
                str(edge.get("evidence_type") or ""),
                str(edge.get("assignment_kind") or ""),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deduped.append(edge)
        return deduped
