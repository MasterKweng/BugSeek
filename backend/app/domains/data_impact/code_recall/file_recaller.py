from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set

from app.utils.field_mapping_utils import normalize_field_name, tokenize_field

from .recall_models import FileRecallCandidate, FileRecallResult


class RuleBasedFileRecaller:
    """Recall likely relevant source files before deeper lineage parsing."""

    _SUPPORTED_SUFFIXES = {".xml", ".java", ".kt", ".py"}
    _CONTENT_READ_LIMIT = 8192
    _ROLE_WEIGHTS = {
        "controller": 1.4,
        "service": 1.2,
        "serializer": 1.1,
        "mapper": 1.2,
        "dto": 1.0,
        "assembler": 1.2,
        "converter": 1.2,
        "schema": 0.8,
        "resource": 0.8,
    }

    def recall_files(
        self,
        *,
        workspace_root: str,
        definition: Any,
        response_field_paths: Sequence[str],
        max_candidates: int = 80,
    ) -> FileRecallResult:
        root = Path(workspace_root)
        if not root.exists():
            return FileRecallResult(candidates=[], used_fallback_scan=True)

        query_terms = self._collect_query_terms(definition=definition, response_field_paths=response_field_paths)
        if not query_terms["all_terms"]:
            return FileRecallResult(candidates=[], used_fallback_scan=True)

        candidates: List[FileRecallCandidate] = []
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self._SUPPORTED_SUFFIXES:
                continue
            score, reasons = self._score_file(file_path=file_path, root=root, query_terms=query_terms)
            if score <= 0:
                continue
            candidates.append(
                FileRecallCandidate(
                    path=str(file_path),
                    score=score,
                    reasons=reasons[:6],
                )
            )

        candidates.sort(key=lambda item: (-item.score, item.path))
        limited = candidates[:max_candidates]
        return FileRecallResult(
            candidates=limited,
            used_fallback_scan=not bool(limited),
        )

    def _collect_query_terms(
        self,
        *,
        definition: Any,
        response_field_paths: Sequence[str],
    ) -> Dict[str, Set[str]]:
        path_tokens = self._tokenize_text(self._first_attr(definition, "path", "api_path", "endpoint", "url_path"))
        method_tokens = self._tokenize_text(self._first_attr(definition, "method", "http_method", "request_method"))
        name_tokens = self._tokenize_text(
            self._first_attr(definition, "name", "operation_id", "summary", "title", "api_name", "handler_name")
        )
        field_tokens: Set[str] = set()
        for field_path in response_field_paths:
            field_tokens.update(self._tokenize_text(field_path))
            field_tokens.update(self._tokenize_text(field_path.split(".")[-1].replace("[]", "")))
        all_terms = {token for token in path_tokens | method_tokens | name_tokens | field_tokens if token}
        return {
            "path_tokens": path_tokens,
            "method_tokens": method_tokens,
            "name_tokens": name_tokens,
            "field_tokens": field_tokens,
            "all_terms": all_terms,
        }

    def _score_file(
        self,
        *,
        file_path: Path,
        root: Path,
        query_terms: Dict[str, Set[str]],
    ) -> tuple[float, List[str]]:
        rel_path = file_path.relative_to(root).as_posix().lower()
        path_tokens = self._path_tokens(file_path.relative_to(root))
        score = 0.0
        reasons: List[str] = []
        content_tokens = self._content_tokens(file_path)

        path_hits = sorted(query_terms["path_tokens"] & path_tokens)
        if path_hits:
            score += min(4.0, 1.2 + 0.6 * len(path_hits))
            reasons.append(f"path:{','.join(path_hits[:3])}")

        name_hits = sorted(query_terms["name_tokens"] & path_tokens)
        if name_hits:
            score += min(3.5, 1.0 + 0.5 * len(name_hits))
            reasons.append(f"name:{','.join(name_hits[:3])}")

        field_hits = sorted(query_terms["field_tokens"] & path_tokens)
        if field_hits:
            score += min(4.0, 0.8 + 0.35 * len(field_hits))
            reasons.append(f"field:{','.join(field_hits[:4])}")

        content_hits = sorted(query_terms["all_terms"] & content_tokens)
        if content_hits:
            score += min(3.5, 0.7 + 0.25 * len(content_hits))
            reasons.append(f"content:{','.join(content_hits[:4])}")

        role_bonus = self._infer_role_bonus(rel_path)
        if role_bonus > 0 and (path_hits or name_hits or field_hits or content_hits):
            score += role_bonus
            reasons.append(f"role:+{role_bonus:.1f}")

        if file_path.suffix.lower() == ".xml" and ("mapper" in rel_path or "mybatis" in rel_path):
            score += 1.0
            reasons.append("xml-mapper")

        # Keep obvious DTO/entity files from dominating unless there is other evidence.
        if not (path_hits or name_hits or field_hits) and any(token in rel_path for token in ("dto", "entity", "model")):
            score += 0.2

        return score, reasons

    def _infer_role_bonus(self, rel_path: str) -> float:
        for keyword, weight in self._ROLE_WEIGHTS.items():
            if keyword in rel_path:
                return weight
        return 0.0

    def _path_tokens(self, relative_path: Path) -> Set[str]:
        joined = relative_path.as_posix().replace("/", " ").replace("-", " ").replace("_", " ")
        return self._tokenize_text(joined)

    def _content_tokens(self, file_path: Path) -> Set[str]:
        try:
            source_text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return set()
        snippet = source_text[: self._CONTENT_READ_LIMIT]
        return self._tokenize_text(snippet)

    def _first_attr(self, obj: Any, *names: str) -> str:
        for name in names:
            value = getattr(obj, name, None)
            if value:
                return str(value)
        return ""

    def _tokenize_text(self, value: str) -> Set[str]:
        normalized = normalize_field_name(str(value or ""))
        tokens = set(tokenize_field(normalized))
        if normalized:
            tokens.update(part for part in normalized.replace("/", " ").replace(".", " ").split() if part)
        return {token for token in tokens if len(token) >= 2}
