# Scenario Schema V1 (Task 3)

## Goal
Define the minimal but complete data model for:
- scenario storage
- DAG node orchestration
- context and mapping configuration

This schema is designed to coexist with existing `ApiCase` and `test_executions`.

## Design Principles
1. Do not break existing `ApiCase` execution flow.
2. Make scenario a first-class aggregate (`scenario + nodes`).
3. Support DAG execution without requiring a separate edge table (v1 stores dependencies in node JSON/list).
4. Keep migration reversible and low-risk.

## Entity 1: `api_scenarios`

## Purpose
Scenario aggregate root and runtime policy container.

## Proposed Columns
- `id` (PK, int)
- `project_id` (FK -> `projects.id`, required)
- `version_id` (FK -> `versions.id`, optional)
- `name` (varchar 255, required)
- `description` (text, optional)
- `scenario_type` (varchar 50, required, default `business_flow`)
- `source_type` (varchar 50, required, default `manual`)
- `source_ref_id` (int, optional; flexible reference for generator source)
- `environment_id` (FK -> `environments.id`, optional)
- `context_init` (JSON, optional; initial context object)
- `execution_mode` (varchar 20, required, default `sequential`)
- `timeout_seconds` (int, required, default `600`)
- `retry_count` (int, required, default `0`)
- `continue_on_failure` (bool, required, default `false`)
- `status` (varchar 20, required, default `draft`)
- `created_by` (FK -> `users.id`, optional)
- `updated_by` (FK -> `users.id`, optional)
- `created_at` (timestamp with timezone, required)
- `updated_at` (timestamp with timezone, required)

## Indexes
- `ix_api_scenarios_project_id(project_id)`
- `ix_api_scenarios_project_status(project_id, status)`
- `ix_api_scenarios_source_type(source_type)`
- `ix_api_scenarios_version_id(version_id)`
- `ix_api_scenarios_updated_at(updated_at)`

## Entity 2: `scenario_nodes`

## Purpose
Store executable nodes and DAG dependencies under one scenario.

## Proposed Columns
- `id` (PK, int)
- `scenario_id` (FK -> `api_scenarios.id` ON DELETE CASCADE, required)
- `node_key` (varchar 64, required; stable node identifier in scenario)
- `node_name` (varchar 255, optional)
- `node_type` (varchar 20, required, default `api_call`)
- `ref_type` (varchar 20, required, default `api_case`)
- `ref_id` (int, required; points to `api_cases.id` or `api_definitions.id` by `ref_type`)
- `step_order` (int, required, default `0`; deterministic UI ordering)
- `depends_on` (JSON, optional; list of upstream node keys)
- `input_mapping` (JSON, optional; runtime input mapping rules)
- `extract_rules` (JSON, optional; node-level extraction rules)
- `assertion_overrides` (JSON, optional; optional assertion override)
- `timeout_seconds` (int, optional; node-level override)
- `retry_count` (int, required, default `0`)
- `continue_on_failure` (bool, required, default `false`)
- `is_enabled` (bool, required, default `true`)
- `extra_config` (JSON, optional; extension point)
- `created_at` (timestamp with timezone, required)
- `updated_at` (timestamp with timezone, required)

## Constraints
- `uq_scenario_node_key(scenario_id, node_key)` unique

## Indexes
- `ix_scenario_nodes_scenario_id(scenario_id)`
- `ix_scenario_nodes_scenario_step(scenario_id, step_order)`
- `ix_scenario_nodes_ref_type_ref_id(ref_type, ref_id)`

## DAG Representation (V1)
- Node dependency is encoded by `depends_on` list.
- Executor builds graph in-memory and validates:
  - unknown dependency keys
  - cycles
  - disconnected nodes (policy-based: allow or reject)

## Execution Record Reuse
- Reuse existing `test_executions` and `test_execution_results`:
  - `execution_type = scenario`
  - `target_id = api_scenarios.id`
- Node-level detail can be carried in:
  - `test_execution_results` extension fields in later tasks, or
  - serialized result payload under scenario execution result record

## Status Enums (Recommended)
- Scenario status: `draft | active | archived`
- Execution mode: `sequential | dag`
- Node ref type: `api_case | api_definition`

## Context Bus Contract (Schema-Adjacent)
- `context_init` seeds runtime context.
- node extraction output is merged to context under:
  - `node.<node_key>.*` namespace
  - optional aliases from `input_mapping`

## Backward Compatibility Notes
- Keep old `scenario_endpoints` out of V1 active path.
- Do not bind V1 schema to legacy `api_endpoints` naming.
- Legacy chain/source relation is represented by `source_type + source_ref_id`.

## Acceptance Criteria for Task 3
- Schema is specific enough to implement migration directly.
- Supports manual and AI-generated scenarios.
- Supports both serial and DAG execution semantics.

