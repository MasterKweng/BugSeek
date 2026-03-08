# Scenario Migration Compatibility Strategy (Task 5)

## Goal
Define exactly what to keep, deprecate, and transform when moving from legacy scenario artifacts to Scenario V1.

## Scope
- Legacy references:
  - `api_scenarios` / `scenario_endpoints` in historical model (`base_backup.py`)
  - chain linkage artifacts (`api_chain_scenarios`, `api_internal_chains`, `api_module_chains`)
- New target:
  - `api_scenarios` (V1 fields)
  - `scenario_nodes`

## Compatibility Policy
1. Read compatibility: keep old data queryable during migration window.
2. Write compatibility: new writes go only to V1 structures.
3. Controlled deprecation: old table usage is phased out, not hard deleted on day one.

## Mapping Matrix

| Legacy Structure | V1 Target | Strategy |
|---|---|---|
| `api_scenarios.name` | `api_scenarios.name` | direct copy |
| `api_scenarios.description` | `api_scenarios.description` | direct copy |
| `api_scenarios.scenario_type` | `api_scenarios.scenario_type` | direct copy (default fallback) |
| `api_scenarios.source_type` | `api_scenarios.source_type` | direct copy |
| `api_scenarios.source_module_chain_id` | `api_scenarios.source_ref_id` | transform + keep `source_type=module_chain` |
| `api_scenarios.variables` | `api_scenarios.context_init` | semantic rename |
| `api_scenarios.timeout` | `api_scenarios.timeout_seconds` | unit-preserving copy |
| `api_scenarios.execution_order` | `scenario_nodes.*` | explode each step to one node |
| `scenario_endpoints(step_order, endpoint_id)` | `scenario_nodes(step_order, ref_id)` | direct projection (with `ref_type` rule) |
| `execution_order.depends_on` | `scenario_nodes.depends_on` | direct copy |
| `execution_order.extract` | `scenario_nodes.extract_rules` | direct copy |
| `execution_order.variables` | `scenario_nodes.input_mapping` | direct copy |

## Keep / Deprecate Decision

## Keep (for transition period)
- `api_chain_scenarios`
- `api_internal_chains`
- `api_module_chains`
- old scenario metadata fields still needed for historical read

## Deprecate (after cutover)
- direct writes to `scenario_endpoints`
- business logic that relies on old `execution_order` as execution source of truth

## Data Backfill Plan
1. Backfill source:
   - legacy `api_scenarios` rows (if existing in target DB)
2. For each scenario:
   - create/merge V1 scenario header
   - generate `scenario_nodes` from:
     - `execution_order` if present (preferred)
     - else `scenario_endpoints` ordered by `step_order`
3. Assign deterministic `node_key`:
   - format: `n_{step_order}_{ref_id}`
4. Populate dependency:
   - from legacy `depends_on`
   - if missing and step_order > 1, default to previous step for serial fallback

## Cutover Phases

## Phase 1: Dual Read / Single Write
- New APIs write only V1 (`api_scenarios + scenario_nodes`)
- Read APIs support:
  - V1 first
  - fallback adapter for legacy structures

## Phase 2: Dual Read / Legacy Write Disabled
- Block all legacy write routes and scripts
- Keep fallback reads for rollback safety

## Phase 3: V1 Only
- Remove fallback adapters
- Archive or drop deprecated table paths in a separate migration window

## Validation Checklist
1. Count validation:
   - migrated scenario count equals source count
2. Node coverage:
   - each migrated scenario has at least one node
3. Order validation:
   - `step_order` monotonic per scenario
4. Dependency validation:
   - all `depends_on` keys resolve inside same scenario
5. Execution dry-run:
   - sample scenarios pass DAG validation

## Rollback Strategy
1. Keep legacy rows untouched during migration.
2. Migration script should be idempotent and re-runnable.
3. On rollback:
   - disable V1 writer routes
   - keep legacy read/write routes active
   - V1 tables can remain for diagnosis or be dropped in controlled rollback

## Acceptance Criteria for Task 5
- Clear field-level mapping from legacy to V1.
- Clear phased cutover and rollback plan.
- Validation checklist is complete and executable by QA/DBA.

