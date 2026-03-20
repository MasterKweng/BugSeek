# Phase 1 Cleanup Notes

## Completed Physical Deletions

- `backend/app/api/v1/field_mappings.py`
  - `_get_db_schema_for_project(...)`
  - `_generate_mapping_candidates_with_gravity(...)`
  - `_extract_api_fields(...)`
  - `_extract_field_descriptions(...)`
  - Removed from the controller after the legacy copies were fully moved to `backend/app/domains/data_mapping/legacy_support.py`.

## Remaining Non-Business Cleanup

- `backend/app/api/v1/field_mappings.py:1+`
  - Module header, core models, repeated query descriptions, route docstrings, main response messages, and scattered error strings have been normalized.
  - The file is now in a maintainable state; any remaining cleanup would be cosmetic only.

## Confirmed Mojibake / Broken Comment Locations

- `backend/app/celery/tasks/field_mapping_tasks.py:21`
  - Consistency warning log contains mojibake text.
- `backend/app/celery/tasks/field_mapping_tasks.py:43`
  - `task.error_message` message contains mojibake text.
- `backend/app/celery/tasks/field_mapping_tasks.py:44`
  - Error log for partial success contains mojibake text.
- `backend/app/celery/tasks/field_mapping_tasks.py:48-97`
  - Task docstring and multiple runtime logs/messages are mojibake.
- `backend/app/api/v1/field_mappings_async.py:1-80`
  - Module docstring, model docstrings, and field descriptions contain mojibake.
- `backend/app/api/v1/field_mappings_async.py:165-314`
  - Async task creation endpoint has mojibake in docstrings, logs, and error messages.
- `backend/app/api/v1/field_mappings_async.py:339-641`
  - Suggestions endpoint has mojibake in comments, docstrings, and response messages.
- `backend/app/api/v1/field_mappings_async.py:1310-1556`
  - Cancel/replay/stage-description legacy block contains mojibake.

## Notes

- A new `_calculate_stage_description(...)` override was appended at the end of `backend/app/api/v1/field_mappings_async.py` to restore correct engine_v2 behavior before the old mojibake block is cleaned.
- This file should be normalized in a later cleanup pass instead of stacking more duplicate helpers.
