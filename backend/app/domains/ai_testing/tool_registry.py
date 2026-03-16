"""Tool registry for AI testing engine."""
from __future__ import annotations

from typing import Any, Dict, Callable

from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.domains.api_hub.retrieval.service import APIRetrievalService
from app.platform.db.base import DbSchemaVersion
from app.ai.service import AIService


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def get(self, name: str) -> Callable[..., Any]:
        return self._tools[name]

    def list(self) -> Dict[str, Callable[..., Any]]:
        return dict(self._tools)


def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()

    def search_api(user_intent: str, project_id: int):
        db: Session = next(get_db())
        try:
            service = APIRetrievalService(db)
            return service.retrieve_apis_by_intent_lite(
                user_intent=user_intent,
                project_id=project_id,
                top_k=10,
            )
        finally:
            db.close()

    def search_table(project_id: int):
        db: Session = next(get_db())
        try:
            schema = (
                db.query(DbSchemaVersion)
                .filter(DbSchemaVersion.project_id == project_id)
                .order_by(DbSchemaVersion.updated_at.desc())
                .first()
            )
            return schema.schema_snapshot if schema else {}
        finally:
            db.close()

    async def generate_test(project_id: int, input_data: Dict[str, Any]):
        ai = AIService()
        return await ai.execute(
            task_type="api_case_generation",
            project_id=project_id,
            input_data=input_data,
        )

    registry.register("search_api", search_api)
    registry.register("search_table", search_table)
    registry.register("generate_test", generate_test)

    return registry
