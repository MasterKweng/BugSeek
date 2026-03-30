"""Helpers for extracting SQL lineage edges with richer structure."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import sqlparse
from sqlparse.sql import Function, Identifier, IdentifierList, Operation, Parenthesis, Statement, Token
from sqlparse.tokens import DML, Keyword, Wildcard


class SQLLineageParser:
    """Parse SQL into structured projection lineage edges.

    The implementation still focuses on the common SELECT path, but now captures:
    - projection vs alias
    - simple expression projections
    - table aliases
    - joined source tables
    - multi-column source references inside expressions
    """

    _SOURCE_COLUMN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)")
    _TABLE_REF_RE = re.compile(
        r"\b(?:FROM|JOIN)\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)(?:\s+(?:AS\s+)?(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?",
        re.IGNORECASE,
    )

    def parse_sql(
        self,
        *,
        sql_text: str,
        dialect: str | None = None,
    ) -> List[Dict[str, Any]]:
        del dialect
        return self._parse_select_sql(
            sql_text=sql_text,
            inherited_cte_source_map={},
            inherited_cte_projection_map={},
        )

    def _parse_select_sql(
        self,
        *,
        sql_text: str,
        inherited_cte_source_map: Dict[str, List[str]],
        inherited_cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        union_segments = self._split_top_level_union(sql_text)
        if len(union_segments) > 1:
            union_edges: List[Dict[str, Any]] = []
            canonical_aliases = self._extract_projection_alias_slots(union_segments[0])
            for index, segment in enumerate(union_segments):
                segment_aliases = self._extract_projection_alias_slots(segment)
                segment_edges = self._parse_select_sql(
                    sql_text=segment,
                    inherited_cte_source_map=inherited_cte_source_map,
                    inherited_cte_projection_map=inherited_cte_projection_map,
                )
                alias_positions = self._build_alias_positions(segment_aliases)
                for edge in segment_edges:
                    alias_name = str(edge.get("projection_alias") or "")
                    slot_index = alias_positions.get(alias_name, [0]).pop(0) if alias_positions.get(alias_name) else None
                    if slot_index is not None and slot_index < len(canonical_aliases):
                        canonical_alias = canonical_aliases[slot_index]
                        if canonical_alias:
                            edge["projection_alias"] = canonical_alias
                    edge["union_hit"] = True
                    edge.setdefault("payload", {})["union_part_index"] = index
                union_edges.extend(segment_edges)
            return union_edges

        statement = next(iter(sqlparse.parse(sql_text or "")), None)
        if statement is None or self._extract_operation(statement) != "SELECT":
            return []

        cte_source_map, cte_projection_map = self._extract_cte_details(
            sql_text,
            inherited_cte_source_map=inherited_cte_source_map,
            inherited_cte_projection_map=inherited_cte_projection_map,
        )
        merged_cte_source_map = {**inherited_cte_source_map, **cte_source_map}
        merged_cte_projection_map = {**inherited_cte_projection_map, **cte_projection_map}
        table_alias_map, join_path, alias_origin_map = self._extract_table_context(
            statement,
            sql_text=sql_text,
            cte_source_map=merged_cte_source_map,
        )
        projections = self._extract_projections(statement)
        if not table_alias_map:
            return []

        edges: List[Dict[str, Any]] = []
        for projection in projections:
            source_refs = projection.get("source_refs") or []
            cte_projection = self._match_cte_projection(
                source_refs=source_refs,
                alias_origin_map=alias_origin_map,
                cte_projection_map=merged_cte_projection_map,
            )
            resolved_refs: List[Tuple[str, str]] = []
            for source_table, source_column in source_refs:
                resolved_tables = table_alias_map.get(source_table, [source_table]) if source_table else self._default_tables(table_alias_map)
                for resolved_table in resolved_tables:
                    resolved_refs.append((resolved_table, source_column))
            if not resolved_refs and projection.get("source_column") == "*":
                default_tables = self._default_tables(table_alias_map)
                resolved_refs = [(default_tables[0], "*")] if default_tables else []
            for source_table, source_column in resolved_refs:
                expression_type = str(projection.get("expression_type") or "projection")
                projection_transform = str(projection.get("transform_type") or "direct")
                transform_type = projection_transform
                if transform_type == "direct":
                    transform_type = str(cte_projection.get("transform_type") or transform_type)
                confidence = 0.9
                if expression_type == "alias":
                    confidence = 0.96
                elif expression_type == "expression":
                    confidence = 0.84
                elif projection.get("join_hit"):
                    confidence = 0.93
                if transform_type == "aggregate":
                    confidence = min(confidence, 0.82)
                elif transform_type == "conditional":
                    confidence = min(confidence, 0.8)
                elif transform_type == "function_wrap":
                    confidence = min(confidence, 0.83)
                elif transform_type == "window":
                    confidence = min(confidence, 0.81)
                elif transform_type == "correlated_subquery":
                    confidence = min(confidence, 0.79)
                edges.append(
                    {
                        "projection_alias": projection.get("projection_alias") or source_column,
                        "source_table": source_table,
                        "source_column": source_column,
                        "source_tables": sorted({table for table, _ in resolved_refs if table}),
                        "source_columns": sorted({column for _, column in resolved_refs if column}),
                        "expression_type": expression_type,
                        "transform_type": transform_type,
                        "cte_hit": bool(
                            projection.get("cte_hit")
                            or cte_projection
                            or any(self._normalize_name(source_table) in merged_cte_source_map for source_table, _ in source_refs if source_table)
                        ),
                        "aggregate_hit": transform_type == "aggregate",
                        "conditional_hit": transform_type == "conditional",
                        "function_wrap_hit": transform_type == "function_wrap",
                        "window_hit": transform_type == "window",
                        "subquery_hit": transform_type == "correlated_subquery",
                        "union_hit": bool(projection.get("union_hit")),
                        "join_hit": bool(projection.get("join_hit") or len({table for table, _ in resolved_refs if table}) > 1),
                        "join_path": join_path,
                        "confidence": confidence,
                        "payload": {
                            "sql_text": sql_text,
                            "expression": projection.get("expression"),
                        },
                    }
                )
        return edges

    def _extract_operation(self, statement: Statement) -> str | None:
        for token in statement.tokens:
            if token.ttype is DML:
                return str(token.value).upper()
        return None

    def _extract_table_context(
        self,
        statement: Statement,
        *,
        sql_text: str,
        cte_source_map: Dict[str, List[str]],
    ) -> Tuple[Dict[str, List[str]], List[str], Dict[str, str]]:
        table_alias_map: Dict[str, List[str]] = {}
        join_path: List[str] = []
        alias_origin_map: Dict[str, str] = {}
        tokens = [token for token in statement.tokens if not token.is_whitespace]
        index = 0
        while index < len(tokens):
            token = tokens[index]
            token_value = str(getattr(token, "value", "")).upper()
            if token.ttype is Keyword and token_value in {"FROM", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "LEFT OUTER JOIN"}:
                next_token = self._next_non_whitespace(tokens, index + 1)
                identifier = next_token if isinstance(next_token, Identifier) else None
                if identifier is not None:
                    alias = str(identifier.get_alias() or "").strip()
                    table_name = str(identifier.get_real_name() or identifier.get_name() or "").strip()
                    resolved_tables = self._resolve_identifier_tables(
                        identifier=identifier,
                        alias=alias,
                        table_name=table_name,
                        cte_source_map=cte_source_map,
                    )
                    if resolved_tables:
                        if alias:
                            table_alias_map[alias] = resolved_tables
                            alias_origin_map[alias] = self._normalize_name(table_name or alias)
                        if table_name:
                            table_alias_map[table_name] = resolved_tables
                            alias_origin_map[table_name] = self._normalize_name(table_name)
                        for resolved_table in resolved_tables:
                            table_alias_map.setdefault(resolved_table, [resolved_table])
                    if token_value != "FROM" and (table_name or alias):
                        join_path.append(str(identifier.value).strip())
            index += 1
        if not table_alias_map:
            table_alias_map, alias_origin_map = self._extract_table_context_from_text(sql_text=sql_text, cte_source_map=cte_source_map)
        return table_alias_map, join_path, alias_origin_map

    def _extract_projections(self, statement: Statement) -> List[Dict[str, Any]]:
        projections: List[Dict[str, Any]] = []
        seen_select = False
        for token in statement.tokens:
            if token.is_whitespace:
                continue
            token_value = str(getattr(token, "value", "")).upper()
            if token.ttype is DML and token_value == "SELECT":
                seen_select = True
                continue
            if not seen_select:
                continue
            if token.ttype is Keyword and token_value == "FROM":
                break
            if isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    parsed = self._parse_projection(identifier)
                    if parsed:
                        projections.append(parsed)
            elif isinstance(token, (Identifier, Function, Operation, Parenthesis)):
                parsed = self._parse_projection(token)
                if parsed:
                    projections.append(parsed)
            elif token.ttype is Wildcard:
                projections.append(
                    {
                        "projection_alias": "*",
                        "source_column": "*",
                        "source_refs": [],
                        "expression_type": "wildcard",
                        "expression": "*",
                        "join_hit": False,
                    }
                )
        return projections

    def _parse_projection(self, token: Token) -> Dict[str, Any] | None:
        expression = str(getattr(token, "value", "") or "").strip()
        if not expression:
            return None

        alias = token.get_alias() if isinstance(token, Identifier) else None
        source_refs = self._extract_source_refs(expression)
        source_column = ""
        if isinstance(token, Identifier):
            source_column = str(token.get_real_name() or token.get_name() or "").strip()
        if not source_column and source_refs:
            source_column = source_refs[0][1]
        if not source_column and expression != "*":
            source_column = self._extract_column_from_expression(expression) or ""
        if not source_column and expression != "*":
            return None

        transform_type = self._classify_transform(expression)
        expression_type = "projection"
        if transform_type != "direct":
            expression_type = "expression"
        elif alias and alias != source_column:
            expression_type = "alias"

        return {
            "projection_alias": self._normalize_name(alias or source_column or expression),
            "source_column": self._normalize_name(source_column or expression),
            "source_refs": [(table, column) for table, column in source_refs if column],
            "expression_type": expression_type,
            "transform_type": transform_type,
            "expression": expression,
            "join_hit": len({table for table, _ in source_refs if table}) > 1,
            "cte_hit": any(self._normalize_name(table) != table for table, _ in source_refs if table),
        }

    def _extract_source_refs(self, expression: str) -> List[Tuple[str, str]]:
        refs: List[Tuple[str, str]] = []
        subquery_alias_map = self._extract_subquery_alias_map(expression)
        for table_alias, column_name in self._SOURCE_COLUMN_RE.findall(expression or ""):
            normalized_alias = self._normalize_name(table_alias)
            refs.append((subquery_alias_map.get(normalized_alias, normalized_alias), self._normalize_name(column_name)))
        refs.extend(self._extract_subquery_refs(expression))
        if refs:
            deduped: List[Tuple[str, str]] = []
            seen: set[Tuple[str, str]] = set()
            for ref in refs:
                if ref in seen:
                    continue
                seen.add(ref)
                deduped.append(ref)
            return deduped
        column_name = self._extract_column_from_expression(expression or "")
        if column_name:
            refs.append(("", self._normalize_name(column_name)))
        return refs

    def _extract_column_from_expression(self, expression: str) -> str | None:
        matches = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)", expression or "")
        if not matches:
            return None
        ignored = {"as", "case", "when", "then", "else", "end", "concat", "sum", "count", "max", "min"}
        for match in reversed(matches):
            if match.lower() not in ignored:
                return match
        return None

    def _looks_like_expression(self, expression: str) -> bool:
        normalized = str(expression or "").lower()
        return any(marker in normalized for marker in ("(", " case ", " concat", " sum", " count", " max", " min", "+", "-", "*", "/"))

    def _classify_transform(self, expression: str) -> str:
        normalized = f" {str(expression or '').lower()} "
        if " case " in normalized and " when " in normalized:
            return "conditional"
        if re.search(r"\bover\s*\(", normalized):
            return "window"
        if re.search(r"\(\s*select\b", normalized):
            return "correlated_subquery"
        if re.search(r"\b(sum|count|max|min|avg)\s*\(", normalized):
            return "aggregate"
        if re.search(r"\b[a-z_][a-z0-9_]*\s*\(", normalized):
            return "function_wrap"
        if self._looks_like_expression(expression):
            return "expression"
        return "direct"

    def _extract_cte_details(
        self,
        sql_text: str,
        *,
        inherited_cte_source_map: Dict[str, List[str]],
        inherited_cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
    ) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Dict[str, Any]]]]:
        normalized = str(sql_text or "").strip()
        if not normalized.lower().startswith("with "):
            return {}, {}
        source_map: Dict[str, List[str]] = {}
        projection_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
        index = 4
        length = len(normalized)
        while index < length:
            while index < length and normalized[index].isspace():
                index += 1
            name_start = index
            while index < length and (normalized[index].isalnum() or normalized[index] == "_"):
                index += 1
            cte_name = normalized[name_start:index].strip()
            if not cte_name:
                break
            while index < length and normalized[index].isspace():
                index += 1
            if normalized[index:index + 2].lower() != "as":
                break
            index += 2
            while index < length and normalized[index].isspace():
                index += 1
            if index >= length or normalized[index] != "(":
                break
            subquery_text, index = self._consume_parenthesized_block(normalized, index)
            inner_sql = subquery_text[1:-1]
            cte_edges = self._parse_select_sql(
                sql_text=inner_sql,
                inherited_cte_source_map={**inherited_cte_source_map, **source_map},
                inherited_cte_projection_map={**inherited_cte_projection_map, **projection_map},
            )
            source_tables = sorted({str(edge.get("source_table") or "") for edge in cte_edges if edge.get("source_table")})
            cte_key = self._normalize_name(cte_name)
            if source_tables:
                source_map[cte_key] = source_tables
            projection_map[cte_key] = {
                self._normalize_name(str(edge.get("projection_alias") or "")): edge
                for edge in cte_edges
                if edge.get("projection_alias")
            }
            while index < length and normalized[index].isspace():
                index += 1
            if index >= length or normalized[index] != ",":
                break
            index += 1
        return source_map, projection_map

    def _consume_parenthesized_block(self, text: str, start_index: int) -> Tuple[str, int]:
        depth = 0
        for index in range(start_index, len(text)):
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return text[start_index:index + 1], index + 1
        return text[start_index:], len(text)

    def _resolve_identifier_tables(
        self,
        *,
        identifier: Identifier,
        alias: str,
        table_name: str,
        cte_source_map: Dict[str, List[str]],
    ) -> List[str]:
        normalized_alias = self._normalize_name(alias)
        normalized_table = self._normalize_name(table_name)
        if normalized_table in cte_source_map:
            return list(cte_source_map[normalized_table])
        if normalized_alias in cte_source_map:
            return list(cte_source_map[normalized_alias])

        identifier_value = str(identifier.value or "").strip()
        if "(" in identifier_value and ")" in identifier_value:
            inner_sql = self._extract_inner_select(identifier_value)
            if inner_sql:
                inner_edges = self.parse_sql(sql_text=inner_sql)
                source_tables = sorted({str(edge.get("source_table") or "") for edge in inner_edges if edge.get("source_table")})
                if source_tables:
                    return source_tables

        if normalized_table:
            return [normalized_table]
        return []

    def _extract_inner_select(self, identifier_value: str) -> str:
        start = identifier_value.find("(")
        if start < 0:
            return ""
        block, _ = self._consume_parenthesized_block(identifier_value, start)
        inner_sql = block[1:-1].strip()
        return inner_sql if inner_sql.lower().startswith("select") or inner_sql.lower().startswith("with ") else ""

    def _extract_table_context_from_text(
        self,
        *,
        sql_text: str,
        cte_source_map: Dict[str, List[str]],
    ) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
        table_alias_map: Dict[str, List[str]] = {}
        alias_origin_map: Dict[str, str] = {}
        for match in self._TABLE_REF_RE.finditer(sql_text or ""):
            table_name = self._normalize_name(match.group("table"))
            alias = self._normalize_name(match.group("alias") or table_name)
            resolved_tables = list(cte_source_map.get(table_name) or [table_name])
            if alias:
                table_alias_map[alias] = resolved_tables
                alias_origin_map[alias] = table_name
            if table_name:
                table_alias_map[table_name] = resolved_tables
                alias_origin_map[table_name] = table_name
            for resolved_table in resolved_tables:
                table_alias_map.setdefault(resolved_table, [resolved_table])
        return table_alias_map, alias_origin_map

    def _default_tables(self, table_alias_map: Dict[str, List[str]]) -> List[str]:
        tables = [
            table
            for key, values in table_alias_map.items()
            if key and values and len(values) == 1 and key == values[0]
            for table in values
        ]
        return tables or [values[0] for values in table_alias_map.values() if values]

    def _match_cte_projection(
        self,
        *,
        source_refs: List[Tuple[str, str]],
        alias_origin_map: Dict[str, str],
        cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        for source_table, source_column in source_refs:
            cte_name = alias_origin_map.get(source_table, source_table)
            cte_edges = cte_projection_map.get(self._normalize_name(cte_name)) or {}
            projection = cte_edges.get(self._normalize_name(source_column))
            if projection:
                return projection
        return {}

    def _extract_projection_alias_slots(self, sql_text: str) -> List[str]:
        statement = next(iter(sqlparse.parse(sql_text or "")), None)
        if statement is None:
            return []
        return [
            str(projection.get("projection_alias") or "")
            for projection in self._extract_projections(statement)
            if projection.get("projection_alias")
        ]

    def _build_alias_positions(self, aliases: List[str]) -> Dict[str, List[int]]:
        positions: Dict[str, List[int]] = {}
        for index, alias in enumerate(aliases):
            positions.setdefault(str(alias), []).append(index)
        return positions

    def _extract_subquery_refs(self, expression: str) -> List[Tuple[str, str]]:
        refs: List[Tuple[str, str]] = []
        for inner_sql in self._extract_embedded_selects(expression):
            alias_to_table: Dict[str, str] = {}
            for table_match in self._TABLE_REF_RE.finditer(inner_sql):
                table_name = self._normalize_name(table_match.group("table"))
                alias = self._normalize_name(table_match.group("alias") or table_name)
                if alias:
                    alias_to_table[alias] = table_name
            inner_edges = self.parse_sql(sql_text=inner_sql)
            for edge in inner_edges:
                source_table = self._normalize_name(str(edge.get("source_table") or ""))
                source_column = self._normalize_name(str(edge.get("source_column") or ""))
                if source_column:
                    refs.append((source_table, source_column))
            for table_alias, column_name in self._SOURCE_COLUMN_RE.findall(inner_sql or ""):
                resolved_table = alias_to_table.get(self._normalize_name(table_alias), self._normalize_name(table_alias))
                refs.append((resolved_table, self._normalize_name(column_name)))
        return refs

    def _extract_subquery_alias_map(self, expression: str) -> Dict[str, str]:
        alias_map: Dict[str, str] = {}
        for inner_sql in self._extract_embedded_selects(expression):
            for table_match in self._TABLE_REF_RE.finditer(inner_sql):
                table_name = self._normalize_name(table_match.group("table"))
                alias = self._normalize_name(table_match.group("alias") or table_name)
                if alias and table_name:
                    alias_map[alias] = table_name
        return alias_map

    def _extract_embedded_selects(self, text: str) -> List[str]:
        embedded: List[str] = []
        raw = str(text or "")
        search_index = 0
        while True:
            match = re.search(r"\(\s*select\b", raw[search_index:], re.IGNORECASE)
            if not match:
                break
            select_index = search_index + match.start()
            block, next_index = self._consume_parenthesized_block(raw, select_index)
            inner_sql = block[1:-1].strip()
            if inner_sql.lower().startswith("select") or inner_sql.lower().startswith("with "):
                embedded.append(inner_sql)
            search_index = next_index
        return embedded

    def _split_top_level_union(self, sql_text: str) -> List[str]:
        text = str(sql_text or "").strip()
        if not text:
            return []
        segments: List[str] = []
        depth = 0
        start = 0
        index = 0
        lowered = text.lower()
        while index < len(text):
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            if depth == 0 and lowered.startswith("union all", index):
                segment = text[start:index].strip()
                if segment:
                    segments.append(segment)
                index += len("union all")
                start = index
                continue
            if depth == 0 and lowered.startswith("union", index):
                segment = text[start:index].strip()
                if segment:
                    segments.append(segment)
                index += len("union")
                start = index
                continue
            index += 1
        tail = text[start:].strip()
        if tail:
            segments.append(tail)
        return segments if len(segments) > 1 else [text]

    def _next_non_whitespace(self, tokens: List[Token], start_index: int) -> Token | None:
        for token in tokens[start_index:]:
            if not token.is_whitespace:
                return token
        return None

    def _normalize_name(self, value: str) -> str:
        cleaned = str(value or "").strip().strip("`\"")
        if "." in cleaned:
            cleaned = cleaned.split(".")[-1]
        return cleaned
