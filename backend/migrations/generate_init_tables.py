"""Generate full database initialization assets from the live database schema.

Execution center note:
The baseline schema now includes ``public.test_executions`` and
``public.test_execution_results`` so fresh environments can initialize the
execution center without applying a follow-up patch.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable, sort_tables_and_constraints

from app.dependencies import engine


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PY = BASE_DIR / "init_tables.py"
OUTPUT_SQL = BASE_DIR / "init_schema.sql"


def _normalize_sql(sql: str) -> str:
    sql = sql.strip()
    if not sql.endswith(";"):
        sql += ";"
    return sql


def collect_ddl_statements() -> list[str]:
    metadata = MetaData()
    metadata.reflect(bind=engine, schema="public")

    dialect = postgresql.dialect()
    statements: list[str] = ['CREATE SCHEMA IF NOT EXISTS public;']

    ordered = sort_tables_and_constraints(metadata.tables.values())

    for table, foreign_keys in ordered:
        if table is not None:
            statements.append(
                _normalize_sql(
                    str(
                        CreateTable(
                            table,
                            include_foreign_key_constraints=list(foreign_keys),
                        ).compile(dialect=dialect)
                    )
                )
            )
            continue

        for foreign_key in foreign_keys:
            statements.append(_normalize_sql(str(AddConstraint(foreign_key).compile(dialect=dialect))))

    for table in metadata.tables.values():
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            statements.append(_normalize_sql(str(CreateIndex(index).compile(dialect=dialect))))

    return statements


def render_python(statements: list[str]) -> str:
    rendered_statements = ",\n".join(
        f"    {json.dumps(statement, ensure_ascii=False)}" for statement in statements
    )

    return f'''"""Full database initialization script generated from the live database schema.

Execution center note:
The baseline schema includes ``public.test_executions`` and
``public.test_execution_results``.
"""

from __future__ import annotations

import logging

from app.dependencies import engine


logger = logging.getLogger(__name__)

DDL_STATEMENTS = [
{rendered_statements}
]


def init_tables() -> None:
    """Create the full database schema in statement order."""
    with engine.begin() as conn:
        for statement in DDL_STATEMENTS:
            conn.exec_driver_sql(statement)

    logger.info("Database schema initialization completed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    init_tables()
'''


def render_sql(statements: list[str]) -> str:
    return (
        "-- Full database initialization script generated from the live database schema.\n"
        "--\n"
        "-- Execution center note:\n"
        "-- The baseline schema includes public.test_executions and\n"
        "-- public.test_execution_results.\n"
        "\n"
        + "\n\n".join(statements)
        + "\n"
    )


def main() -> None:
    statements = collect_ddl_statements()
    OUTPUT_PY.write_text(render_python(statements), encoding="utf-8")
    OUTPUT_SQL.write_text(render_sql(statements), encoding="utf-8")
    print(f"Generated {OUTPUT_PY}")
    print(f"Generated {OUTPUT_SQL}")
    print(f"Statements: {len(statements)}")


if __name__ == "__main__":
    main()
