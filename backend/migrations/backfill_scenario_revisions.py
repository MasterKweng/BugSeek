"""Backfill scenario revisions for legacy scenarios.

This script migrates existing scenarios that only have ``api_scenarios`` +
``scenario_nodes`` state into the new revision-based model introduced in P0-P2.

Behavior:
- draft scenarios get a draft revision and ``draft_revision_id``
- active scenarios get a published revision and ``published_revision_id``
- archived scenarios get an archived revision so history is not lost

The script is idempotent:
- it will reuse existing revisions when possible
- it only creates a new revision when the scenario has no revisions yet
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.dependencies import SessionLocal
from app.platform.db.base import ApiScenario, ScenarioRevision
from app.services.scenario_revision_service import ScenarioRevisionService

logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    scanned: int = 0
    created_revisions: int = 0
    updated_scenarios: int = 0
    reused_revisions: int = 0


def _normalize_lifecycle_status(scenario: ApiScenario) -> str:
    lifecycle_status = getattr(scenario, "lifecycle_status", None)
    if lifecycle_status in {"draft", "validated", "published", "archived"}:
        return lifecycle_status

    legacy_status = (scenario.status or "draft").lower()
    if legacy_status == "active":
        return "published"
    if legacy_status == "archived":
        return "archived"
    return "draft"


def _target_revision_status(scenario: ApiScenario) -> str:
    lifecycle_status = _normalize_lifecycle_status(scenario)
    if lifecycle_status == "published":
        return "published"
    if lifecycle_status == "archived":
        return "archived"
    return "draft"


def _latest_revision_by_status(db: Session, scenario_id: int, status: str) -> Optional[ScenarioRevision]:
    return (
        db.query(ScenarioRevision)
        .filter(
            ScenarioRevision.scenario_id == scenario_id,
            ScenarioRevision.status == status,
        )
        .order_by(ScenarioRevision.revision_no.desc())
        .first()
    )


def _latest_revision(db: Session, scenario_id: int) -> Optional[ScenarioRevision]:
    return (
        db.query(ScenarioRevision)
        .filter(ScenarioRevision.scenario_id == scenario_id)
        .order_by(ScenarioRevision.revision_no.desc())
        .first()
    )


def backfill_scenario(db: Session, scenario: ApiScenario, *, dry_run: bool = False) -> tuple[bool, bool]:
    changed = False
    created_revision = False

    lifecycle_status = _normalize_lifecycle_status(scenario)
    target_revision_status = _target_revision_status(scenario)

    revision = _latest_revision(db, scenario.id)
    matching_revision = _latest_revision_by_status(db, scenario.id, target_revision_status)

    if revision is None:
        logger.info(
            "Scenario %s has no revisions, creating initial %s revision",
            scenario.id,
            target_revision_status,
        )
        if not dry_run:
            revision = ScenarioRevisionService.create_revision(
                db,
                scenario=scenario,
                created_by=scenario.updated_by or scenario.created_by,
                status=target_revision_status if target_revision_status != "published" else "draft",
            )
            if target_revision_status == "published":
                ScenarioRevisionService.publish_revision(
                    db,
                    scenario=scenario,
                    revision=revision,
                    published_by=scenario.updated_by or scenario.created_by,
                )
            else:
                revision.status = target_revision_status
        created_revision = True
        changed = True
    elif matching_revision is None and lifecycle_status in {"draft", "published", "archived"}:
        logger.info(
            "Scenario %s has revisions but no %s revision, creating one for lifecycle alignment",
            scenario.id,
            target_revision_status,
        )
        if not dry_run:
            matching_revision = ScenarioRevisionService.create_revision(
                db,
                scenario=scenario,
                created_by=scenario.updated_by or scenario.created_by,
                status=target_revision_status if target_revision_status != "published" else "draft",
            )
            if target_revision_status == "published":
                ScenarioRevisionService.publish_revision(
                    db,
                    scenario=scenario,
                    revision=matching_revision,
                    published_by=scenario.updated_by or scenario.created_by,
                )
            else:
                matching_revision.status = target_revision_status
        created_revision = True
        changed = True
    else:
        logger.info("Scenario %s already has revisions, reusing latest revision %s", scenario.id, revision.id)

    if not dry_run:
        latest = _latest_revision(db, scenario.id)
        published_revision = _latest_revision_by_status(db, scenario.id, "published")
        draft_revision = _latest_revision_by_status(db, scenario.id, "draft")
        archived_revision = _latest_revision_by_status(db, scenario.id, "archived")

        scenario.lifecycle_status = lifecycle_status
        scenario.latest_revision_no = latest.revision_no if latest else scenario.latest_revision_no

        if lifecycle_status == "published":
            target_revision_id = published_revision.id if published_revision else None
            if scenario.published_revision_id != target_revision_id:
                scenario.published_revision_id = target_revision_id
                changed = True
        elif lifecycle_status == "draft":
            target_revision_id = draft_revision.id if draft_revision else None
            if scenario.draft_revision_id != target_revision_id:
                scenario.draft_revision_id = target_revision_id
                changed = True
        elif lifecycle_status == "archived":
            target_revision_id = archived_revision.id if archived_revision else None
            if scenario.draft_revision_id != target_revision_id:
                scenario.draft_revision_id = target_revision_id
                changed = True

    return changed, created_revision


def backfill_all(*, dry_run: bool = False) -> BackfillResult:
    result = BackfillResult()
    db: Session = SessionLocal()
    try:
        scenarios = db.query(ApiScenario).order_by(ApiScenario.id.asc()).all()
        result.scanned = len(scenarios)
        for scenario in scenarios:
            changed, created_revision = backfill_scenario(db, scenario, dry_run=dry_run)
            if created_revision:
                result.created_revisions += 1
            elif changed:
                result.reused_revisions += 1
            if changed:
                result.updated_scenarios += 1

        if dry_run:
            db.rollback()
            logger.info("Dry run complete, rolled back all changes")
        else:
            db.commit()
            logger.info("Backfill committed successfully")
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill scenario revisions for legacy scenarios")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = backfill_all(dry_run=args.dry_run)
    logger.info(
        "Scanned=%s, CreatedRevisions=%s, UpdatedScenarios=%s, ReusedRevisions=%s",
        result.scanned,
        result.created_revisions,
        result.updated_scenarios,
        result.reused_revisions,
    )


if __name__ == "__main__":
    main()
