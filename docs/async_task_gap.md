# Async Task Gap Analysis (Task 2)

## Goal
Identify concrete gaps in current async execution paths, then define a unification direction.

## Scope
- `backend/app/api/v1/sync_tasks.py`
- `backend/app/celery/tasks.py`
- `backend/app/api/v1/field_mappings_async.py`
- `backend/app/core/async_task/manager.py`
- `backend/app/core/async_task/executor.py`

## Current Async Paths

## Path A: Sync Task (document sync)
- Route: `POST /sync-tasks` in `sync_tasks.py`
- Behavior:
  - creates `SyncTask` row
  - imports `execute_sync_task` from `app.celery.tasks`
  - calls `.apply_async(...)`

Observed gap:
- `backend/app/celery/tasks.py` defines `execute_field_mapping_task`, but **does not define** `execute_sync_task`.

Risk:
- runtime import error when creating sync tasks
- feature appears available from API but cannot execute

## Path B: Field Mapping Async
- Route family in `field_mappings_async.py`
- Behavior:
  - creates `AsyncTask` row
  - dispatches Celery task `execute_field_mapping_task`
  - tracks status/progress/result in `AsyncTask`

Status:
- this path is functionally present and mostly self-consistent

## Path C: Local In-Process Queue
- `core/async_task/manager.py` implements:
  - in-memory `asyncio.Queue`
  - `start_worker()`, `submit_task()`, cancellation
- `core/async_task/executor.py` executes task types from queue

Observed gap:
- no confirmed startup hook wiring to run `start_worker()` as process lifecycle worker
- this path overlaps with Celery responsibilities

Risk:
- dual-task-system ambiguity (Celery + local queue)
- inconsistent state transitions depending on entry point

## Data Model Mismatch Notes
- `SyncTask` and `AsyncTask` are separate entities with different lifecycles.
- Field mapping uses `AsyncTask`; document sync uses `SyncTask`.
- No shared orchestration abstraction to enforce consistent status machine.

## Key Breakpoints
1. Missing Celery task symbol:
   - API expects `execute_sync_task`
   - tasks module exports no such function
2. Competing orchestration mechanisms:
   - Celery is production-ready path
   - local queue manager has no guaranteed process-level activation
3. Status contract drift:
   - `SyncTask` status flow and `AsyncTask` status flow are similar but not unified

## Recommended Direction
Use **Celery as the single execution backbone** for production routes.

Guidelines:
1. Every async API route dispatches Celery task only.
2. Local queue manager is either:
   - compatibility-only, explicitly marked non-production, or
   - removed after migration.
3. Standardize status contract:
   - `pending -> running -> completed/partial_success/failed/cancelled`

## Concrete Follow-up Work
1. Implement `execute_sync_task` in `backend/app/celery/tasks.py`.
2. Ensure `sync_tasks.py` and `field_mappings_async.py` use same status semantics where possible.
3. Add health/log checks that verify task registration at startup.
4. Decide and document lifecycle of `core/async_task/manager.py`.

## Acceptance Criteria for Task 2
- Missing symbol and broken call chain are explicitly documented.
- Dual-path orchestration risk is explicitly documented.
- A clear unification decision is recorded and actionable.

