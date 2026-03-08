# Scenario Baseline Diff (Task 1)

## Goal
Create a factual baseline of scenario-related code drift between:
- current active model and APIs
- historical/backup model and migration scripts

This document is the source of truth before implementing scenario V1.

## Scope
- `backend/app/db/base.py`
- `backend/app/db/base_backup.py`
- `backend/app/core/sync/change_detector.py`
- `backend/app/core/test_execution.py`
- `backend/migrations/add_scenario_tables.py`

## Findings Summary

| Area | Current State | Historical State | Gap |
|---|---|---|---|
| Scenario ORM model | Missing in `base.py` | Present in `base_backup.py` (`ApiScenario`, `ScenarioEndpoint`) | Core scenario entities are not in active metadata |
| Scenario dependency model | Missing in `base.py` | Present in `base_backup.py` (`ApiDependency`) | Upstream dependency graph for scenario is absent |
| Scenario execution | `ScenarioExecutor` exists but raises `NotImplementedError` | N/A | No runnable scenario engine |
| Scenario impact scan | `change_detector.py` imports `ApiScenario` from active `base.py` | `ApiScenario` only exists in backup file | Runtime import mismatch risk |
| Scenario migration script | `add_scenario_tables.py` imports `ApiDependency`, `ApiScenario`, `ScenarioEndpoint` from active `base.py` | Entities exist only in backup file | Migration script cannot run cleanly on current code |
| Execution tables | `test_executions` supports `single/scenario/suite` in active `base.py` | Similar in backup | Storage exists, scenario producer/executor missing |

## Detailed Gaps

## 1) Active model does not define scenario entities
- `backend/app/db/base.py` defines:
  - `ApiDefinition`, `ApiCase`, `AsyncTask`, `TestExecution`, `TestExecutionResult`
- `backend/app/db/base.py` does **not** define:
  - `ApiScenario`, `ScenarioEndpoint`, `ApiDependency`

Impact:
- scenario CRUD/API cannot bind to ORM
- scenario-aware impact scanning is broken
- old scenario migration scripts that import these models are invalid

## 2) Sync change detector imports missing model from active base
- `backend/app/core/sync/change_detector.py` imports:
  - `ApiDefinition`, `ApiCase`, `ApiScenario`, `User` from `app.db.base`
- `ApiScenario` is absent in `base.py`

Impact:
- import-time failure or dead code path for impact scanner
- scenario impact result (`affected_scenarios`) cannot be trusted

## 3) Migration script is coupled to missing ORM classes
- `backend/migrations/add_scenario_tables.py` imports:
  - `ApiDependency`, `ApiScenario`, `ScenarioEndpoint` from `app.db.base`
- these classes are not in active model

Impact:
- migration task cannot be executed in current branch
- scenario table lineage is not reproducible

## 4) Execution layer advertises scenario capability but does not implement it
- `backend/app/core/test_execution.py`:
  - `ExecutionType.SCENARIO` exists
  - `ScenarioExecutor.execute_scenario(...)` raises `NotImplementedError`

Impact:
- scenario execution is a contract without implementation
- cannot close the "intent -> scenario -> run" loop

## 5) Table-level support exists for scenario records but no producer path
- `test_executions` allows `execution_type = scenario`
- active APIs only expose case-level execution routes (`api_cases.py`)

Impact:
- storage can hold scenario runs, but no route/service writes scenario records

## Root Causes
- Partial migration from an older "api integration/scenario" branch to current "api hub + case execution" branch.
- Scenario domain models were removed or never merged into active `base.py`, but references remained in other modules.
- Async and execution capabilities evolved independently without scenario backbone integration.

## Priority and Fix Order
1. Reintroduce scenario ORM entities in active `base.py` (or compatible V1 entities).
2. Add deterministic migration script that does not depend on missing classes.
3. Repair `change_detector` imports and scenario query contracts.
4. Implement `ScenarioExecutor` and scenario API routes.
5. Wire execution records and reports for scenario runs.

## Acceptance Criteria for Task 1
- A clear list of hard mismatches is documented.
- Every mismatch references real files and current behavior.
- Fix order is defined and actionable for Tasks 3-5+.

