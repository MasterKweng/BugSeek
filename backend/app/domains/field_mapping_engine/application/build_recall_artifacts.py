"""Step for assembling recall artifacts."""

from __future__ import annotations

from typing import Any, Dict, List


def run(
    service: Any,
    *,
    project_id: int,
    version_id: int,
    field_specs: List[Dict[str, Any]],
    use_sql_lineage: bool = True,
    use_code_lineage: bool = True,
    use_runtime_verification: bool = True,
) -> List[Dict[str, Any]]:
    schema_snapshot = service._load_db_schema(project_id, version_id)
    db_columns = service.db_extractor.extract_columns(schema_snapshot)
    history_prior_map = service.history_recaller.build_prior_map(project_id, version_id)
    rejected_prior_map = service.history_recaller.build_rejected_prior_map(project_id, version_id)

    items: List[Dict[str, Any]] = []
    for field_spec in field_specs:
        metadata = dict(field_spec.get("metadata") or {})
        field_context = service.context_builder.build_field_context(field_spec=field_spec)
        history_prior = service._resolve_history_prior(
            field_spec["field_path"],
            field_spec["field_name"],
            history_prior_map,
        )
        rejected_prior = service._resolve_history_prior(
            field_spec["field_path"],
            field_spec["field_name"],
            rejected_prior_map,
        )
        runtime_table_prior = (
            service.runtime_recaller.get_field_table_prior_map(
                int(field_spec["definition_id"]),
                field_spec["field_path"],
            )
            if use_runtime_verification
            else {}
        )
        lexical_candidates = service.lexical_recaller.recall_from_dict(
            field_spec,
            db_columns,
            history_prior,
            context=field_context,
        )
        lexical_candidates = service._apply_runtime_table_prior(lexical_candidates, runtime_table_prior)
        vector_candidates = service.vector_recaller.recall_from_dict(
            field_spec,
            schema_snapshot,
            context=field_context,
            allowed_tables=list(metadata.get("allowed_tables") or runtime_table_prior.keys()) or None,
        )
        vector_candidates = service.vector_recaller.attach_table_prior(vector_candidates, runtime_table_prior)
        runtime_candidates = (
            service.runtime_recaller.recall_from_dict(field_spec, schema_snapshot)
            if use_runtime_verification
            else []
        )
        sql_lineage_candidates = (
            service.sql_lineage_recaller.recall_from_dict(field_spec, schema_snapshot)
            if use_sql_lineage
            else []
        )
        code_lineage_candidates = (
            service.code_lineage_recaller.recall_from_dict(field_spec)
            if use_code_lineage
            else []
        )
        code_lineage_candidates = service._attach_weak_code_lineage_hints(
            code_lineage_candidates=code_lineage_candidates,
            candidate_groups=[lexical_candidates, vector_candidates, runtime_candidates, sql_lineage_candidates],
        )
        candidate_evidence = service._merge_candidate_evidence(
            lexical_candidates,
            vector_candidates,
            runtime_candidates,
            sql_lineage_candidates,
            code_lineage_candidates,
        )
        items.append(
            {
                "definition_id": field_spec["definition_id"],
                "definition_method": field_spec["method"],
                "definition_path": field_spec["path"],
                "api_field_path": field_spec["field_path"],
                "field_name": field_spec["field_name"],
                "source_type": field_spec.get("source_type"),
                "field_description": field_spec.get("description"),
                "sibling_paths": field_spec.get("sibling_paths", []),
                "field_metadata": metadata,
                "field_context": field_context,
                "risk_level": metadata.get("risk_level", "medium"),
                "domain_anchor": metadata.get("domain_anchor"),
                "allowed_tables": list(metadata.get("allowed_tables") or list(runtime_table_prior.keys())),
                "api_summary": metadata.get("api_summary"),
                "module_tag": metadata.get("module_tag"),
                "runtime_table_prior": runtime_table_prior,
                "rejected_history_prior": rejected_prior,
                "candidate_evidence": candidate_evidence,
            }
        )
    return items
