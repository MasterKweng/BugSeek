"""Helpers for extracting lineage edges from ORM-style metadata."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List


class ORMLineageParser:
    """Normalize mapper metadata into a shared lineage edge format."""

    _TABLE_NAME_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
    _TABLE_ANNOTATION_RE = re.compile(r'@Table\s*\(\s*name\s*=\s*"(?P<table>[A-Za-z_][A-Za-z0-9_]*)"\s*\)')
    _COLUMN_FIELD_RE = re.compile(
        r'@Column\s*\(\s*name\s*=\s*"(?P<column>[A-Za-z_][A-Za-z0-9_]*)"\s*\)\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:private|protected|public)\s+[A-Za-z_][A-Za-z0-9_<>, ?\[\]]+\s+(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s*;',
        re.IGNORECASE | re.MULTILINE,
    )

    def parse_result_mapping(
        self,
        *,
        mapping_payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        mappings = mapping_payload.get("mappings") or []
        edges: List[Dict[str, Any]] = []
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            target_field = str(mapping.get("target_field") or mapping.get("property") or "").strip()
            source_column = str(mapping.get("source_column") or mapping.get("column") or "").strip()
            if not target_field or not source_column:
                continue
            edges.append(
                {
                    "api_field_path": str(mapping.get("api_field_path") or target_field),
                    "target_field": target_field,
                    "source_table": mapping.get("source_table"),
                    "source_column": source_column,
                    "evidence_type": "orm_mapping",
                    "confidence": float(mapping.get("confidence", 0.94) or 0.94),
                    "payload": mapping,
                }
            )
        return edges

    def parse_mapper_text(
        self,
        *,
        mapper_text: str,
        default_api_prefix: str = "body",
    ) -> List[Dict[str, Any]]:
        if not mapper_text:
            return []

        annotation_edges = self._parse_annotation_text(mapper_text=mapper_text, default_api_prefix=default_api_prefix)
        root = self._parse_xml_root(mapper_text)
        if root is None:
            fallback_edges = self._parse_mapper_text_fallback(mapper_text=mapper_text, default_api_prefix=default_api_prefix)
            return annotation_edges + fallback_edges

        select_table_map = self._build_select_table_map(root)
        default_select_tables = next(iter(select_table_map.values()), [])
        result_map_nodes = self._collect_result_maps(root)
        edges: List[Dict[str, Any]] = []
        for result_map_id, result_map_node in result_map_nodes.items():
            edges.extend(
                self._parse_result_map_node(
                    result_map_node=result_map_node,
                    result_map_nodes=result_map_nodes,
                    select_table_map=select_table_map,
                    default_api_prefix=default_api_prefix,
                    path_prefix="",
                    table_prefix=None,
                    inherited_select_id=None,
                    inherited_result_map_id=result_map_id,
                    default_select_tables=default_select_tables,
                )
            )
        return annotation_edges + edges

    def _parse_xml_root(self, mapper_text: str) -> ET.Element | None:
        try:
            return ET.fromstring(f"<root>{mapper_text}</root>")
        except ET.ParseError:
            return None

    def _build_select_table_map(self, root: ET.Element) -> Dict[str, List[str]]:
        table_map: Dict[str, List[str]] = {}
        for node in root:
            tag = self._local_name(node.tag)
            if tag != "select":
                continue
            select_id = str(node.attrib.get("id") or "").strip()
            sql_text = "".join(node.itertext())
            tables = self._extract_tables(sql_text)
            if select_id and tables:
                table_map[select_id] = tables
            result_map_id = str(node.attrib.get("resultMap") or "").strip()
            if result_map_id and tables:
                table_map.setdefault(result_map_id, tables)
        return table_map

    def _collect_result_maps(self, root: ET.Element) -> Dict[str, ET.Element]:
        result_maps: Dict[str, ET.Element] = {}
        for node in root.iter():
            if self._local_name(node.tag) != "resultMap":
                continue
            result_map_id = str(node.attrib.get("id") or "").strip()
            if result_map_id:
                result_maps[result_map_id] = node
        return result_maps

    def _parse_result_map_node(
        self,
        *,
        result_map_node: ET.Element,
        result_map_nodes: Dict[str, ET.Element],
        select_table_map: Dict[str, List[str]],
        default_api_prefix: str,
        path_prefix: str,
        table_prefix: str | None,
        inherited_select_id: str | None,
        inherited_result_map_id: str | None,
        default_select_tables: List[str],
    ) -> List[Dict[str, Any]]:
        edges: List[Dict[str, Any]] = []
        current_result_map_id = str(result_map_node.attrib.get("id") or inherited_result_map_id or "").strip() or None
        select_id = inherited_select_id
        if current_result_map_id and current_result_map_id in select_table_map:
            select_id = current_result_map_id

        for child in list(result_map_node):
            tag = self._local_name(child.tag)
            if tag in {"id", "result"}:
                edge = self._build_mapping_edge(
                    node=child,
                    default_api_prefix=default_api_prefix,
                    path_prefix=path_prefix,
                    table_prefix=table_prefix,
                    select_id=select_id,
                    select_table_map=select_table_map,
                    result_map_id=current_result_map_id,
                    default_select_tables=default_select_tables,
                )
                if edge:
                    edges.append(edge)
                continue
            if tag not in {"association", "collection"}:
                continue

            property_name = str(child.attrib.get("property") or "").strip()
            nested_prefix = self._join_property_path(path_prefix, property_name)
            nested_table_prefix = self._join_column_prefix(table_prefix, child.attrib.get("columnPrefix"))
            nested_select_id = str(child.attrib.get("select") or "").strip() or select_id
            nested_result_map_ref = str(child.attrib.get("resultMap") or "").strip()

            nested_simple_edge = self._build_mapping_edge(
                node=child,
                default_api_prefix=default_api_prefix,
                path_prefix=path_prefix,
                table_prefix=table_prefix,
                select_id=nested_select_id,
                select_table_map=select_table_map,
                result_map_id=current_result_map_id,
                default_select_tables=default_select_tables,
            )
            if nested_simple_edge:
                edges.append(nested_simple_edge)

            if nested_result_map_ref and nested_result_map_ref in result_map_nodes:
                edges.extend(
                    self._parse_result_map_node(
                        result_map_node=result_map_nodes[nested_result_map_ref],
                        result_map_nodes=result_map_nodes,
                        select_table_map=select_table_map,
                        default_api_prefix=default_api_prefix,
                        path_prefix=nested_prefix,
                        table_prefix=nested_table_prefix,
                        inherited_select_id=nested_select_id,
                        inherited_result_map_id=nested_result_map_ref,
                        default_select_tables=default_select_tables,
                    )
                )
                continue

            if list(child):
                edges.extend(
                    self._parse_result_map_node(
                        result_map_node=child,
                        result_map_nodes=result_map_nodes,
                        select_table_map=select_table_map,
                        default_api_prefix=default_api_prefix,
                        path_prefix=nested_prefix,
                        table_prefix=nested_table_prefix,
                        inherited_select_id=nested_select_id,
                        inherited_result_map_id=current_result_map_id,
                        default_select_tables=default_select_tables,
                    )
                )
        return edges

    def _build_mapping_edge(
        self,
        *,
        node: ET.Element,
        default_api_prefix: str,
        path_prefix: str,
        table_prefix: str | None,
        select_id: str | None,
        select_table_map: Dict[str, List[str]],
        result_map_id: str | None,
        default_select_tables: List[str],
    ) -> Dict[str, Any] | None:
        property_name = str(node.attrib.get("property") or "").strip()
        column_name = str(node.attrib.get("column") or "").strip()
        if not property_name or not column_name:
            return None

        property_path = self._join_property_path(path_prefix, property_name)
        api_field_path = property_path if "." in property_path else f"{default_api_prefix}.{property_path}"
        normalized_column = self._apply_column_prefix(table_prefix, column_name)
        source_tables = list(select_table_map.get(select_id or "", []))
        if not source_tables and result_map_id:
            source_tables = list(select_table_map.get(result_map_id, []))
        if not source_tables:
            source_tables = list(default_select_tables)
        source_table = source_tables[0] if source_tables else None

        return {
            "api_field_path": api_field_path,
            "target_field": property_path,
            "source_table": source_table,
            "source_tables": source_tables,
            "source_column": normalized_column,
            "evidence_type": "orm_mapping",
            "confidence": 0.95,
            "payload": {
                "select_id": select_id,
                "result_map_id": result_map_id,
                "property_path": property_path,
                "column_prefix": table_prefix,
            },
        }

    def _parse_mapper_text_fallback(
        self,
        *,
        mapper_text: str,
        default_api_prefix: str,
    ) -> List[Dict[str, Any]]:
        result_mapping_re = re.compile(
            r"<(?:id|result)\b[^>]*\bproperty\s*=\s*['\"](?P<property>[^'\"]+)['\"][^>]*\bcolumn\s*=\s*['\"](?P<column>[^'\"]+)['\"][^>]*/?>",
            re.IGNORECASE,
        )
        inferred_tables = self._extract_tables(mapper_text)
        source_table = inferred_tables[0] if inferred_tables else None
        edges: List[Dict[str, Any]] = []
        for match in result_mapping_re.finditer(mapper_text):
            target_field = str(match.group("property") or "").strip()
            source_column = str(match.group("column") or "").strip()
            if not target_field or not source_column:
                continue
            api_field_path = target_field if "." in target_field else f"{default_api_prefix}.{target_field}"
            edges.append(
                {
                    "api_field_path": api_field_path,
                    "target_field": target_field.split(".")[-1],
                    "source_table": source_table,
                    "source_column": source_column,
                    "evidence_type": "orm_mapping",
                    "confidence": 0.95,
                    "payload": {"mapper_text": mapper_text[:1000]},
                }
            )
        return edges

    def _parse_annotation_text(
        self,
        *,
        mapper_text: str,
        default_api_prefix: str,
    ) -> List[Dict[str, Any]]:
        table_match = self._TABLE_ANNOTATION_RE.search(mapper_text or "")
        source_table = str(table_match.group("table") or "").strip() if table_match else None
        edges: List[Dict[str, Any]] = []
        for match in self._COLUMN_FIELD_RE.finditer(mapper_text or ""):
            source_column = str(match.group("column") or "").strip()
            target_field = str(match.group("field") or "").strip()
            if not source_column or not target_field:
                continue
            edges.append(
                {
                    "api_field_path": f"{default_api_prefix}.{target_field}",
                    "target_field": target_field,
                    "source_table": source_table,
                    "source_tables": [source_table] if source_table else [],
                    "source_column": source_column,
                    "evidence_type": "orm_annotation",
                    "confidence": 0.9,
                    "payload": {
                        "annotation_mode": "jpa_column",
                        "table_name": source_table,
                    },
                }
            )
        return edges

    def _extract_tables(self, sql_text: str) -> List[str]:
        tables: List[str] = []
        for table_name in self._TABLE_NAME_RE.findall(sql_text or ""):
            normalized = str(table_name or "").strip()
            if normalized and normalized not in tables:
                tables.append(normalized)
        return tables

    def _join_property_path(self, path_prefix: str, property_name: str) -> str:
        clean_property = str(property_name or "").strip()
        if not clean_property:
            return path_prefix
        if not path_prefix:
            return clean_property
        if clean_property.startswith("["):
            return f"{path_prefix}{clean_property}"
        return f"{path_prefix}.{clean_property}"

    def _join_column_prefix(self, table_prefix: str | None, column_prefix: Any) -> str | None:
        parts = [str(table_prefix or "").strip(), str(column_prefix or "").strip()]
        joined = "".join(part for part in parts if part)
        return joined or None

    def _apply_column_prefix(self, table_prefix: str | None, column_name: str) -> str:
        prefix = str(table_prefix or "").strip()
        normalized_column = str(column_name or "").strip()
        return f"{prefix}{normalized_column}" if prefix else normalized_column

    def _local_name(self, tag: str) -> str:
        return str(tag or "").split("}", 1)[-1]
