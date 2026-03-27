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

    def parse_sql(
        self,
        *,
        sql_text: str,
        dialect: str | None = None,
    ) -> List[Dict[str, Any]]:
        del dialect
        statement = next(iter(sqlparse.parse(sql_text or "")), None)
        if statement is None or self._extract_operation(statement) != "SELECT":
            return []

        table_alias_map, join_path = self._extract_table_context(statement)
        projections = self._extract_projections(statement)
        if not table_alias_map:
            return []

        edges: List[Dict[str, Any]] = []
        for projection in projections:
            source_refs = projection.get("source_refs") or []
            resolved_refs = [
                (table_alias_map.get(source_table, source_table), source_column)
                for source_table, source_column in source_refs
            ]
            if not resolved_refs and projection.get("source_column") == "*":
                resolved_refs = [(next(iter(table_alias_map.values())), "*")]
            for source_table, source_column in resolved_refs:
                expression_type = str(projection.get("expression_type") or "projection")
                confidence = 0.9
                if expression_type == "alias":
                    confidence = 0.96
                elif expression_type == "expression":
                    confidence = 0.84
                elif projection.get("join_hit"):
                    confidence = 0.93
                edges.append(
                    {
                        "projection_alias": projection.get("projection_alias") or source_column,
                        "source_table": source_table,
                        "source_column": source_column,
                        "source_tables": sorted({table for table, _ in resolved_refs if table}),
                        "source_columns": sorted({column for _, column in resolved_refs if column}),
                        "expression_type": expression_type,
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

    def _extract_table_context(self, statement: Statement) -> Tuple[Dict[str, str], List[str]]:
        table_alias_map: Dict[str, str] = {}
        join_path: List[str] = []
        tokens = [token for token in statement.tokens if not token.is_whitespace]
        index = 0
        while index < len(tokens):
            token = tokens[index]
            token_value = str(getattr(token, "value", "")).upper()
            if token.ttype is Keyword and token_value in {"FROM", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "LEFT OUTER JOIN"}:
                next_token = self._next_non_whitespace(tokens, index + 1)
                identifier = next_token if isinstance(next_token, Identifier) else None
                if identifier is not None:
                    table_name = str(identifier.get_real_name() or identifier.get_name() or "").strip()
                    alias = str(identifier.get_alias() or table_name).strip()
                    if table_name:
                        table_alias_map[alias] = table_name
                        table_alias_map[table_name] = table_name
                    if token_value != "FROM" and table_name:
                        join_path.append(str(identifier.value).strip())
            index += 1
        return table_alias_map, join_path

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

        expression_type = "projection"
        if self._looks_like_expression(expression):
            expression_type = "expression"
        elif alias and alias != source_column:
            expression_type = "alias"

        return {
            "projection_alias": self._normalize_name(alias or source_column or expression),
            "source_column": self._normalize_name(source_column or expression),
            "source_refs": [(table, column) for table, column in source_refs if column],
            "expression_type": expression_type,
            "expression": expression,
            "join_hit": len({table for table, _ in source_refs if table}) > 1,
        }

    def _extract_source_refs(self, expression: str) -> List[Tuple[str, str]]:
        refs: List[Tuple[str, str]] = []
        for table_alias, column_name in self._SOURCE_COLUMN_RE.findall(expression or ""):
            refs.append((self._normalize_name(table_alias), self._normalize_name(column_name)))
        if refs:
            return refs
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
