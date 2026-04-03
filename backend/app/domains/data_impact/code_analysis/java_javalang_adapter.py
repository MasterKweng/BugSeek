from __future__ import annotations

import importlib
from typing import List

from .java_adapter_base import BaseJavaAdapter
from .java_ir import JavaAssignmentFact


class JavalangJavaAdapter(BaseJavaAdapter):
    """Java adapter backed by javalang."""

    adapter_name = "java_javalang"

    def is_available(self) -> bool:
        return self._load_javalang() is not None

    def parse_facts(self, *, source_text: str) -> List[JavaAssignmentFact]:
        if not source_text.strip():
            return []
        javalang = self._load_javalang()
        if javalang is None:
            return []
        try:
            tree = javalang.parse.parse(source_text)
        except Exception:
            return []

        statement_expression_cls = getattr(javalang.tree, "StatementExpression", None)
        assignment_cls = getattr(javalang.tree, "Assignment", None)
        method_invocation_cls = getattr(javalang.tree, "MethodInvocation", None)
        local_var_decl_cls = getattr(javalang.tree, "LocalVariableDeclaration", None)

        facts: List[JavaAssignmentFact] = []
        for _, node in tree:
            if statement_expression_cls is not None and isinstance(node, statement_expression_cls):
                expression = getattr(node, "expression", None)
                if assignment_cls is not None and isinstance(expression, assignment_cls):
                    fact = self._fact_from_assignment(expression=expression)
                    if fact:
                        facts.append(fact)
                elif method_invocation_cls is not None and isinstance(expression, method_invocation_cls):
                    fact = self._fact_from_method_invocation(expression=expression)
                    if fact:
                        facts.append(fact)
            elif local_var_decl_cls is not None and isinstance(node, local_var_decl_cls):
                for declarator in getattr(node, "declarators", []) or []:
                    initializer = getattr(declarator, "initializer", None)
                    target_name = getattr(declarator, "name", None)
                    source_ref = self._extract_source_ref(initializer)
                    if target_name and source_ref:
                        facts.append(
                            JavaAssignmentFact(
                                target_ref=str(target_name),
                                source_ref=source_ref,
                                fact_kind="local_var",
                                adapter_name=self.adapter_name,
                            )
                        )
        return facts

    def _load_javalang(self):
        try:
            return importlib.import_module("javalang")
        except Exception:
            return None

    def _fact_from_assignment(self, *, expression: object) -> JavaAssignmentFact | None:
        target_ref = self._extract_target_ref(getattr(expression, "expressionl", None))
        source_ref = self._extract_source_ref(getattr(expression, "value", None))
        if not target_ref or not source_ref:
            return None
        return JavaAssignmentFact(
            target_ref=target_ref,
            source_ref=source_ref,
            fact_kind="assignment",
            adapter_name=self.adapter_name,
        )

    def _fact_from_method_invocation(self, *, expression: object) -> JavaAssignmentFact | None:
        method_name = str(getattr(expression, "member", "") or "")
        arguments = list(getattr(expression, "arguments", []) or [])
        if not method_name.startswith("set") or len(arguments) != 1:
            return None
        source_ref = self._extract_source_ref(arguments[0])
        if not source_ref:
            return None
        target_ref = self._camel_to_snake(method_name[3:])
        if not target_ref:
            return None
        return JavaAssignmentFact(
            target_ref=target_ref,
            source_ref=source_ref,
            fact_kind="setter",
            adapter_name=self.adapter_name,
        )

    def _extract_target_ref(self, node: object | None) -> str | None:
        if node is None:
            return None
        return self._extract_source_ref(node)

    def _extract_source_ref(self, node: object | None) -> str | None:
        if node is None:
            return None
        class_name = node.__class__.__name__
        qualifier = getattr(node, "qualifier", None)
        member = getattr(node, "member", None)
        if class_name == "MemberReference":
            return ".".join(part for part in [qualifier, member] if part)
        if class_name == "MethodInvocation":
            owner = self._extract_source_ref(qualifier) if qualifier is not None and not isinstance(qualifier, str) else str(qualifier or "")
            if owner:
                return f"{owner}.{member}"
            return str(member or "")
        if class_name == "This":
            selectors = getattr(node, "selectors", []) or []
            if selectors:
                selector = selectors[0]
                return self._extract_source_ref(selector)
            return "this"
        if class_name == "Literal":
            return None
        if hasattr(node, "member") and member:
            owner = str(qualifier or "")
            return ".".join(part for part in [owner, str(member)] if part)
        if hasattr(node, "name"):
            return str(getattr(node, "name") or "")
        if class_name == "BinaryOperation":
            left = self._extract_source_ref(getattr(node, "operandl", None))
            right = self._extract_source_ref(getattr(node, "operandr", None))
            return left or right
        if class_name == "Cast":
            return self._extract_source_ref(getattr(node, "expression", None))
        return None

    def _camel_to_snake(self, value: str) -> str:
        if not value:
            return ""
        result: List[str] = []
        for index, char in enumerate(value):
            if char.isupper() and index > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result).lstrip("_")
