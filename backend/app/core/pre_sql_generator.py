"""根据字段映射生成 pre_sql"""
from typing import Dict, Any, List, Optional, Tuple
import re
import logging
from sqlalchemy.orm import Session

from app.platform.db.base import ApiFieldMapping, DbSchemaVersion

logger = logging.getLogger(__name__)

IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _is_safe_identifier(value: str) -> bool:
    return bool(value and IDENTIFIER_PATTERN.match(value))


def _extract_required_vars(request_data: Any) -> List[str]:
    if not request_data:
        return []
    pattern = re.compile(r'\{\{\s*([a-zA-Z_]\w*)\s*(\([^{}]*\))?\s*\}\}')
    found: set = set()

    def walk(node: Any):
        if isinstance(node, str):
            for m in pattern.finditer(node):
                name = m.group(1)
                has_call = m.group(2) is not None
                if has_call:
                    continue
                found.add(name)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(request_data)
    return sorted(found)


def _get_latest_schema_snapshot(
    db: Session,
    project_id: int,
    version_id: int
) -> Optional[Dict[str, Any]]:
    schema = db.query(DbSchemaVersion).filter(
        DbSchemaVersion.project_id == project_id,
        DbSchemaVersion.version_id == version_id
    ).order_by(DbSchemaVersion.updated_at.desc()).first()
    if not schema:
        return None
    return schema.schema_snapshot


def _table_exists(schema_snapshot: Optional[Dict[str, Any]], table: str) -> bool:
    if not schema_snapshot or not table:
        return True
    tables = schema_snapshot.get("tables")
    if not isinstance(tables, list):
        return True
    return any(t.get("name") == table for t in tables if isinstance(t, dict))


def _column_exists(schema_snapshot: Optional[Dict[str, Any]], table: str, column: str) -> bool:
    if not schema_snapshot or not table or not column:
        return True
    tables = schema_snapshot.get("tables")
    if not isinstance(tables, list):
        return True
    for t in tables:
        if not isinstance(t, dict) or t.get("name") != table:
            continue
        cols = t.get("columns")
        if not isinstance(cols, list):
            return True
        return any(c.get("name") == column for c in cols if isinstance(c, dict))
    return True


def generate_pre_sql(
    db: Session,
    project_id: int,
    version_id: int,
    definition_id: int,
    request_data: Optional[Dict[str, Any]] = None,
    required_variables: Optional[List[str]] = None
) -> Tuple[Optional[str], List[Dict[str, Any]], List[str]]:
    """
    基于字段映射生成 pre_sql
    返回：pre_sql, data_prep, required_variables
    """
    if required_variables is None:
        required_variables = _extract_required_vars(request_data)

    if not required_variables:
        return None, [], []

    mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == project_id,
        ApiFieldMapping.version_id == version_id,
        ApiFieldMapping.definition_id == definition_id
    ).all()

    if not mappings:
        return None, [], required_variables

    schema_snapshot = _get_latest_schema_snapshot(db, project_id, version_id)

    var_to_mapping: Dict[str, ApiFieldMapping] = {}
    for m in mappings:
        if not m.api_field_path:
            continue
        var_name = m.api_field_path.split(".")[-1]
        if var_name in required_variables and var_name not in var_to_mapping:
            var_to_mapping[var_name] = m

    table_group: Dict[str, List[Tuple[str, str]]] = {}
    data_prep: List[Dict[str, Any]] = []

    for var_name in required_variables:
        mapping = var_to_mapping.get(var_name)
        if not mapping:
            continue
        if not _is_safe_identifier(mapping.db_table) or not _is_safe_identifier(mapping.db_column):
            logger.warning(f"Unsafe identifier in mapping: table={mapping.db_table}, column={mapping.db_column}")
            continue
        if not _table_exists(schema_snapshot, mapping.db_table):
            logger.warning(f"Table not found in schema: {mapping.db_table}")
            continue
        if not _column_exists(schema_snapshot, mapping.db_table, mapping.db_column):
            logger.warning(f"Column not found in schema: {mapping.db_table}.{mapping.db_column}")
            continue

        table_group.setdefault(mapping.db_table, []).append((mapping.db_column, var_name))
        data_prep.append({
            "var": var_name,
            "strategy": "select",
            "table": mapping.db_table,
            "column": mapping.db_column
        })

    if not table_group:
        return None, data_prep, required_variables

    statements: List[str] = []
    for table_name, cols in table_group.items():
        select_parts = [f"{col} AS {var_name}" for col, var_name in cols]
        statement = f"SELECT {', '.join(select_parts)} FROM {table_name} LIMIT 1"
        statements.append(statement)

    pre_sql = "; ".join(statements)
    return pre_sql, data_prep, required_variables
