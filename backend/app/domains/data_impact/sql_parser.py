"""Lightweight SQL parser helpers backed by sqlglot."""

from __future__ import annotations

from typing import Optional, Tuple

import sqlglot
from sqlglot import exp


def parse_sql_operation(sql_text: str) -> Optional[str]:
    try:
        parsed = sqlglot.parse_one(sql_text or "")
    except Exception:
        return None
    if parsed is None:
        return None
    if isinstance(parsed, exp.Select):
        return "SELECT"
    if isinstance(parsed, exp.Insert):
        return "INSERT"
    if isinstance(parsed, exp.Update):
        return "UPDATE"
    if isinstance(parsed, exp.Delete):
        return "DELETE"
    return None


def parse_sql_table(sql_text: str) -> Optional[str]:
    try:
        parsed = sqlglot.parse_one(sql_text or "")
    except Exception:
        return None
    if parsed is None:
        return None

    if isinstance(parsed, exp.Select):
        from_expr = parsed.args.get("from_")
        table_expr = from_expr.this if from_expr is not None else None
        if isinstance(table_expr, exp.Table):
            return _normalize_identifier(table_expr.name)
        return None

    if isinstance(parsed, (exp.Insert, exp.Update, exp.Delete)):
        table_expr = parsed.this
        if isinstance(table_expr, exp.Table):
            return _normalize_identifier(table_expr.name)
    return None


def parse_sql(sql_text: str) -> Tuple[Optional[str], Optional[str]]:
    operation = parse_sql_operation(sql_text)
    table_name = parse_sql_table(sql_text)
    return operation, table_name


def _normalize_identifier(value: str) -> str:
    cleaned = str(value or "").strip().strip("`\"")
    if "." in cleaned:
        cleaned = cleaned.split(".")[-1]
    return cleaned or None
