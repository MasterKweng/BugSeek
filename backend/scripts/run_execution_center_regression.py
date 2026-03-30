from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from fastapi.testclient import TestClient
from jose import jwt

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("APP_ENV", "dev")

from app.api.v1.deps import get_current_user  # noqa: E402
from app.context import update_user_context  # noqa: E402
from app.dependencies import SessionLocal, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.platform.config.settings import settings  # noqa: E402
from app.platform.db.base import (  # noqa: E402
    ApiDefinition,
    Environment,
    TestExecution,
    TestExecutionResult,
    User,
    Version,
)


SEED_PREFIX = "[Execution Regression Seed]"


@dataclass
class SeedContext:
    user_id: int
    username: str
    project_id: int
    version_id: int
    environment_id: int
    environment_name: str
    definition_ids: List[int]
    execution_ids: Dict[str, int]
    result_ids: Dict[str, int]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _pick_seed_base():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin").first() or db.query(User).order_by(User.id.asc()).first()
        _assert(user is not None, "no user found in database")

        version = db.query(Version).order_by(Version.id.asc()).first()
        _assert(version is not None, "no version found in database")

        environment = (
            db.query(Environment)
            .filter(Environment.project_id == version.project_id)
            .order_by(Environment.id.asc())
            .first()
        )
        _assert(environment is not None, f"no environment found for project {version.project_id}")

        definitions = (
            db.query(ApiDefinition)
            .filter(ApiDefinition.project_id == version.project_id)
            .order_by(ApiDefinition.id.asc())
            .limit(3)
            .all()
        )
        _assert(len(definitions) >= 3, f"not enough api definitions for project {version.project_id}")
        return user, version, environment, definitions
    finally:
        db.close()


def _reset_seed_data(db):
    execution_ids = [
        row.id
        for row in db.query(TestExecution.id)
        .filter(TestExecution.title.ilike(f"{SEED_PREFIX}%"))
        .all()
    ]
    execution_ids = [row[0] if isinstance(row, tuple) else row for row in execution_ids]
    if execution_ids:
        db.query(TestExecutionResult).filter(TestExecutionResult.execution_id.in_(execution_ids)).delete(
            synchronize_session=False
        )
        db.query(TestExecution).filter(TestExecution.id.in_(execution_ids)).delete(synchronize_session=False)
        db.commit()


