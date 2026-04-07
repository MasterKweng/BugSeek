"""Inspect field-mapping task artifacts for cross-lineage agreement potential."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = CURRENT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.chdir(BACKEND_ROOT)

from app.dependencies import SessionLocal  # noqa: E402
from app.platform.db.base import AsyncTask, FieldMappingStageArtifact  # noqa: E402
from app.domains.field_mapping_engine.constants import Stage  # noqa: E402
from app.domains.field_mapping_engine.evidence.feature_builder import FeatureBuilder  # noqa: E402
from app.domains.field_mapping_engine.ranking.ranker import CandidateRanker  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze cross-lineage evidence on field-mapping tasks.")
    parser.add_argument("task_ids", nargs="+", type=int, help="Field-mapping async task ids.")
    parser.add_argument("--top", type=int, default=12, help="How many impacted fields to print.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of readable text.")
    return parser.parse_args()


def load_artifact_payload(session: Any, task_id: int, artifact_type: str) -> Dict[str, Any] | None:
    row = (
        session.query(FieldMappingStageArtifact)
        .filter(
            FieldMappingStageArtifact.task_id == task_id,
            FieldMappingStageArtifact.stage == Stage.AI_OPTIMIZATION,
            FieldMappingStageArtifact.artifact_type == artifact_type,
        )
        .order_by(FieldMappingStageArtifact.id.desc())
        .first()
    )
    if row is None and artifact_type == "ai_ranked_items":
        row = (
            session.query(FieldMappingStageArtifact)
            .filter(
                FieldMappingStageArtifact.task_id == task_id,
                FieldMappingStageArtifact.artifact_type == artifact_type,
            )
            .order_by(FieldMappingStageArtifact.id.desc())
            .first()
        )
    if row is None:
        return None
    payload = getattr(row, "payload_json", None)
    return payload if isinstance(payload, dict) else None


def task_meta(session: Any, task_id: int) -> Dict[str, Any]:
    task = session.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if task is None:
        return {"task_id": task_id, "missing": True}
    return {
        "task_id": task_id,
        "status": getattr(task, "status", None),
        "project_id": getattr(task, "project_id", None),
        "current_stage": getattr(task, "current_stage", None),
        "statistics": getattr(task, "statistics", None),
    }


def iter_ranked_items(payload: Dict[str, Any] | None) -> Iterable[Dict[str, Any]]:
    if not payload:
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return items


def analyze_ranked_item(item: Dict[str, Any], *, feature_builder: FeatureBuilder, ranker: CandidateRanker) -> Dict[str, Any]:
    rule_candidates = [dict(candidate) for candidate in list(item.get("rule_candidates") or [])]
    if not rule_candidates:
        return {
            "api_field_path": item.get("api_field_path"),
            "field_name": item.get("field_name"),
            "candidate_count": 0,
            "cross_hits": 0,
            "top_changed": False,
            "max_cross": 0.0,
            "top_before": None,
            "top_after": None,
        }

    before_ranked = [dict(candidate) for candidate in rule_candidates]
    after_candidates: List[Dict[str, Any]] = []
    cross_hits = 0
    max_cross = 0.0
    top_before = before_ranked[0]
    for candidate in rule_candidates:
        enriched = feature_builder.enrich_candidate(field_item=item, candidate=dict(candidate))
        cross_score = float((enriched.get("features") or {}).get("f_cross_lineage_agreement", 0.0) or 0.0)
        if cross_score > 0.0:
            cross_hits += 1
            max_cross = max(max_cross, cross_score)
        after_candidates.append(enriched)

    reranked = ranker.rank_from_dict(after_candidates)
    top_after = reranked[0] if reranked else None
    top_changed = (
        bool(top_before)
        and bool(top_after)
        and (
            str(top_before.get("db_table") or "") != str(top_after.get("db_table") or "")
            or str(top_before.get("db_column") or "") != str(top_after.get("db_column") or "")
        )
    )
    return {
        "api_field_path": item.get("api_field_path"),
        "field_name": item.get("field_name"),
        "candidate_count": len(rule_candidates),
        "cross_hits": cross_hits,
        "top_changed": top_changed,
        "max_cross": round(max_cross, 4),
        "top_before": summarize_candidate(top_before),
        "top_after": summarize_candidate(top_after),
    }


def summarize_candidate(candidate: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not candidate:
        return None
    features = dict(candidate.get("features", {}) or {})
    return {
        "db_table": candidate.get("db_table"),
        "db_column": candidate.get("db_column"),
        "score": candidate.get("score"),
        "recall_sources": list(candidate.get("recall_sources", []) or []),
        "f_sql_lineage_exact": float(features.get("f_sql_lineage_exact", 0.0) or 0.0),
        "f_code_assignment_hit": float(features.get("f_code_assignment_hit", 0.0) or 0.0),
        "f_cross_lineage_agreement": float(features.get("f_cross_lineage_agreement", 0.0) or 0.0),
    }


def analyze_task(session: Any, task_id: int) -> Dict[str, Any]:
    meta = task_meta(session, task_id)
    payload = load_artifact_payload(session, task_id, "ai_ranked_items")
    if payload is None:
        meta["error"] = "ai_ranked_items artifact not found"
        return meta

    feature_builder = FeatureBuilder()
    ranker = CandidateRanker()
    field_results = [
        analyze_ranked_item(item, feature_builder=feature_builder, ranker=ranker)
        for item in iter_ranked_items(payload)
    ]
    cross_fields = [item for item in field_results if item.get("cross_hits", 0) > 0]
    changed_fields = [item for item in field_results if item.get("top_changed")]
    meta["summary"] = {
        "field_count": len(field_results),
        "fields_with_cross_hits": len(cross_fields),
        "fields_with_top_change": len(changed_fields),
        "max_cross": max((float(item.get("max_cross", 0.0) or 0.0) for item in field_results), default=0.0),
    }
    meta["top_impacts"] = sorted(
        cross_fields,
        key=lambda item: (
            int(bool(item.get("top_changed"))),
            float(item.get("max_cross", 0.0) or 0.0),
            int(item.get("cross_hits", 0) or 0),
        ),
        reverse=True,
    )
    return meta


def print_readable(result: Dict[str, Any], *, top: int) -> None:
    print(f"Task {result.get('task_id')}")
    if result.get("missing"):
        print("  task missing")
        return
    if result.get("error"):
        print(f"  error: {result['error']}")
        return
    summary = result.get("summary", {})
    print(f"  status: {result.get('status')}")
    print(f"  fields: {summary.get('field_count', 0)}")
    print(f"  fields_with_cross_hits: {summary.get('fields_with_cross_hits', 0)}")
    print(f"  fields_with_top_change: {summary.get('fields_with_top_change', 0)}")
    print(f"  max_cross: {summary.get('max_cross', 0.0)}")
    for item in list(result.get("top_impacts", []) or [])[:top]:
        print(
            "  - {path}: cross_hits={hits} max_cross={cross} top_changed={changed}".format(
                path=item.get("api_field_path"),
                hits=item.get("cross_hits"),
                cross=item.get("max_cross"),
                changed=item.get("top_changed"),
            )
        )
        print(f"    before: {item.get('top_before')}")
        print(f"    after:  {item.get('top_after')}")


def main() -> int:
    args = parse_args()
    session = SessionLocal()
    try:
        results = [analyze_task(session, task_id) for task_id in args.task_ids]
    finally:
        session.close()

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for result in results:
        print_readable(result, top=args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
