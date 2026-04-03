"""Pluggable code-lineage analyzers for source files."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from app.platform.config.settings import settings
from .code_analysis.java_adapter_base import BaseJavaAdapter
from .code_analysis.java_adapter_registry import JavaAdapterRegistry
from .code_analysis.java_javalang_adapter import JavalangJavaAdapter
from .code_lineage_parser import CodeLineageParser


class SourceAnalyzer(Protocol):
    """Protocol for source analyzers that emit normalized code-lineage edges."""

    def supports(self, *, file_path: Optional[str]) -> bool:
        ...

    def analyze(
        self,
        *,
        source_text: str,
        file_path: Optional[str],
        default_api_prefix: str = "body",
    ) -> List[Dict[str, object]]:
        ...


class PythonAstCodeAnalyzer:
    """Use Python AST for assignment, constructor, dict, and collection lineage extraction."""

    _WRAPPER_FUNCS = {"str", "int", "float", "bool", "Decimal", "uuid4", "date", "datetime"}
    _MODEL_FACTORY_ATTRS = {"from_orm", "model_validate", "parse_obj"}
    _MODEL_DUMP_ATTRS = {"model_dump", "dict"}
    _DATACLASS_FUNCS = {"asdict"}
    _ORM_RESULT_ATTRS = {"first", "one", "one_or_none", "scalar", "scalar_one", "scalar_one_or_none"}
    _ORM_MAPPING_ATTRS = {"mappings", "fetchone", "fetchall"}
    _ORM_SCALAR_ATTRS = {"scalars"}

    def supports(self, *, file_path: Optional[str]) -> bool:
        return str(file_path or "").lower().endswith(".py")

    def analyze(
        self,
        *,
        source_text: str,
        file_path: Optional[str],
        default_api_prefix: str = "body",
    ) -> List[Dict[str, object]]:
        del file_path
        if not source_text.strip():
            return []
        try:
            tree = ast.parse(source_text)
        except SyntaxError:
            return []

        scope_vars: Dict[str, str] = {}
        model_scope: Dict[str, Dict[str, Dict[str, object]]] = {}
        edges = self._collect_python_edges(
            statements=list(getattr(tree, "body", []) or []),
            scope_vars=scope_vars,
            model_scope=model_scope,
            default_api_prefix=default_api_prefix,
        )
        return self._dedupe(edges)

    def _collect_python_edges(
        self,
        *,
        statements: List[ast.stmt],
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
        method_return_target: str | None = None,
    ) -> List[Dict[str, object]]:
        edges: List[Dict[str, object]] = []
        for node in statements:
            if isinstance(node, ast.Assign):
                serializer_edges = self._extract_serializer_field_edges(
                    node=node,
                    scope_vars=scope_vars,
                    model_scope=model_scope,
                    default_api_prefix=default_api_prefix,
                )
                if serializer_edges:
                    edges.extend(serializer_edges)
                    continue
                value_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                    node.value,
                    scope_vars=scope_vars,
                    model_scope=model_scope,
                )
                if not value_ref and not isinstance(node.value, ast.Dict):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and value_ref:
                        model_mapping = self._extract_model_field_map(
                            node.value,
                            scope_vars=scope_vars,
                            model_scope=model_scope,
                        )
                        if model_mapping:
                            model_scope[target.id] = model_mapping
                            continue
                        scope_vars[target.id] = value_ref
                        continue
                    target_ref = self._extract_target_ref(target)
                    if not target_ref:
                        continue
                    if isinstance(node.value, ast.Dict):
                        edges.extend(
                            self._extract_dict_assignment_edges(
                                target_ref=target_ref,
                                value=node.value,
                                scope_vars=scope_vars,
                                model_scope=model_scope,
                                default_api_prefix=default_api_prefix,
                            )
                        )
                        continue
                    edges.append(
                        self._build_edge(
                            target_ref=target_ref,
                            source_ref=value_ref,
                            default_api_prefix=default_api_prefix,
                            assignment_kind=assignment_kind,
                            transform_hint=transform_hint,
                            intermediate_variable_hit=intermediate_hit,
                        )
                    )
            elif isinstance(node, ast.AnnAssign):
                value_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                    node.value,
                    scope_vars=scope_vars,
                    model_scope=model_scope,
                )
                target_ref = self._extract_target_ref(node.target)
                if value_ref and target_ref:
                    if isinstance(node.target, ast.Name):
                        model_mapping = self._extract_model_field_map(
                            node.value,
                            scope_vars=scope_vars,
                            model_scope=model_scope,
                        )
                        if model_mapping:
                            model_scope[node.target.id] = model_mapping
                            continue
                        scope_vars[node.target.id] = value_ref
                        continue
                    edges.append(
                        self._build_edge(
                            target_ref=target_ref,
                            source_ref=value_ref,
                            default_api_prefix=default_api_prefix,
                            assignment_kind=assignment_kind,
                            transform_hint=transform_hint,
                            intermediate_variable_hit=intermediate_hit,
                        )
                    )
            elif isinstance(node, ast.Expr):
                edges.extend(
                    self._extract_expr_edges(
                        node=node,
                        scope_vars=scope_vars,
                        model_scope=model_scope,
                        default_api_prefix=default_api_prefix,
                    )
                )
            elif isinstance(node, ast.Return):
                edges.extend(
                    self._extract_return_edges(
                        node=node,
                        scope_vars=scope_vars,
                        model_scope=model_scope,
                        default_api_prefix=default_api_prefix,
                        method_return_target=method_return_target,
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_scope = dict(scope_vars)
                local_models = dict(model_scope)
                return_target = self._serializer_method_target(node.name)
                edges.extend(
                    self._collect_python_edges(
                        statements=list(node.body or []),
                        scope_vars=local_scope,
                        model_scope=local_models,
                        default_api_prefix=default_api_prefix,
                        method_return_target=return_target,
                    )
                )
            elif isinstance(node, ast.ClassDef):
                class_scope = dict(scope_vars)
                class_models = dict(model_scope)
                edges.extend(
                    self._collect_python_edges(
                        statements=list(node.body or []),
                        scope_vars=class_scope,
                        model_scope=class_models,
                        default_api_prefix=default_api_prefix,
                    )
                )
            elif isinstance(node, ast.If):
                branch_scope = dict(scope_vars)
                branch_models = dict(model_scope)
                edges.extend(
                    self._collect_python_edges(
                        statements=list(node.body or []),
                        scope_vars=branch_scope,
                        model_scope=branch_models,
                        default_api_prefix=default_api_prefix,
                        method_return_target=method_return_target,
                    )
                )
                orelse_scope = dict(scope_vars)
                orelse_models = dict(model_scope)
                edges.extend(
                    self._collect_python_edges(
                        statements=list(node.orelse or []),
                        scope_vars=orelse_scope,
                        model_scope=orelse_models,
                        default_api_prefix=default_api_prefix,
                        method_return_target=method_return_target,
                    )
                )
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
                nested_blocks: List[List[ast.stmt]] = []
                if hasattr(node, "body"):
                    nested_blocks.append(list(getattr(node, "body") or []))
                if hasattr(node, "orelse"):
                    nested_blocks.append(list(getattr(node, "orelse") or []))
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        nested_blocks.append(list(handler.body or []))
                    nested_blocks.append(list(node.finalbody or []))
                for block in nested_blocks:
                    nested_scope = dict(scope_vars)
                    nested_models = dict(model_scope)
                    edges.extend(
                        self._collect_python_edges(
                            statements=block,
                            scope_vars=nested_scope,
                            model_scope=nested_models,
                            default_api_prefix=default_api_prefix,
                            method_return_target=method_return_target,
                        )
                    )
        return edges

    def _extract_expr_edges(
        self,
        *,
        node: ast.Expr,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
    ) -> List[Dict[str, object]]:
        setter_edge = self._extract_setter_call(node=node, scope_vars=scope_vars, model_scope=model_scope, default_api_prefix=default_api_prefix)
        if setter_edge:
            return [setter_edge]
        call = node.value
        if isinstance(call, ast.Call):
            return self._extract_dict_update_edges(
                call=call,
                scope_vars=scope_vars,
                model_scope=model_scope,
                default_api_prefix=default_api_prefix,
            )
        return []

    def _extract_setter_call(
        self,
        *,
        node: ast.Expr,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
    ) -> Dict[str, object] | None:
        call = node.value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
            return None
        method_name = str(call.func.attr or "")
        if not method_name.startswith("set") or len(call.args) != 1:
            return None
        target_name = method_name[3:]
        if not target_name:
            return None
        source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
            call.args[0],
            scope_vars=scope_vars,
            model_scope=model_scope,
        )
        if not source_ref:
            return None
        target_ref = self._camel_to_snake(target_name)
        return self._build_edge(
            target_ref=target_ref,
            source_ref=source_ref,
            default_api_prefix=default_api_prefix,
            assignment_kind=assignment_kind,
            transform_hint=transform_hint,
            intermediate_variable_hit=intermediate_hit,
        )

    def _extract_target_ref(self, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Attribute):
            return self._attribute_to_ref(node)
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _extract_source_ref(
        self,
        node: ast.AST | None,
        *,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
    ) -> tuple[str | None, str, str, bool]:
        if node is None:
            return None, "direct", "", False
        if isinstance(node, ast.Attribute):
            resolved = self._resolve_model_attribute(node, model_scope=model_scope)
            if resolved:
                return resolved
            scoped_ref = self._resolve_scoped_attribute(node, scope_vars=scope_vars)
            return scoped_ref or self._attribute_to_ref(node), "nested", "", bool(scoped_ref)
        if isinstance(node, ast.Name):
            resolved = scope_vars.get(node.id)
            return resolved or node.id, ("nested" if resolved and "." in resolved else "direct"), "", bool(resolved)
        if isinstance(node, ast.Subscript):
            subscript_ref = self._subscript_to_ref(node, scope_vars=scope_vars, model_scope=model_scope)
            if subscript_ref:
                return subscript_ref, ("nested" if "." in subscript_ref else "direct"), "", False
        if isinstance(node, ast.Call):
            return self._extract_call_source_ref(node, scope_vars=scope_vars, model_scope=model_scope)
        if isinstance(node, ast.ListComp):
            return self._extract_list_comp_ref(node, scope_vars=scope_vars, model_scope=model_scope)
        if isinstance(node, ast.IfExp):
            left = self._extract_source_ref(node.body, scope_vars=scope_vars, model_scope=model_scope)
            right = self._extract_source_ref(node.orelse, scope_vars=scope_vars, model_scope=model_scope)
            chosen = left if left[0] else right
            return chosen[0], chosen[1], "conditional", chosen[3]
        return None, "direct", "", False

    def _extract_call_source_ref(
        self,
        node: ast.Call,
        *,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
    ) -> tuple[str | None, str, str, bool]:
        func_name = self._call_name(node.func)
        orm_ref = self._extract_orm_call_ref(node, scope_vars=scope_vars, model_scope=model_scope)
        if orm_ref[0]:
            return orm_ref
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "get" and node.args:
                source_ref, assignment_kind, _, intermediate_hit = self._extract_source_ref(
                    node.func.value,
                    scope_vars=scope_vars,
                    model_scope=model_scope,
                )
                key_name = self._literal_key(node.args[0])
                if source_ref and key_name:
                    return f"{source_ref}.{key_name}", "nested", "", intermediate_hit
        if isinstance(node.func, ast.Name) and node.args:
            inner_ref, assignment_kind, _, intermediate_hit = self._extract_source_ref(
                node.args[0],
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if inner_ref and func_name in self._WRAPPER_FUNCS:
                return inner_ref, assignment_kind, func_name.lower(), intermediate_hit
            if inner_ref and func_name in self._DATACLASS_FUNCS:
                return inner_ref, "bean_copy", "asdict", intermediate_hit
            if inner_ref and func_name.lower() in {"select", "selectinload"}:
                return inner_ref, "orm_statement", func_name.lower(), intermediate_hit
        if isinstance(node.func, ast.Attribute):
            owner_ref, assignment_kind, _, intermediate_hit = self._extract_source_ref(
                node.func.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if owner_ref and func_name in {"format", "isoformat", "lower", "upper", "strip"}:
                return owner_ref, assignment_kind, func_name.lower(), intermediate_hit
            if owner_ref and func_name in self._MODEL_DUMP_ATTRS:
                return owner_ref, "bean_copy", func_name.lower(), intermediate_hit
            if owner_ref:
                return f"{owner_ref}.{node.func.attr}", "nested", "", intermediate_hit
        for keyword in node.keywords or []:
            if not keyword.arg:
                continue
            source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                keyword.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if source_ref:
                return source_ref, assignment_kind, transform_hint or func_name.lower(), intermediate_hit
        if node.args:
            source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                node.args[0],
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            return source_ref, assignment_kind, transform_hint, intermediate_hit
        return None, "direct", "", False

    def _extract_orm_call_ref(
        self,
        node: ast.Call,
        *,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
    ) -> tuple[str | None, str, str, bool]:
        if not isinstance(node.func, ast.Attribute):
            return None, "direct", "", False

        attr_name = str(node.func.attr or "").lower()
        if attr_name == "execute" and node.args:
            stmt_ref, _, _, intermediate_hit = self._extract_source_ref(
                node.args[0],
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if stmt_ref:
                return stmt_ref, "orm_result", "execute", intermediate_hit
        if attr_name in self._ORM_MAPPING_ATTRS:
            owner_ref, _, _, intermediate_hit = self._extract_source_ref(
                node.func.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if owner_ref:
                return owner_ref, "orm_result", f"sqlalchemy_{attr_name}", intermediate_hit
        if attr_name in self._ORM_SCALAR_ATTRS:
            owner_ref, _, _, intermediate_hit = self._extract_source_ref(
                node.func.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if owner_ref:
                return owner_ref, "orm_result", f"sqlalchemy_{attr_name}", intermediate_hit
        if attr_name in self._ORM_RESULT_ATTRS:
            source_ref, transform_hint = self._extract_orm_result_owner(
                node.func.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
                terminal_attr=attr_name,
            )
            if source_ref:
                return source_ref, "orm_result", transform_hint, "." in source_ref
        return None, "direct", "", False

    def _extract_orm_result_owner(
        self,
        node: ast.AST,
        *,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        terminal_attr: str,
    ) -> tuple[str | None, str]:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner_attr = str(node.func.attr or "").lower()
            if owner_attr == "query" and node.args:
                entity_name = self._entity_name(node.args[0])
                if entity_name:
                    return entity_name, f"query_{terminal_attr}"
            if owner_attr in self._ORM_MAPPING_ATTRS | self._ORM_SCALAR_ATTRS:
                owner_ref, _, _, _ = self._extract_source_ref(
                    node.func.value,
                    scope_vars=scope_vars,
                    model_scope=model_scope,
                )
                if owner_ref:
                    return owner_ref, f"sqlalchemy_{owner_attr}_{terminal_attr}"
            if owner_attr == "execute" and node.args:
                stmt_ref, _, _, _ = self._extract_source_ref(
                    node.args[0],
                    scope_vars=scope_vars,
                    model_scope=model_scope,
                )
                if stmt_ref:
                    return stmt_ref, f"execute_{terminal_attr}"
            owner_ref, _, _, _ = self._extract_source_ref(
                node,
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if owner_ref:
                return owner_ref, f"call_{terminal_attr}"
        owner_ref, _, _, _ = self._extract_source_ref(
            node,
            scope_vars=scope_vars,
            model_scope=model_scope,
        )
        if owner_ref:
            return owner_ref, terminal_attr
        return None, ""

    def _extract_list_comp_ref(
        self,
        node: ast.ListComp,
        *,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
    ) -> tuple[str | None, str, str, bool]:
        if not node.generators:
            return None, "direct", "", False
        generator = node.generators[0]
        iterable_ref, _, _, iterable_hit = self._extract_source_ref(
            generator.iter,
            scope_vars=scope_vars,
            model_scope=model_scope,
        )
        if not iterable_ref:
            return None, "direct", "", False
        local_scope = dict(scope_vars)
        if isinstance(generator.target, ast.Name):
            local_scope[generator.target.id] = iterable_ref
        element_ref, _, _, element_hit = self._extract_source_ref(
            node.elt,
            scope_vars=local_scope,
            model_scope=model_scope,
        )
        return element_ref or iterable_ref, "collection_map", "list_comp", iterable_hit or element_hit

    def _extract_dict_assignment_edges(
        self,
        *,
        target_ref: str,
        value: ast.Dict,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
    ) -> List[Dict[str, object]]:
        edges: List[Dict[str, object]] = []
        for key_node, value_node in zip(value.keys, value.values):
            key_name = self._literal_key(key_node)
            if not key_name:
                continue
            source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                value_node,
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if not source_ref:
                continue
            edges.append(
                self._build_edge(
                    target_ref=f"{target_ref}.{key_name}",
                    source_ref=source_ref,
                    default_api_prefix=default_api_prefix,
                    assignment_kind=assignment_kind,
                    transform_hint=transform_hint or "dict_literal",
                    intermediate_variable_hit=intermediate_hit,
                )
            )
        return edges

    def _extract_dict_update_edges(
        self,
        *,
        call: ast.Call,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
    ) -> List[Dict[str, object]]:
        if not isinstance(call.func, ast.Attribute):
            return []
        if call.func.attr != "update":
            return []
        target_ref = self._extract_target_ref(call.func.value)
        if not target_ref or not call.args:
            return []
        first_arg = call.args[0]
        if not isinstance(first_arg, ast.Dict):
            return []
        return self._extract_dict_assignment_edges(
            target_ref=target_ref,
            value=first_arg,
            scope_vars=scope_vars,
            model_scope=model_scope,
            default_api_prefix=default_api_prefix,
        )

    def _extract_return_edges(
        self,
        *,
        node: ast.Return,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
        method_return_target: str | None = None,
    ) -> List[Dict[str, object]]:
        if method_return_target:
            source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                node.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if source_ref:
                return [
                    self._build_edge(
                        target_ref=method_return_target,
                        source_ref=source_ref,
                        default_api_prefix=default_api_prefix,
                        assignment_kind=assignment_kind,
                        transform_hint=transform_hint or "serializer_method",
                        intermediate_variable_hit=intermediate_hit,
                    )
                ]
        if isinstance(node.value, ast.Name):
            model_edges = self._emit_model_scope_edges(
                target_name=node.value.id,
                model_scope=model_scope,
                default_api_prefix=default_api_prefix,
            )
            if model_edges:
                return model_edges
        if isinstance(node.value, ast.Dict):
            return self._extract_dict_assignment_edges(
                target_ref="body",
                value=node.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
                default_api_prefix="",
            )
        if isinstance(node.value, ast.Call):
            model_edges = self._extract_return_model_call_edges(
                call=node.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
                default_api_prefix=default_api_prefix,
            )
            if model_edges:
                return model_edges
            edges: List[Dict[str, object]] = []
            for keyword in node.value.keywords or []:
                if not keyword.arg:
                    continue
                source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                    keyword.value,
                    scope_vars=scope_vars,
                    model_scope=model_scope,
                )
                if not source_ref:
                    continue
                edges.append(
                    self._build_edge(
                        target_ref=keyword.arg,
                        source_ref=source_ref,
                        default_api_prefix=default_api_prefix,
                        assignment_kind=assignment_kind,
                        transform_hint=transform_hint or self._call_name(node.value.func).lower(),
                        intermediate_variable_hit=intermediate_hit,
                    )
                )
            return edges
        return []

    def _extract_serializer_field_edges(
        self,
        *,
        node: ast.Assign,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
    ) -> List[Dict[str, object]]:
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            return []
        if not isinstance(node.value, ast.Call):
            return []
        source_keyword = None
        for keyword in node.value.keywords or []:
            if keyword.arg == "source":
                source_keyword = keyword
                break
        if source_keyword is None:
            return []
        source_name = self._literal_key(source_keyword.value)
        if not source_name:
            return []
        del scope_vars, model_scope
        source_ref = source_name
        assignment_kind = "nested" if "." in source_ref else "direct"
        transform_hint = ""
        intermediate_hit = False
        return [
            self._build_edge(
                target_ref=node.targets[0].id,
                source_ref=source_ref,
                default_api_prefix=default_api_prefix,
                assignment_kind=assignment_kind if assignment_kind != "direct" else ("nested" if "." in source_ref else "direct"),
                transform_hint=transform_hint or "serializer_source",
                intermediate_variable_hit=intermediate_hit,
            )
        ]

    def _extract_model_field_map(
        self,
        node: ast.AST | None,
        *,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
    ) -> Dict[str, Dict[str, object]] | None:
        if not isinstance(node, ast.Call):
            return None
        call_name = self._call_name(node.func).lower()
        if node.keywords:
            mapping: Dict[str, Dict[str, object]] = {}
            for keyword in node.keywords:
                if not keyword.arg:
                    continue
                source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                    keyword.value,
                    scope_vars=scope_vars,
                    model_scope=model_scope,
                )
                if not source_ref:
                    continue
                mapping[keyword.arg] = {
                    "source_ref": source_ref,
                    "assignment_kind": assignment_kind,
                    "transform_hint": transform_hint or call_name,
                    "intermediate_variable_hit": intermediate_hit,
                }
            return mapping or None
        if isinstance(node.func, ast.Attribute) and node.func.attr in self._MODEL_FACTORY_ATTRS and node.args:
            source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                node.args[0],
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if source_ref:
                return {
                    "*": {
                        "source_ref": source_ref,
                        "assignment_kind": "bean_copy",
                        "transform_hint": transform_hint or node.func.attr.lower(),
                        "intermediate_variable_hit": intermediate_hit,
                    }
                }
        if isinstance(node.func, ast.Attribute) and node.func.attr in self._MODEL_DUMP_ATTRS:
            source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                node.func.value,
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if source_ref:
                return {
                    "*": {
                        "source_ref": source_ref,
                        "assignment_kind": "bean_copy",
                        "transform_hint": transform_hint or node.func.attr.lower(),
                        "intermediate_variable_hit": intermediate_hit,
                    }
                }
        if isinstance(node.func, ast.Name) and node.func.id in self._DATACLASS_FUNCS and node.args:
            source_ref, assignment_kind, transform_hint, intermediate_hit = self._extract_source_ref(
                node.args[0],
                scope_vars=scope_vars,
                model_scope=model_scope,
            )
            if source_ref:
                return {
                    "*": {
                        "source_ref": source_ref,
                        "assignment_kind": "bean_copy",
                        "transform_hint": transform_hint or node.func.id.lower(),
                        "intermediate_variable_hit": intermediate_hit,
                    }
                }
        return None

    def _emit_model_scope_edges(
        self,
        *,
        target_name: str,
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
    ) -> List[Dict[str, object]]:
        mapping = model_scope.get(target_name)
        if not mapping:
            return []
        edges: List[Dict[str, object]] = []
        if "*" in mapping:
            wildcard = mapping["*"]
            source_ref = str(wildcard.get("source_ref") or "")
            if source_ref:
                edges.append(
                    self._build_wildcard_edge(
                        source_ref=source_ref,
                        transform_hint=str(wildcard.get("transform_hint") or ""),
                        intermediate_variable_hit=bool(wildcard.get("intermediate_variable_hit")),
                    )
                )
            return edges
        for target_field, meta in mapping.items():
            source_ref = str(meta.get("source_ref") or "")
            if not source_ref:
                continue
            edges.append(
                self._build_edge(
                    target_ref=target_field,
                    source_ref=source_ref,
                    default_api_prefix=default_api_prefix,
                    assignment_kind=str(meta.get("assignment_kind") or "direct"),
                    transform_hint=str(meta.get("transform_hint") or ""),
                    intermediate_variable_hit=bool(meta.get("intermediate_variable_hit")),
                )
            )
        return edges

    def _extract_return_model_call_edges(
        self,
        *,
        call: ast.Call,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
        default_api_prefix: str,
    ) -> List[Dict[str, object]]:
        model_mapping = self._extract_model_field_map(call, scope_vars=scope_vars, model_scope=model_scope)
        if not model_mapping:
            return []
        temp_scope = {"__return__": model_mapping}
        return self._emit_model_scope_edges(
            target_name="__return__",
            model_scope=temp_scope,
            default_api_prefix=default_api_prefix,
        )

    def _resolve_model_attribute(
        self,
        node: ast.Attribute,
        *,
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
    ) -> tuple[str | None, str, str, bool] | None:
        if not isinstance(node.value, ast.Name):
            return None
        mapping = model_scope.get(node.value.id)
        if not mapping:
            return None
        meta = mapping.get(node.attr)
        if not meta:
            return None
        return (
            str(meta.get("source_ref") or ""),
            str(meta.get("assignment_kind") or "direct"),
            str(meta.get("transform_hint") or ""),
            bool(meta.get("intermediate_variable_hit")),
        )

    def _resolve_scoped_attribute(
        self,
        node: ast.Attribute,
        *,
        scope_vars: Dict[str, str],
    ) -> str | None:
        parts: List[str] = []
        current: ast.AST | None = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return None
        root_ref = scope_vars.get(current.id)
        if not root_ref:
            return None
        parts.append(root_ref)
        return ".".join(reversed(parts))

    def _attribute_to_ref(self, node: ast.Attribute) -> str | None:
        parts: List[str] = []
        current: ast.AST | None = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        if not parts:
            return None
        return ".".join(reversed(parts))

    def _build_edge(
        self,
        *,
        target_ref: str,
        source_ref: str,
        default_api_prefix: str,
        assignment_kind: str = "direct",
        transform_hint: str = "",
        intermediate_variable_hit: bool = False,
    ) -> Dict[str, object]:
        target_leaf = target_ref.split(".")[-1]
        source_leaf = source_ref.split(".")[-1]
        final_path = f"{default_api_prefix}.{target_leaf}" if default_api_prefix else target_ref
        return {
            "api_field_path": final_path,
            "target_field": target_leaf,
            "target_object": target_ref.rsplit(".", 1)[0] if "." in target_ref else "",
            "target_chain": target_ref,
            "source_field": source_leaf,
            "source_object": source_ref.rsplit(".", 1)[0] if "." in source_ref else "",
            "source_chain": source_ref,
            "db_table": None,
            "db_column": source_leaf,
            "chain_depth": max(source_ref.count(".") + 1, 1),
            "assignment_kind": assignment_kind if assignment_kind else ("nested" if "." in source_ref else "direct"),
            "transform_hint": transform_hint,
            "intermediate_variable_hit": intermediate_variable_hit,
            "evidence_type": "code_assignment_ast",
            "confidence": 0.92,
            "payload": {"analyzer": "python_ast", "transform_hint": transform_hint},
        }

    def _dedupe(self, edges: List[Dict[str, object]]) -> List[Dict[str, object]]:
        seen = set()
        items: List[Dict[str, object]] = []
        for edge in edges:
            key = (
                edge.get("api_field_path"),
                edge.get("target_chain"),
                edge.get("source_chain"),
                edge.get("assignment_kind"),
                edge.get("evidence_type"),
            )
            if key in seen:
                continue
            seen.add(key)
            items.append(edge)
        return items

    def _camel_to_snake(self, value: str) -> str:
        if not value:
            return ""
        if value.lower() == value:
            return value.lstrip("_")
        result: List[str] = []
        for index, char in enumerate(value):
            if char.isupper() and index > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result).lstrip("_")

    def _literal_key(self, node: ast.AST | None) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return str(node.value)
        return None

    def _entity_name(self, node: ast.AST | None) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return self._attribute_to_ref(node)
        return None

    def _serializer_method_target(self, function_name: str) -> str | None:
        if function_name.startswith("get_") and len(function_name) > 4:
            return function_name[4:]
        return None

    def _subscript_to_ref(
        self,
        node: ast.Subscript,
        *,
        scope_vars: Dict[str, str],
        model_scope: Dict[str, Dict[str, Dict[str, object]]],
    ) -> str | None:
        base_ref, _, _, _ = self._extract_source_ref(node.value, scope_vars=scope_vars, model_scope=model_scope)
        key_name = self._literal_key(node.slice) if not isinstance(node.slice, ast.Index) else self._literal_key(node.slice.value)
        if base_ref and key_name:
            return f"{base_ref}.{key_name}"
        return None

    def _call_name(self, func: ast.AST) -> str:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return ""

    def _build_wildcard_edge(
        self,
        *,
        source_ref: str,
        transform_hint: str,
        intermediate_variable_hit: bool,
    ) -> Dict[str, object]:
        source_leaf = source_ref.split(".")[-1]
        return {
            "api_field_path": "*",
            "target_field": "*",
            "target_object": "",
            "target_chain": "*",
            "source_field": "*",
            "source_object": source_ref.rsplit(".", 1)[0] if "." in source_ref else source_ref,
            "source_chain": source_ref,
            "db_table": None,
            "db_column": source_leaf,
            "chain_depth": max(source_ref.count(".") + 1, 1),
            "assignment_kind": "bean_copy",
            "transform_hint": transform_hint,
            "intermediate_variable_hit": intermediate_variable_hit,
            "evidence_type": "code_assignment_ast",
            "confidence": 0.9,
            "payload": {"analyzer": "python_ast", "transform_hint": transform_hint, "copy_mode": "same_name_field_copy"},
        }


class JavaAstCodeAnalyzer:
    """Use javalang AST when available for Java assignment extraction."""

    def __init__(
        self,
        adapter: BaseJavaAdapter | None = None,
        registry: JavaAdapterRegistry | None = None,
        preferred_adapter_name: str | None = None,
    ) -> None:
        self.registry = registry or JavaAdapterRegistry(
            adapters=[adapter or JavalangJavaAdapter()],
            preferred_adapter_name=preferred_adapter_name or settings.DATA_IMPACT_JAVA_ADAPTER,
        )

    def supports(self, *, file_path: Optional[str]) -> bool:
        return str(file_path or "").lower().endswith(".java")

    def analyze(
        self,
        *,
        source_text: str,
        file_path: Optional[str],
        default_api_prefix: str = "body",
    ) -> List[Dict[str, object]]:
        del file_path
        adapter = self.registry.resolve()
        facts = adapter.parse_facts(source_text=source_text)
        return adapter.to_lineage_edges(facts=facts, default_api_prefix=default_api_prefix)


class TextPatternCodeAnalyzer:
    """Fallback analyzer backed by the legacy pattern parser."""

    def __init__(self) -> None:
        self.parser = CodeLineageParser()

    def supports(self, *, file_path: Optional[str]) -> bool:
        suffix = Path(str(file_path or "")).suffix.lower()
        return suffix in {".java", ".kt", ".py", ".txt", ""}

    def analyze(
        self,
        *,
        source_text: str,
        file_path: Optional[str],
        default_api_prefix: str = "body",
    ) -> List[Dict[str, object]]:
        return self.parser.parse_source_text(
            source_text=self._normalize_source_text(source_text),
            default_api_prefix=default_api_prefix,
        )

    def _normalize_source_text(self, source_text: str) -> str:
        statements: List[str] = []
        buffer: List[str] = []
        for raw_line in source_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue
            buffer.append(line)
            if line.endswith(";"):
                statements.append(" ".join(buffer))
                buffer = []
        if buffer:
            statements.append(" ".join(buffer))
        return "\n".join(statements)


class _NormalizedPatternAnalyzer:
    """Base helper for pattern analyzers that need statement normalization."""

    def __init__(self) -> None:
        self.parser = CodeLineageParser()

    def supports(self, *, file_path: Optional[str]) -> bool:
        suffix = Path(str(file_path or "")).suffix.lower()
        return suffix in {".java", ".kt", ".py", ".txt", ""}

    def analyze(
        self,
        *,
        source_text: str,
        file_path: Optional[str],
        default_api_prefix: str = "body",
    ) -> List[Dict[str, object]]:
        raw_edges = self.parser.parse_source_text(
            source_text=self._normalize_source_text(source_text),
            default_api_prefix=default_api_prefix,
        )
        return self._filter_edges(raw_edges, file_path=file_path)

    def _filter_edges(
        self,
        edges: List[Dict[str, object]],
        *,
        file_path: Optional[str],
    ) -> List[Dict[str, object]]:
        del file_path
        return edges

    def _normalize_source_text(self, source_text: str) -> str:
        statements: List[str] = []
        buffer: List[str] = []
        for raw_line in source_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue
            buffer.append(line)
            if line.endswith(";"):
                statements.append(" ".join(buffer))
                buffer = []
        if buffer:
            statements.append(" ".join(buffer))
        return "\n".join(statements)


class BeanCopyEnricher(_NormalizedPatternAnalyzer):
    """Supplement AST results with BeanUtils-style wildcard copy evidence."""

    def _filter_edges(
        self,
        edges: List[Dict[str, object]],
        *,
        file_path: Optional[str],
    ) -> List[Dict[str, object]]:
        del file_path
        return [edge for edge in edges if str(edge.get("evidence_type") or "") == "bean_copy"]


class BuilderPatternEnricher(_NormalizedPatternAnalyzer):
    """Supplement AST results with multi-step builder chains."""

    def _filter_edges(
        self,
        edges: List[Dict[str, object]],
        *,
        file_path: Optional[str],
    ) -> List[Dict[str, object]]:
        del file_path
        return [edge for edge in edges if str(edge.get("assignment_kind") or "") == "builder"]


class StreamPatternEnricher(_NormalizedPatternAnalyzer):
    """Supplement AST results with stream and foreach collection transforms."""

    _KINDS = {"stream_map", "foreach_add", "collection_copy"}

    def _filter_edges(
        self,
        edges: List[Dict[str, object]],
        *,
        file_path: Optional[str],
    ) -> List[Dict[str, object]]:
        del file_path
        return [edge for edge in edges if str(edge.get("assignment_kind") or "") in self._KINDS]


class MapperAnnotationEnricher(_NormalizedPatternAnalyzer):
    """Supplement AST results with annotation-based mapper hints."""

    def _filter_edges(
        self,
        edges: List[Dict[str, object]],
        *,
        file_path: Optional[str],
    ) -> List[Dict[str, object]]:
        del file_path
        return [edge for edge in edges if str(edge.get("evidence_type") or "") == "mapper_annotation"]


class ConverterPatternEnricher(_NormalizedPatternAnalyzer):
    """Supplement AST results with converter-style wrapper transforms."""

    def _filter_edges(
        self,
        edges: List[Dict[str, object]],
        *,
        file_path: Optional[str],
    ) -> List[Dict[str, object]]:
        del file_path
        return [edge for edge in edges if str(edge.get("assignment_kind") or "") == "converter"]


class CodeAnalysisPipeline:
    """Route source files through AST analyzers first, then enrich or fallback."""

    def __init__(self, analyzers: Optional[List[SourceAnalyzer]] = None) -> None:
        if analyzers is not None:
            self.primary_analyzers = analyzers
            self.enrich_analyzers: List[SourceAnalyzer] = []
            self.fallback_analyzer = TextPatternCodeAnalyzer()
            return
        self.primary_analyzers = [PythonAstCodeAnalyzer(), JavaAstCodeAnalyzer()]
        self.enrich_analyzers = [
            BeanCopyEnricher(),
            BuilderPatternEnricher(),
            StreamPatternEnricher(),
            MapperAnnotationEnricher(),
            ConverterPatternEnricher(),
        ]
        self.fallback_analyzer = TextPatternCodeAnalyzer()

    def analyze(
        self,
        *,
        source_text: str,
        file_path: Optional[str],
        default_api_prefix: str = "body",
    ) -> List[Dict[str, object]]:
        return self.analyze_with_stats(
            source_text=source_text,
            file_path=file_path,
            default_api_prefix=default_api_prefix,
        )["edges"]

    def analyze_with_stats(
        self,
        *,
        source_text: str,
        file_path: Optional[str],
        default_api_prefix: str = "body",
    ) -> Dict[str, Any]:
        merged: List[Dict[str, object]] = []
        seen = set()
        primary_hit = False

        for analyzer in self.primary_analyzers:
            if not analyzer.supports(file_path=file_path):
                continue
            self._merge_edges(
                merged=merged,
                seen=seen,
                edges=analyzer.analyze(
                    source_text=source_text,
                    file_path=file_path,
                    default_api_prefix=default_api_prefix,
                ),
            )
            if merged:
                primary_hit = True
                break

        if not merged and self.fallback_analyzer.supports(file_path=file_path):
            self._merge_edges(
                merged=merged,
                seen=seen,
                edges=self.fallback_analyzer.analyze(
                    source_text=source_text,
                    file_path=file_path,
                    default_api_prefix=default_api_prefix,
                ),
            )
            return {
                "edges": merged,
                "stats": self._build_stats(
                    file_path=file_path,
                    edges=merged,
                    used_fallback=True,
                    primary_hit=False,
                ),
            }

        for analyzer in self.enrich_analyzers:
            if not analyzer.supports(file_path=file_path):
                continue
            self._merge_edges(
                merged=merged,
                seen=seen,
                edges=analyzer.analyze(
                    source_text=source_text,
                    file_path=file_path,
                    default_api_prefix=default_api_prefix,
                ),
            )
        return {
            "edges": merged,
            "stats": self._build_stats(
                file_path=file_path,
                edges=merged,
                used_fallback=False,
                primary_hit=primary_hit,
            ),
        }

    def _merge_edges(
        self,
        *,
        merged: List[Dict[str, object]],
        seen: set,
        edges: List[Dict[str, object]],
    ) -> None:
        for edge in edges:
            key = (
                edge.get("api_field_path"),
                edge.get("target_chain"),
                edge.get("source_chain"),
                edge.get("assignment_kind"),
                edge.get("evidence_type"),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(edge)

    def _build_stats(
        self,
        *,
        file_path: Optional[str],
        edges: List[Dict[str, object]],
        used_fallback: bool,
        primary_hit: bool,
    ) -> Dict[str, object]:
        assignment_kinds = Counter(str(edge.get("assignment_kind") or "") for edge in edges if edge.get("assignment_kind"))
        evidence_types = Counter(str(edge.get("evidence_type") or "") for edge in edges if edge.get("evidence_type"))
        pipeline_sources = Counter(self._edge_source_label(edge) for edge in edges)
        return {
            "file_path": str(file_path or ""),
            "edge_count": len(edges),
            "used_fallback": used_fallback,
            "primary_hit": primary_hit,
            "pipeline_sources": dict(sorted(pipeline_sources.items())),
            "assignment_kinds": dict(sorted(assignment_kinds.items())),
            "evidence_types": dict(sorted(evidence_types.items())),
        }

    def _edge_source_label(self, edge: Dict[str, object]) -> str:
        payload = edge.get("payload")
        if isinstance(payload, dict):
            analyzer = str(payload.get("analyzer") or "").strip()
            if analyzer:
                return analyzer
        evidence_type = str(edge.get("evidence_type") or "").strip()
        assignment_kind = str(edge.get("assignment_kind") or "").strip()
        if evidence_type == "bean_copy":
            return "bean_copy_enricher"
        if evidence_type == "mapper_annotation":
            return "mapper_annotation_enricher"
        if assignment_kind == "builder":
            return "builder_enricher"
        if assignment_kind in {"stream_map", "foreach_add", "collection_copy"}:
            return "stream_enricher"
        if assignment_kind == "converter":
            return "converter_enricher"
        return "legacy_pattern_fallback"