def _seed_data() -> SeedContext:
    user, version, environment, definitions = _pick_seed_base()
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        _reset_seed_data(db)
        user = db.query(User).filter(User.id == user.id).first()
        version = db.query(Version).filter(Version.id == version.id).first()
        environment = db.query(Environment).filter(Environment.id == environment.id).first()
        definitions = [db.query(ApiDefinition).filter(ApiDefinition.id == item.id).first() for item in definitions]

        update_user_context(db, user, project_id=version.project_id, version_id=version.id)

        source_single = TestExecution(
            project_id=version.project_id,
            version_id=version.id,
            execution_type="single",
            target_id=definitions[0].id,
            operator_user_id=user.id,
            title=f"{SEED_PREFIX} Source Single",
            summary_json={"seed": True, "role": "source"},
            result_status="failed",
            environment_id=environment.id,
            execution_mode="sequential",
            triggered_by="manual",
            status="completed",
            started_at=now - timedelta(minutes=20),
            finished_at=now - timedelta(minutes=19, seconds=50),
            duration=10000,
            total=1,
            passed=0,
            failed=1,
            skipped=0,
        )
        db.add(source_single)
        db.flush()

        rerun_single = TestExecution(
            project_id=version.project_id,
            version_id=version.id,
            execution_type="single",
            target_id=definitions[0].id,
            operator_user_id=user.id,
            title=f"{SEED_PREFIX} Rerun Single",
            summary_json={"seed": True, "role": "rerun"},
            result_status="passed",
            source_execution_id=source_single.id,
            environment_id=environment.id,
            execution_mode="sequential",
            triggered_by="rerun",
            status="completed",
            started_at=now - timedelta(minutes=18),
            finished_at=now - timedelta(minutes=17, seconds=50),
            duration=10000,
            total=1,
            passed=1,
            failed=0,
            skipped=0,
        )
        db.add(rerun_single)
        db.flush()

        batch_parent = TestExecution(
            project_id=version.project_id,
            version_id=version.id,
            execution_type="batch",
            target_id=definitions[1].id,
            operator_user_id=user.id,
            title=f"{SEED_PREFIX} Batch Parent",
            summary_json={"seed": True, "role": "parent", "case_ids": []},
            result_status="partial_failed",
            environment_id=environment.id,
            execution_mode="parallel",
            triggered_by="manual",
            status="completed",
            started_at=now - timedelta(minutes=15),
            finished_at=now - timedelta(minutes=14, seconds=30),
            duration=30000,
            total=2,
            passed=1,
            failed=1,
            skipped=0,
        )
        db.add(batch_parent)
        db.flush()

        child_passed = TestExecution(
            project_id=version.project_id,
            version_id=version.id,
            execution_type="single",
            target_id=definitions[1].id,
            parent_execution_id=batch_parent.id,
            operator_user_id=user.id,
            title=f"{SEED_PREFIX} Child Passed",
            summary_json={"seed": True, "role": "child-pass"},
            result_status="passed",
            environment_id=environment.id,
            execution_mode="sequential",
            triggered_by="manual",
            status="completed",
            started_at=now - timedelta(minutes=15),
            finished_at=now - timedelta(minutes=14, seconds=50),
            duration=10000,
            total=1,
            passed=1,
            failed=0,
            skipped=0,
        )
        child_failed = TestExecution(
            project_id=version.project_id,
            version_id=version.id,
            execution_type="single",
            target_id=definitions[2].id,
            parent_execution_id=batch_parent.id,
            operator_user_id=user.id,
            title=f"{SEED_PREFIX} Child Failed",
            summary_json={"seed": True, "role": "child-fail"},
            result_status="failed",
            environment_id=environment.id,
            execution_mode="sequential",
            triggered_by="manual",
            status="completed",
            started_at=now - timedelta(minutes=14, seconds=45),
            finished_at=now - timedelta(minutes=14, seconds=30),
            duration=15000,
            total=1,
            passed=0,
            failed=1,
            skipped=0,
        )
        db.add_all([child_passed, child_failed])
        db.flush()

        source_result = TestExecutionResult(
            execution_id=source_single.id,
            target_type="endpoint",
            target_id=definitions[0].id,
            definition_id=definitions[0].id,
            target_name="Source Definition",
            status="failed",
            response_time=520,
            response_code=500,
            response_body={"raw": '{"error":"seed failed"}', "json": {"error": "seed failed"}},
            request_body={"raw": '{"seed":"source"}', "json": {"seed": "source"}},
            response_headers={"content-type": "application/json"},
            request_headers={"x-seed": "source"},
            request_display_type="json",
            response_display_type="json",
            assertion_results={"assertions": [{"name": "status_code", "success": False}]},
            assertion_passed_count=0,
            assertion_total_count=1,
            extracted_variables={"trace_id": "seed-source"},
            error_message="seed source failure",
            sort_order=1,
        )
        rerun_result = TestExecutionResult(
            execution_id=rerun_single.id,
            target_type="endpoint",
            target_id=definitions[0].id,
            definition_id=definitions[0].id,
            target_name="Rerun Definition",
            status="passed",
            response_time=210,
            response_code=200,
            response_body={"raw": '{"ok":true}', "json": {"ok": True}},
            request_body={"raw": '{"seed":"rerun"}', "json": {"seed": "rerun"}},
            response_headers={"content-type": "application/json"},
            request_headers={"x-seed": "rerun"},
            request_display_type="json",
            response_display_type="json",
            assertion_results={"assertions": [{"name": "status_code", "success": True}]},
            assertion_passed_count=1,
            assertion_total_count=1,
            extracted_variables={"trace_id": "seed-rerun"},
            error_message=None,
            sort_order=1,
        )
        child_passed_result = TestExecutionResult(
            execution_id=child_passed.id,
            target_type="endpoint",
            target_id=definitions[1].id,
            definition_id=definitions[1].id,
            target_name="Batch Passed Definition",
            status="passed",
            response_time=180,
            response_code=200,
            response_body={"raw": '{"success":true}', "json": {"success": True}},
            request_body={"raw": '{"seed":"child-pass"}', "json": {"seed": "child-pass"}},
            response_headers={"content-type": "application/json", "x-env": environment.name},
            request_headers={"x-seed": "child-pass"},
            request_display_type="json",
            response_display_type="json",
            assertion_results={"assertions": [{"name": "status_code", "success": True}]},
            assertion_passed_count=1,
            assertion_total_count=1,
            extracted_variables={"token": "child-pass"},
            error_message=None,
            sort_order=1,
        )
        child_failed_result = TestExecutionResult(
            execution_id=child_failed.id,
            target_type="endpoint",
            target_id=definitions[2].id,
            definition_id=definitions[2].id,
            target_name="Batch Failed Definition",
            status="failed",
            response_time=860,
            response_code=502,
            response_body={"raw": '{"error":"upstream"}', "json": {"error": "upstream"}},
            request_body={"raw": '{"seed":"child-fail"}', "json": {"seed": "child-fail"}},
            response_headers={"content-type": "application/json", "x-env": environment.name},
            request_headers={"x-seed": "child-fail"},
            request_display_type="json",
            response_display_type="json",
            assertion_results={"assertions": [{"name": "status_code", "success": False}]},
            assertion_passed_count=0,
            assertion_total_count=1,
            extracted_variables={"token": "child-fail"},
            error_message="upstream failed",
            sort_order=1,
        )
        db.add_all([source_result, rerun_result, child_passed_result, child_failed_result])
        db.commit()
        db.refresh(source_single)
        db.refresh(rerun_single)
        db.refresh(batch_parent)
        db.refresh(child_passed)
        db.refresh(child_failed)
        db.refresh(child_failed_result)

        return SeedContext(
            user_id=user.id,
            username=user.username,
            project_id=version.project_id,
            version_id=version.id,
            environment_id=environment.id,
            environment_name=environment.name,
            definition_ids=[item.id for item in definitions],
            execution_ids={
                "source_single": source_single.id,
                "rerun_single": rerun_single.id,
                "batch_parent": batch_parent.id,
                "child_passed": child_passed.id,
                "child_failed": child_failed.id,
            },
            result_ids={
                "source_result": source_result.id,
                "rerun_result": rerun_result.id,
                "child_passed_result": child_passed_result.id,
                "child_failed_result": child_failed_result.id,
            },
        )
    finally:
        db.close()


