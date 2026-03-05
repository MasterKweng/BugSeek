"""Domain inference for field mapping."""
from typing import Dict, List, Set

from app.utils.name_normalizer import normalize_name


class DomainInferer:
    """Infer allowed tables for an API by weighted path/field signals."""

    COMMON_PREFIXES: Set[str] = {
        "id", "name", "code", "status", "type", "time", "date", "create",
        "update", "deleted", "is", "flag", "desc", "remark", "value",
        "list", "item", "data", "info", "result", "content"
    }
    PATH_STOP_WORDS: Set[str] = {
        "api", "v1", "v2", "v3", "create", "update", "delete", "get", "list",
        "batch", "export", "import", "query", "detail", "search"
    }

    def __init__(self, db_schema: Dict):
        self.db_schema = db_schema or {}
        self.tables = list((self.db_schema.get("tables") or {}).keys())
        self.normalized_tables = {table: normalize_name(table) for table in self.tables}

    def infer(self, api_path: str, fields: List[str]) -> List[str]:
        path_domain = self.extract_from_path(api_path)
        field_prefixes = self.count_field_prefixes(fields)
        return self.weighted_merge(path_domain, field_prefixes)

    def extract_from_path(self, api_path: str) -> str:
        if not api_path:
            return ""
        segments = [seg.strip().lower() for seg in api_path.strip("/").split("/") if seg.strip()]
        candidates = [
            seg for seg in segments
            if not seg.startswith("{") and seg not in self.PATH_STOP_WORDS and len(seg) > 1
        ]
        if not candidates:
            return ""
        return normalize_name(candidates[-1])

    def count_field_prefixes(self, fields: List[str]) -> Dict[str, float]:
        prefix_count: Dict[str, int] = {}
        for field in fields or []:
            normalized = normalize_name(field)
            if not normalized:
                continue
            parts = [p for p in normalized.split("_") if p]
            if not parts:
                continue
            prefix = parts[0]
            if prefix in self.COMMON_PREFIXES or len(prefix) <= 1:
                continue
            prefix_count[prefix] = prefix_count.get(prefix, 0) + 1

        total = sum(prefix_count.values()) or 1
        return {k: v / total for k, v in prefix_count.items()}

    def weighted_merge(self, path_domain: str, field_prefixes: Dict[str, float]) -> List[str]:
        if not self.tables:
            return []

        scored = []
        for table in self.tables:
            norm_table = self.normalized_tables.get(table, "")
            score = 0.0

            if path_domain and norm_table:
                if norm_table == path_domain:
                    score += 0.7
                elif path_domain in norm_table or norm_table in path_domain:
                    score += 0.35

            field_score = 0.0
            if field_prefixes and norm_table:
                table_tokens = set(t for t in norm_table.split("_") if t)
                for prefix, ratio in field_prefixes.items():
                    if prefix in table_tokens:
                        field_score = max(field_score, ratio)
                score += field_score * 0.3

            if score > 0:
                scored.append((table, score))

        if not scored:
            return []

        scored.sort(key=lambda x: x[1], reverse=True)
        top_score = scored[0][1]
        threshold = max(0.1, top_score * 0.35)
        return [table for table, score in scored if score >= threshold]
