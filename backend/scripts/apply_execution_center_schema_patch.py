from pathlib import Path

from sqlalchemy import text

from app.dependencies import engine
from app.platform.db.base import Base, TestExecution, TestExecutionResult


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    sql_path = root / "docs" / "execution_center_schema_patch.sql"
    sql_text = sql_path.read_text(encoding="utf-8")

    statements = [item.strip() for item in sql_text.split(";") if item.strip()]
    Base.metadata.create_all(bind=engine, tables=[TestExecution.__table__, TestExecutionResult.__table__], checkfirst=True)
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))

    print(f"Applied execution center schema patch: {sql_path}")
    print(f"Executed {len(statements)} statements")


if __name__ == "__main__":
    main()
