from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.domains.ai_testing.scenario_generator import ScenarioGenerator
from app.platform.db.base import ScenarioAISuggestion
from app.services.draft_normalizer import DraftNormalizer
from app.services.suggestion_guardrail_service import SuggestionGuardrailService


class ScenarioDraftGenerator:
    @staticmethod
    async def generate(
        db: Session,
        *,
        project_id: int,
        intent_text: str,
        version_id: Optional[int],
        created_by: Optional[int],
    ) -> Dict[str, Any]:
        draft = await ScenarioGenerator().generate(project_id=project_id, intent_text=intent_text)
        payload = DraftNormalizer.normalize(draft.model_dump() if hasattr(draft, "model_dump") else dict(draft))
        if version_id is not None:
            payload["scenario"]["version_id"] = version_id
        guarded = SuggestionGuardrailService.guard_draft(db, project_id=project_id, draft=payload)
        confidence = ScenarioDraftGenerator._estimate_confidence(guarded)
        suggestion = ScenarioAISuggestion(
            scenario_id=None,
            revision_id=None,
            suggestion_type="draft",
            payload_json={
                "intent_text": intent_text,
                "draft": guarded,
            },
            confidence=confidence,
            status="pending",
            created_by=created_by,
        )
        db.add(suggestion)
        db.flush()
        return {
            "suggestion_id": suggestion.id,
            "draft": guarded,
            "confidence": confidence,
        }

    @staticmethod
    def _estimate_confidence(payload: Dict[str, Any]) -> float:
        candidate_count = len(payload.get("candidate_apis") or [])
        node_count = len(payload.get("nodes") or [])
        if not node_count:
            return 0.2
        confidence = 0.45
        confidence += min(candidate_count, 5) * 0.08
        confidence += min(node_count, 5) * 0.05
        return round(min(confidence, 0.95), 2)
