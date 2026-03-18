# Infrastructure Operations

## Scope
- Redis-backed auth cache
- PDF report generation
- Artifact storage configuration for reports, attachments, and graph exports

## Redis Auth Cache
- `REDIS_URL`: Redis connection string.
- `AUTH_CACHE_TTL_SECONDS`: cache TTL for auth variables.
- Runtime behavior:
  - Primary path writes and reads auth variables from Redis hash key `auth_vars:{project_id}`.
  - If Redis is unavailable, the service falls back to in-memory cache for the current process.

## PDF Reports
- Primary renderer: Playwright HTML-to-PDF.
- Fallback renderer: built-in text PDF generator, used when browser runtime is unavailable.
- Entry points:
  - `GET /api/v1/scenarios/{scenario_id}/executions/{execution_id}/report?format=html`
  - `GET /api/v1/scenarios/{scenario_id}/executions/{execution_id}/report?format=pdf`

## Artifact Storage
Current phase ships configuration and operational guidance first.
Default runtime still uses local storage.

Recommended env vars:
- `OBJECT_STORAGE_ENABLED`
- `OBJECT_STORAGE_PROVIDER`
- `OBJECT_STORAGE_ENDPOINT`
- `OBJECT_STORAGE_BUCKET`
- `OBJECT_STORAGE_REGION`
- `OBJECT_STORAGE_ACCESS_KEY`
- `OBJECT_STORAGE_SECRET_KEY`
- `OBJECT_STORAGE_REPORT_PREFIX`
- `OBJECT_STORAGE_ATTACHMENT_PREFIX`
- `OBJECT_STORAGE_GRAPH_EXPORT_PREFIX`
- `ARTIFACT_LOCAL_DIR`

## Rollout Notes
- Validate Redis connectivity before enabling long-lived auth cache usage.
- If Playwright browser binaries are missing, install them with `python -m playwright install chromium`.
- Object storage can remain disabled until report/attachment volume requires remote persistence.
