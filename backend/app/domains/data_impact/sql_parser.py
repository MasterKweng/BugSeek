"""Lightweight SQL parser helpers."""
from typing import Optional, Tuple
import re
import sqlparse
from sqlparse import tokens as T
from sqlparse.sql import Identifier, IdentifierList, Parenthesis, TokenList


_OPERATION_RE = re.compile(r"^(INSERT|UPDATE|DELETE|SELECT)\b", re.IGNORECASE)


def parse_sql_operation(sql_text: str) -> Optional[str]:
    match = _OPERATION_RE.search(sql_text.strip())
    if not match:
        return None
    return match.group(1).upper()


def _normalize_identifier(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1]
    if "." in value:
        value = value.split(".")[-1]
    return value.strip()


def _extract_identifier(token) -> Optional[str]:
    if isinstance(token, Identifier):
        name = token.get_real_name() or token.get_name() or token.value
        return _normalize_identifier(str(name))
    if isinstance(token, IdentifierList):
        for item in token.get_identifiers():
            return _extract_identifier(item)
    if token is None:
        return None
    value = getattr(token, "value", "")
    if value:
        return _normalize_identifier(str(value))
    return None


def _next_identifier(tokens, start_index: int) -> Optional[str]:
    for token in tokens[start_index + 1:]:
        if token.is_whitespace or token.ttype in T.Newline:
            continue
        if token.ttype in (T.Keyword, T.Keyword.DML) and token.value.upper() in ("ONLY",):
            continue
        if isinstance(token, TokenList) and token.is_group:
            if isinstance(token, Identifier) or isinstance(token, IdentifierList):
                return _extract_identifier(token)
            # Skip subqueries like FROM (SELECT ...)
            if isinstance(token, Parenthesis):
                continue
        if token.ttype in (T.Keyword, T.Keyword.DML):
            continue
        return _extract_identifier(token)
    return None


def parse_sql_table(sql_text: str) -> Optional[str]:
    parsed = sqlparse.parse(sql_text)
    if not parsed:
        return None
    statement = parsed[0]
    tokens = [token for token in statement.tokens if not token.is_whitespace]
    if not tokens:
        return None

    operation = parse_sql_operation(sql_text)
    upper_values = [token.value.upper() for token in tokens]

    def _find_keyword(keyword: str) -> Optional[int]:
        for idx, token in enumerate(tokens):
            if token.ttype in (T.Keyword, T.Keyword.DML) and token.value.upper() == keyword:
                return idx
        return None

    if operation == "UPDATE":
        idx = _find_keyword("UPDATE")
        return _next_identifier(tokens, idx) if idx is not None else None
    if operation == "INSERT":
        idx = _find_keyword("INTO")
        if idx is None and "INSERT" in upper_values:
            idx = upper_values.index("INSERT")
        return _next_identifier(tokens, idx) if idx is not None else None
    if operation == "DELETE":
        idx = _find_keyword("FROM")
        return _next_identifier(tokens, idx) if idx is not None else None
    if operation == "SELECT":
        idx = _find_keyword("FROM")
        return _next_identifier(tokens, idx) if idx is not None else None

    return None


def parse_sql(sql_text: str) -> Tuple[Optional[str], Optional[str]]:
    operation = parse_sql_operation(sql_text)
    table_name = parse_sql_table(sql_text)
    return operation, table_name
