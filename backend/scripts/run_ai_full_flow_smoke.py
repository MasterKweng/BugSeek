"""Smoke test for AI full flow."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dependencies import SessionLocal
from app.platform.db.base import Project, Environment
from app.domains.ai_testing.engine import AITestingEngine
from app.platform.config.settings import settings


async def main():
    db = SessionLocal()
    try:
        project = db.query(Project).order_by(Project.id.asc()).first()
        if not project:
            print("No project found; abort")
            return
        env = db.query(Environment).filter(Environment.project_id == project.id).order_by(Environment.is_default.desc(), Environment.id.asc()).first()
        if not env:
            print("No environment found; abort")
            return

        if not settings.OPENAI_API_KEY:
            print("OPENAI_API_KEY is empty; AI call likely to fail")

        engine = AITestingEngine()
        result = await engine.run_full_flow(
            project_id=project.id,
            intent_text="???????????",
            environment_id=env.id,
            auto_fix=False,
        )
        print("Full flow result:")
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
