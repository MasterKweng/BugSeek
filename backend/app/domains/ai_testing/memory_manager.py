"""AI memory manager."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.platform.db.base import AiMemory
from app.ai.embedding_service import EmbeddingService


class MemoryManager:
    def __init__(self):
        self.embedding = EmbeddingService()

    def store(
        self,
        project_id: Optional[int],
        memory_type: str,
        context: Dict[str, Any],
        result: Dict[str, Any],
    ) -> int:
        db: Session = next(get_db())
        try:
            text = _pack_text(context, result)
            try:
                embedding = self.embedding.encode([text])[0] if text else None
            except Exception:
                embedding = None
            item = AiMemory(
                project_id=project_id,
                memory_type=memory_type,
                context=context,
                result=result,
                embedding=embedding,
            )
            db.add(item)
            db.commit()
            return item.id
        finally:
            db.close()

    def search(
        self,
        project_id: Optional[int],
        query: Dict[str, Any],
        memory_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        db: Session = next(get_db())
        try:
            text = _pack_text(query, {})
            try:
                query_vec = self.embedding.encode([text])[0] if text else None
            except Exception:
                query_vec = None

            q = db.query(AiMemory)
            if project_id is not None:
                q = q.filter(AiMemory.project_id == project_id)
            if memory_type:
                q = q.filter(AiMemory.memory_type == memory_type)

            rows = q.order_by(AiMemory.id.desc()).limit(200).all()
            if not query_vec:
                return [self._to_dict(row, score=None) for row in rows[:top_k]]

            scored = []
            for row in rows:
                if not row.embedding:
                    continue
                score = self.embedding.similarity(query_vec, row.embedding)
                scored.append((score, row))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [self._to_dict(r, score=s) for s, r in scored[:top_k]]
        finally:
            db.close()

    def _to_dict(self, row: AiMemory, score: Optional[float]) -> Dict[str, Any]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "memory_type": row.memory_type,
            "context": row.context,
            "result": row.result,
            "score": score,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


def _pack_text(context: Dict[str, Any], result: Dict[str, Any]) -> str:
    parts = []
    if context:
        parts.append(str(context))
    if result:
        parts.append(str(result))
    return "\n".join(parts)
