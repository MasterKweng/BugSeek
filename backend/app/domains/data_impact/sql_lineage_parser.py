"""Helpers for extracting SQL lineage edges with richer structure."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)


class SQLLineageParser:
    """Parse SQL into structured projection lineage edges using sqlglot only."""

    def parse_sql(
        self,
        *,
        sql_text: str,
        dialect: str | None = None,
    ) -> List[Dict[str, Any]]:
        return self._parse_select_sql(
            sql_text=sql_text,
            inherited_cte_source_map={},
            inherited_cte_projection_map={},
            dialect=dialect,
        )

    def _parse_select_sql(
        self,
        *,
        sql_text: str,
        inherited_cte_source_map: Dict[str, List[str]],
        inherited_cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
        dialect: str | None = None,
    ) -> List[Dict[str, Any]]:
        logger.debug(
            "SQL lineage parser dispatch: engine=sqlglot, dialect=%s, sql_length=%s",
            dialect or "default",
            len(sql_text or ""),
        )
        parsed = sqlglot.parse_one(sql_text or "", read=dialect)
        if parsed is None:
            logger.debug("SQL lineage parser completed with sqlglot: edges=0")
            return []

        cte_source_map, cte_projection_map = self._extract_cte_details_sqlglot(
            parsed,
            inherited_cte_source_map=inherited_cte_source_map,
            inherited_cte_projection_map=inherited_cte_projection_map,
            dialect=dialect,
        )
        merged_cte_source_map = {**inherited_cte_source_map, **cte_source_map}
        merged_cte_projection_map = {**inherited_cte_projection_map, **cte_projection_map}

        if isinstance(parsed, exp.Union):
            edges = self._parse_union_sqlglot(
                parsed,
                inherited_cte_source_map=merged_cte_source_map,
                inherited_cte_projection_map=merged_cte_projection_map,
                dialect=dialect,
            )
            logger.debug("SQL lineage parser completed with sqlglot: edges=%s", len(edges))
            return edges

        select_expr = parsed if isinstance(parsed, exp.Select) else parsed.find(exp.Select)
        if select_expr is None:
            logger.debug("SQL lineage parser completed with sqlglot: edges=0")
            return []

        table_alias_map, join_path, alias_origin_map = self._extract_table_context_sqlglot(
            select_expr,
            cte_source_map=merged_cte_source_map,
            inherited_cte_projection_map=merged_cte_projection_map,
            dialect=dialect,
        )
        projections = self._extract_projections_sqlglot(select_expr)
        if not table_alias_map:
            logger.debug("SQL lineage parser completed with sqlglot: edges=0")
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
                edges.append(
                    self._build_projection_edge(
                        projection=projection,
                        source_table=source_table,
                        source_column=source_column,
                        resolved_refs=resolved_refs,
                        cte_projection=cte_projection,
                        cte_source_map=merged_cte_source_map,
                        source_refs=source_refs,
                        join_path=join_path,
                        sql_text=sql_text,
                    )
                )
        logger.debug("SQL lineage parser completed with sqlglot: edges=%s", len(edges))
        return edges

    def _parse_union_sqlglot(
        self,
        union_expr: Any,
        *,
        inherited_cte_source_map: Dict[str, List[str]],
        inherited_cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
        dialect: str | None,
    ) -> List[Dict[str, Any]]:
        segments = self._flatten_union_sqlglot(union_expr)
        if not segments:
            return []

        canonical_aliases = self._extract_projection_alias_slots_sqlglot(segments[0])
        union_edges: List[Dict[str, Any]] = []
        for index, segment in enumerate(segments):
            segment_aliases = self._extract_projection_alias_slots_sqlglot(segment)
            segment_edges = self._parse_select_sql(
                sql_text=segment.sql(dialect=dialect),
                inherited_cte_source_map=inherited_cte_source_map,
                inherited_cte_projection_map=inherited_cte_projection_map,
                dialect=dialect,
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

    def _flatten_union_sqlglot(self, union_expr: Any) -> List[Any]:
        if not isinstance(union_expr, exp.Union):
            return [union_expr]
        segments: List[Any] = []
        left = union_expr.args.get("this")
        right = union_expr.args.get("expression")
        if isinstance(left, exp.Union):
            segments.extend(self._flatten_union_sqlglot(left))
        elif left is not None:
            segments.append(left)
        if isinstance(right, exp.Union):
            segments.extend(self._flatten_union_sqlglot(right))
        elif right is not None:
            segments.append(right)
        return segments

    def _extract_projection_alias_slots_sqlglot(self, expression: Any) -> List[str]:
        select_expr = expression if isinstance(expression, exp.Select) else expression.find(exp.Select)
        if select_expr is None:
            return []
        return [
            str(projection.get("projection_alias") or "")
            for projection in self._extract_projections_sqlglot(select_expr)
            if projection.get("projection_alias")
        ]

    def _extract_cte_details_sqlglot(
        self,
        expression: Any,
        *,
        inherited_cte_source_map: Dict[str, List[str]],
        inherited_cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
        dialect: str | None,
    ) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Dict[str, Any]]]]:
        with_expr = expression.args.get("with_") if hasattr(expression, "args") else None
        if not with_expr:
            return {}, {}

        source_map: Dict[str, List[str]] = {}
        projection_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for cte in with_expr.expressions or []:
            cte_name = self._normalize_name(getattr(cte, "alias_or_name", "") or "")
            cte_query = cte.args.get("this")
            if not cte_name or cte_query is None:
                continue
            cte_edges = self._parse_select_sql(
                sql_text=cte_query.sql(dialect=dialect),
                inherited_cte_source_map={**inherited_cte_source_map, **source_map},
                inherited_cte_projection_map={**inherited_cte_projection_map, **projection_map},
                dialect=dialect,
            )
            source_tables = sorted({str(edge.get("source_table") or "") for edge in cte_edges if edge.get("source_table")})
            if source_tables:
                source_map[cte_name] = source_tables
            projection_map[cte_name] = {
                self._normalize_name(str(edge.get("projection_alias") or "")): edge
                for edge in cte_edges
                if edge.get("projection_alias")
            }
        return source_map, projection_map

    def _extract_table_context_sqlglot(
        self,
        select_expr: Any,
        *,
        cte_source_map: Dict[str, List[str]],
        inherited_cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
        dialect: str | None,
    ) -> Tuple[Dict[str, List[str]], List[str], Dict[str, str]]:
        table_alias_map: Dict[str, List[str]] = {}
        join_path: List[str] = []
        alias_origin_map: Dict[str, str] = {}

        from_expr = select_expr.args.get("from_") if hasattr(select_expr, "args") else None
        if from_expr is not None and from_expr.this is not None:
            self._register_sqlglot_source(
                source_expr=from_expr.this,
                table_alias_map=table_alias_map,
                alias_origin_map=alias_origin_map,
                cte_source_map=cte_source_map,
                inherited_cte_projection_map=inherited_cte_projection_map,
                dialect=dialect,
            )

        for join_expr in (select_expr.args.get("joins") or []):
            joined_source = join_expr.args.get("this")
            if joined_source is None:
                continue
            self._register_sqlglot_source(
                source_expr=joined_source,
                table_alias_map=table_alias_map,
                alias_origin_map=alias_origin_map,
                cte_source_map=cte_source_map,
                inherited_cte_projection_map=inherited_cte_projection_map,
                dialect=dialect,
            )
            join_path.append(joined_source.sql(dialect=dialect))
        return table_alias_map, join_path, alias_origin_map

    def _register_sqlglot_source(
        self,
        *,
        source_expr: Any,
        table_alias_map: Dict[str, List[str]],
        alias_origin_map: Dict[str, str],
        cte_source_map: Dict[str, List[str]],
        inherited_cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
        dialect: str | None,
    ) -> None:
        resolved_tables, alias, table_name = self._resolve_sqlglot_source_tables(
            source_expr=source_expr,
            cte_source_map=cte_source_map,
            inherited_cte_projection_map=inherited_cte_projection_map,
            dialect=dialect,
        )
        if not resolved_tables:
            return
        if alias:
            table_alias_map[alias] = resolved_tables
            alias_origin_map[alias] = self._normalize_name(table_name or alias)
        if table_name:
            table_alias_map[table_name] = resolved_tables
            alias_origin_map[table_name] = self._normalize_name(table_name)
        for resolved_table in resolved_tables:
            table_alias_map.setdefault(resolved_table, [resolved_table])

    def _resolve_sqlglot_source_tables(
        self,
        *,
        source_expr: Any,
        cte_source_map: Dict[str, List[str]],
        inherited_cte_projection_map: Dict[str, Dict[str, Dict[str, Any]]],
        dialect: str | None,
    ) -> Tuple[List[str], str, str]:
        if isinstance(source_expr, exp.Table):
            table_name = self._normalize_name(source_expr.name)
            alias = self._normalize_name(source_expr.alias or table_name)
            resolved_tables = list(cte_source_map.get(table_name) or [table_name])
            return resolved_tables, alias, table_name
        if isinstance(source_expr, exp.Subquery):
            alias = self._normalize_name(source_expr.alias or "")
            inner_query = source_expr.this
            if inner_query is None:
                return [], alias, alias
            inner_edges = self._parse_select_sql(
                sql_text=inner_query.sql(dialect=dialect),
                inherited_cte_source_map=cte_source_map,
                inherited_cte_projection_map=inherited_cte_projection_map,
                dialect=dialect,
            )
            resolved_tables = sorted({str(edge.get("source_table") or "") for edge in inner_edges if edge.get("source_table")})
            return resolved_tables, alias, alias
        return [], "", ""

    def _extract_projections_sqlglot(self, select_expr: Any) -> List[Dict[str, Any]]:
        projections: List[Dict[str, Any]] = []
        for projection_expr in select_expr.expressions or []:
            parsed = self._parse_projection_sqlglot(projection_expr)
            if parsed:
                projections.append(parsed)
        return projections

    def _parse_projection_sqlglot(self, projection_expr: Any) -> Dict[str, Any] | None:
        expression = projection_expr.sql()
        alias = self._normalize_name(getattr(projection_expr, "alias", "") or "")
        base_expr = projection_expr.this if isinstance(projection_expr, exp.Alias) else projection_expr

        if isinstance(base_expr, exp.Star):
            return {
                "projection_alias": alias or "*",
                "source_column": "*",
                "source_refs": [],
                "expression_type": "wildcard",
                "expression": expression,
                "join_hit": False,
            }

        source_refs = self._extract_source_refs_sqlglot(base_expr)
        source_column = ""
        if isinstance(base_expr, exp.Column):
            source_column = self._normalize_name(base_expr.name)
        elif source_refs:
            source_column = source_refs[0][1]
        if not source_column:
            return None

        transform_type = self._classify_transform_sqlglot(base_expr)
        expression_type = "projection"
        if transform_type != "direct":
            expression_type = "expression"
        elif alias and alias != source_column:
            expression_type = "alias"

        return {
            "projection_alias": alias or self._normalize_name(source_column or expression),
            "source_column": self._normalize_name(source_column or expression),
            "source_refs": [(table, column) for table, column in source_refs if column],
            "expression_type": expression_type,
            "transform_type": transform_type,
            "expression": expression,
            "join_hit": len({table for table, _ in source_refs if table}) > 1,
            "cte_hit": False,
        }

    def _extract_source_refs_sqlglot(self, expression: Any) -> List[Tuple[str, str]]:
        refs: List[Tuple[str, str]] = []
        alias_map: Dict[str, str] = {}
        for table_expr in expression.find_all(exp.Table):
            table_name = self._normalize_name(getattr(table_expr, "name", "") or "")
            alias_name = self._normalize_name(getattr(table_expr, "alias", "") or table_name)
            if alias_name and table_name:
                alias_map[alias_name] = table_name
        for column_expr in expression.find_all(exp.Column):
            table_alias = self._normalize_name(getattr(column_expr, "table", "") or "")
            table_alias = alias_map.get(table_alias, table_alias)
            column_name = self._normalize_name(getattr(column_expr, "name", "") or "")
            if column_name:
                refs.append((table_alias, column_name))
        deduped: List[Tuple[str, str]] = []
        seen: set[Tuple[str, str]] = set()
        for ref in refs:
            if ref in seen:
                continue
            seen.add(ref)
            deduped.append(ref)
        return deduped

    def _classify_transform_sqlglot(self, expression: Any) -> str:
        if isinstance(expression, exp.Case):
            return "conditional"
        if isinstance(expression, exp.Window):
            return "window"
        if any(isinstance(node, exp.Subquery) for node in expression.walk()):
            return "correlated_subquery"
        if any(isinstance(node, exp.AggFunc) for node in expression.walk()):
            return "aggregate"
        if isinstance(expression, exp.Func) and not isinstance(expression, exp.Column):
            return "function_wrap"
        if isinstance(expression, (exp.Binary, exp.Paren, exp.Neg, exp.Not)):
            return "expression"
        return "direct"

    def _build_projection_edge(
        self,
        *,
        projection: Dict[str, Any],
        source_table: str,
        source_column: str,
        resolved_refs: List[Tuple[str, str]],
        cte_projection: Dict[str, Any],
        cte_source_map: Dict[str, List[str]],
        source_refs: List[Tuple[str, str]],
        join_path: List[str],
        sql_text: str,
    ) -> Dict[str, Any]:
        expression_type = self._resolve_expression_type(projection)
        transform_type = self._resolve_transform_type(projection=projection, cte_projection=cte_projection)
        cte_hit = self._resolve_cte_hit(
            projection=projection,
            cte_projection=cte_projection,
            cte_source_map=cte_source_map,
            source_refs=source_refs,
        )
        join_hit = self._resolve_join_hit(projection=projection, resolved_refs=resolved_refs)
        confidence = self._calculate_confidence(
            expression_type=expression_type,
            transform_type=transform_type,
            join_hit=join_hit,
        )
        return {
            "projection_alias": projection.get("projection_alias") or source_column,
            "source_table": source_table,
            "source_column": source_column,
            "source_tables": sorted({table for table, _ in resolved_refs if table}),
            "source_columns": sorted({column for _, column in resolved_refs if column}),
            "expression_type": expression_type,
            "transform_type": transform_type,
            "cte_hit": cte_hit,
            "aggregate_hit": transform_type == "aggregate",
            "conditional_hit": transform_type == "conditional",
            "function_wrap_hit": transform_type == "function_wrap",
            "window_hit": transform_type == "window",
            "subquery_hit": transform_type == "correlated_subquery",
            "union_hit": bool(projection.get("union_hit")),
            "join_hit": join_hit,
            "join_path": join_path,
            "confidence": confidence,
            "payload": {
                "sql_text": sql_text,
                "expression": projection.get("expression"),
            },
        }

    def _resolve_expression_type(self, projection: Dict[str, Any]) -> str:
        return str(projection.get("expression_type") or "projection")

    def _resolve_transform_type(
        self,
        *,
        projection: Dict[str, Any],
        cte_projection: Dict[str, Any],
    ) -> str:
        transform_type = str(projection.get("transform_type") or "direct")
        if transform_type == "direct":
            return str(cte_projection.get("transform_type") or transform_type)
        return transform_type

    def _resolve_cte_hit(
        self,
        *,
        projection: Dict[str, Any],
        cte_projection: Dict[str, Any],
        cte_source_map: Dict[str, List[str]],
        source_refs: List[Tuple[str, str]],
    ) -> bool:
        return bool(
            projection.get("cte_hit")
            or cte_projection
            or any(self._normalize_name(source_table) in cte_source_map for source_table, _ in source_refs if source_table)
        )

    def _resolve_join_hit(
        self,
        *,
        projection: Dict[str, Any],
        resolved_refs: List[Tuple[str, str]],
    ) -> bool:
        return bool(projection.get("join_hit") or len({table for table, _ in resolved_refs if table}) > 1)

    def _calculate_confidence(
        self,
        *,
        expression_type: str,
        transform_type: str,
        join_hit: bool,
    ) -> float:
        confidence = 0.9
        if expression_type == "alias":
            confidence = 0.96
        elif expression_type == "expression":
            confidence = 0.84
        elif join_hit:
            confidence = 0.93

        if transform_type == "aggregate":
            return min(confidence, 0.82)
        if transform_type == "conditional":
            return min(confidence, 0.8)
        if transform_type == "function_wrap":
            return min(confidence, 0.83)
        if transform_type == "window":
            return min(confidence, 0.81)
        if transform_type == "correlated_subquery":
            return min(confidence, 0.79)
        return confidence

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

    def _build_alias_positions(self, aliases: List[str]) -> Dict[str, List[int]]:
        positions: Dict[str, List[int]] = {}
        for index, alias in enumerate(aliases):
            positions.setdefault(str(alias), []).append(index)
        return positions

    def _normalize_name(self, value: str) -> str:
        cleaned = str(value or "").strip().strip("`\"")
        if "." in cleaned:
            cleaned = cleaned.split(".")[-1]
        return cleaned
