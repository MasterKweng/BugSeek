# Context Bus Spec (Task 10)

## Goal
Define a stable read/write contract for scenario runtime variables so downstream nodes can consume upstream outputs in DAG execution.

## Runtime Object
Context is a JSON-compatible object initialized at scenario start:

```json
{
  "vars": {},
  "node": {}
}
```

Initialization sources:
1. `scenario.context_init` (if object)
2. request-level `variables`
3. system defaults: `vars`, `node`

## Write Rules
After each node execution, `extracted_variables` is merged by `_merge_context`:

1. Node namespace write:
- `context.node.<node_key> = extracted_variables`

2. Global variable bucket write:
- for each key/value in `extracted_variables`:
- `context.vars.<key> = value`

3. Top-level scalar compatibility write:
- if value is scalar (`str/int/float/bool`)
- `context.<key> = value`

## Collision Policy
Variable overwrite is deterministic and last-writer-wins:

1. `context.node.<node_key>`: replaced by same node re-run output
2. `context.vars.<key>`: overwritten by latest completed node in execution order
3. `context.<key>` scalar alias: overwritten together with `context.vars.<key>`

Recommended usage for deterministic reads:
1. prefer `node.<node_key>.<var>` for strict source pinning
2. use `vars.<var>` only when latest value semantics are expected

## Read Rules
Template rendering supports dotted paths:

- syntax: `{{ path.to.value }}`
- resolver: `_get_context_value(context, key_path)`
- unresolved keys remain unchanged in payload (no hard failure at render stage)

Examples:
- `{{vars.order_id}}`
- `{{node.create_order.order_id}}`
- `{{token}}` (top-level scalar alias)

## Execution Integration
Per-node input processing:
1. read `node.input_mapping`
2. render templates with current context snapshot
3. flatten scalar variables from context (`_extract_flat_variables`)
4. merge rendered mapping into execution variable map
5. execute case

Level execution model:
1. level-wise snapshot is used to avoid intra-level read races
2. extracted outputs are merged after node completion
3. next level observes merged context

## Non-Goals (V1)
1. no type coercion policy beyond string rendering
2. no conflict lock/transaction semantics for intra-level same-key writes
3. no expression engine (only path lookup)

## Acceptance Checklist
1. Downstream node can read upstream variable via `{{node.<node_key>.<var>}}`
2. Downstream node can read latest alias via `{{vars.<var>}}`
3. Variable key collision has deterministic overwrite behavior
4. Unresolved placeholders do not crash execution
5. Context object is returned with execution result for troubleshooting
