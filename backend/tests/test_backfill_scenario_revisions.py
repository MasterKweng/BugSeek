from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from migrations.backfill_scenario_revisions import backfill_scenario


def _make_scenario(**overrides):
    payload = {
        "id": 101,
        "status": "active",
        "lifecycle_status": None,
        "created_by": 7,
        "updated_by": 9,
        "published_revision_id": None,
        "draft_revision_id": None,
        "latest_revision_no": 1,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _make_revision(revision_id: int, revision_no: int, status: str):
    return SimpleNamespace(id=revision_id, revision_no=revision_no, status=status)


def test_backfill_creates_published_revision_when_only_draft_exists_for_active_scenario():
    db = Mock()
    scenario = _make_scenario(status="active", lifecycle_status=None)
    existing_draft = _make_revision(10, 1, "draft")
    new_published = _make_revision(11, 2, "published")

    with patch(
        "migrations.backfill_scenario_revisions._latest_revision",
        side_effect=[existing_draft, new_published],
    ), patch(
        "migrations.backfill_scenario_revisions._latest_revision_by_status",
        side_effect=[None, new_published, existing_draft, None],
    ), patch(
        "migrations.backfill_scenario_revisions.ScenarioRevisionService.create_revision",
        return_value=new_published,
    ) as create_revision, patch(
        "migrations.backfill_scenario_revisions.ScenarioRevisionService.publish_revision",
    ) as publish_revision:
        changed, created = backfill_scenario(db, scenario, dry_run=False)

    assert changed is True
    assert created is True
    assert create_revision.call_count == 1
    assert publish_revision.call_count == 1
    assert scenario.lifecycle_status == "published"
    assert scenario.published_revision_id == 11
    assert scenario.latest_revision_no == 2


def test_backfill_reuses_existing_published_revision_without_creating_new_one():
    db = Mock()
    scenario = _make_scenario(
        status="active",
        lifecycle_status="published",
        published_revision_id=None,
    )
    published_revision = _make_revision(21, 3, "published")

    with patch(
        "migrations.backfill_scenario_revisions._latest_revision",
        side_effect=[published_revision, published_revision],
    ), patch(
        "migrations.backfill_scenario_revisions._latest_revision_by_status",
        side_effect=[published_revision, published_revision, None, None],
    ), patch(
        "migrations.backfill_scenario_revisions.ScenarioRevisionService.create_revision",
    ) as create_revision, patch(
        "migrations.backfill_scenario_revisions.ScenarioRevisionService.publish_revision",
    ) as publish_revision:
        changed, created = backfill_scenario(db, scenario, dry_run=False)

    assert changed is True
    assert created is False
    assert create_revision.call_count == 0
    assert publish_revision.call_count == 0
    assert scenario.published_revision_id == 21
    assert scenario.latest_revision_no == 3


def test_backfill_dry_run_does_not_mutate_or_create_revisions():
    db = Mock()
    scenario = _make_scenario(status="draft", lifecycle_status=None)
    latest_revision = _make_revision(31, 1, "draft")

    with patch(
        "migrations.backfill_scenario_revisions._latest_revision",
        return_value=latest_revision,
    ), patch(
        "migrations.backfill_scenario_revisions._latest_revision_by_status",
        return_value=latest_revision,
    ), patch(
        "migrations.backfill_scenario_revisions.ScenarioRevisionService.create_revision",
    ) as create_revision:
        changed, created = backfill_scenario(db, scenario, dry_run=True)

    assert changed is False
    assert created is False
    assert create_revision.call_count == 0
    assert scenario.published_revision_id is None
    assert scenario.draft_revision_id is None