def _override_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_api_checks(seed: SeedContext) -> None:
    app.dependency_overrides[get_db] = _override_db

    def _override_current_user():
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == seed.user_id).first()
            _assert(user is not None, f"user {seed.user_id} not found during api smoke")
            db.expunge(user)
            return user
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = _override_current_user

    client = TestClient(app)
    base = settings.API_V1_STR

    try:
        list_resp = client.get(f"{base}/executions")
        _assert(list_resp.status_code == 200, f"list executions failed: {list_resp.status_code}")
        list_data = list_resp.json()["data"]
        execution_ids = {item["id"] for item in list_data["items"]}
        _assert(seed.execution_ids["batch_parent"] in execution_ids, "batch parent missing from list endpoint")
        _assert(seed.execution_ids["rerun_single"] in execution_ids, "rerun execution missing from list endpoint")

        filtered_resp = client.get(
            f"{base}/executions",
            params={"definition_id": seed.definition_ids[2]},
        )
        _assert(filtered_resp.status_code == 200, f"filtered executions failed: {filtered_resp.status_code}")
        filtered_items = filtered_resp.json()["data"]["items"]
        _assert(any(item["id"] == seed.execution_ids["child_failed"] for item in filtered_items), "definition filter did not match child failed execution")

        detail_resp = client.get(f"{base}/executions/{seed.execution_ids['batch_parent']}")
        _assert(detail_resp.status_code == 200, f"execution detail failed: {detail_resp.status_code}")
        detail_data = detail_resp.json()["data"]
        _assert(detail_data["children_count"] == 2, "children_count mismatch")
        _assert(detail_data["result_status"] == "partial_failed", "batch parent result_status mismatch")

        children_resp = client.get(f"{base}/executions/{seed.execution_ids['batch_parent']}/children")
        _assert(children_resp.status_code == 200, f"children endpoint failed: {children_resp.status_code}")
        children_data = children_resp.json()["data"]["items"]
        _assert(len(children_data) == 2, "children endpoint count mismatch")

        results_resp = client.get(f"{base}/executions/{seed.execution_ids['child_failed']}/results")
        _assert(results_resp.status_code == 200, f"results endpoint failed: {results_resp.status_code}")
        results_data = results_resp.json()["data"]["items"]
        _assert(len(results_data) == 1, "child failed results count mismatch")
        _assert(results_data[0]["definition_id"] == seed.definition_ids[2], "result definition_id mismatch")

        result_detail_resp = client.get(f"{base}/execution-results/{seed.result_ids['child_failed_result']}")
        _assert(result_detail_resp.status_code == 200, f"result detail failed: {result_detail_resp.status_code}")
        result_detail = result_detail_resp.json()["data"]
        _assert(result_detail["request"]["headers"]["x-seed"] == "child-fail", "request headers mismatch")
        _assert(result_detail["response"]["headers"]["x-env"] == seed.environment_name, "response headers mismatch")
        _assert(result_detail["assertions"]["passed"] == 0, "assertion passed count mismatch")
        _assert(result_detail["assertions"]["total"] == 1, "assertion total count mismatch")

        summary_resp = client.get(f"{base}/reports/executions/summary")
        _assert(summary_resp.status_code == 200, f"summary report failed: {summary_resp.status_code}")
        summary_data = summary_resp.json()["data"]
        _assert(summary_data["total_executions"] >= 5, "summary total_executions too small")
        _assert(summary_data["total_results"] >= 4, "summary total_results too small")

        trends_resp = client.get(f"{base}/reports/executions/trends", params={"group_by": "day"})
        _assert(trends_resp.status_code == 200, f"trends report failed: {trends_resp.status_code}")
        _assert(len(trends_resp.json()["data"]["items"]) >= 1, "trends data empty")

        env_resp = client.get(f"{base}/reports/executions/environment-comparison")
        _assert(env_resp.status_code == 200, f"environment comparison failed: {env_resp.status_code}")
        _assert(len(env_resp.json()["data"]["items"]) >= 1, "environment comparison empty")

        version_resp = client.get(f"{base}/reports/executions/version-comparison")
        _assert(version_resp.status_code == 200, f"version comparison failed: {version_resp.status_code}")
        _assert(len(version_resp.json()["data"]["items"]) >= 1, "version comparison empty")
    finally:
        app.dependency_overrides.clear()


def main() -> None:
    print("== Execution Center Regression Smoke ==")
    seed = _seed_data()
    print(f"seed user: {seed.username} ({seed.user_id})")
    print(f"seed project/version/environment: {seed.project_id}/{seed.version_id}/{seed.environment_id}")
    print(f"seed executions: {seed.execution_ids}")
    print(f"seed results: {seed.result_ids}")
    _run_api_checks(seed)
    print("all api smoke checks passed")
    print("manual regression pages:")
    print("  /operations/executions")
    print(f"  /operations/executions/{seed.execution_ids['batch_parent']}")
    print("  /operations/reports")
    print("note: rerun endpoint intentionally not auto-triggered in smoke script because it creates real execution tasks")


if __name__ == "__main__":
    main()
