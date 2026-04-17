"""Initialize API definition modules from existing tags.

Default behavior is dry-run. Use --apply to persist changes.

Examples:
    python backend/scripts/init_api_modules_from_tags.py --project-id 1
    python backend/scripts/init_api_modules_from_tags.py --project-id 1 --apply
    python backend/scripts/init_api_modules_from_tags.py --project-id 1 --mapping-file backend/scripts/api_module_mapping.json --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.platform.db.base import ApiDefinition, ApiEndpointGroup
from app.platform.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize API modules from tags.")
    parser.add_argument("--project-id", type=int, required=True, help="Target project ID")
    parser.add_argument(
        "--mapping-file",
        type=str,
        default=None,
        help="Optional JSON file mapping tag -> module name",
    )
    parser.add_argument(
        "--fallback-module",
        type=str,
        default="ungrouped",
        help="Fallback module name for definitions without usable tags",
    )
    parser.add_argument(
        "--include-assigned",
        action="store_true",
        help="Also re-process definitions that already have a module assigned",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist module creation and assignment",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only inspect the first N definitions ordered by id",
    )
    return parser.parse_args()


def load_mapping(mapping_file: Optional[str]) -> Dict[str, str]:
    if not mapping_file:
        return {}

    path = Path(mapping_file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Mapping file must be a JSON object: {\"tag\": \"module\"}")

    mapping: Dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Mapping file keys and values must both be strings")
        tag = key.strip()
        module = value.strip()
        if tag and module:
            mapping[tag] = module
    return mapping


def normalize_module_name(name: str) -> str:
    return name.strip()


def get_primary_tag(tags: Any) -> Optional[str]:
    if not isinstance(tags, list):
        return None
    for item in tags:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def resolve_module_name(
    definition: ApiDefinition,
    mapping: Dict[str, str],
    fallback_module: str,
) -> str:
    primary_tag = get_primary_tag(definition.tags)
    if primary_tag and primary_tag in mapping:
        return normalize_module_name(mapping[primary_tag])
    if primary_tag:
        return normalize_module_name(primary_tag)
    return normalize_module_name(fallback_module)


def fetch_definitions(
    project_id: int,
    include_assigned: bool,
    limit: Optional[int],
) -> Iterable[ApiDefinition]:
    db = SessionLocal()
    try:
        query = db.query(ApiDefinition).filter(ApiDefinition.project_id == project_id).order_by(ApiDefinition.id.asc())
        if not include_assigned:
            query = query.filter(ApiDefinition.group_id.is_(None))
        if limit:
            query = query.limit(limit)
        return list(query.all())
    finally:
        db.close()


def print_plan(
    definitions: list[ApiDefinition],
    mapping: Dict[str, str],
    fallback_module: str,
) -> None:
    planned_modules = Counter()
    untagged = 0
    samples_by_module: dict[str, list[str]] = defaultdict(list)

    for definition in definitions:
        module_name = resolve_module_name(definition, mapping, fallback_module)
        planned_modules[module_name] += 1
        if get_primary_tag(definition.tags) is None:
            untagged += 1
        if len(samples_by_module[module_name]) < 3:
            samples_by_module[module_name].append(f"{definition.method} {definition.path}")

    print("=" * 72)
    print("API module initialization plan")
    print("=" * 72)
    print(f"Definitions to process: {len(definitions)}")
    print(f"Definitions without usable tags: {untagged}")
    print(f"Planned modules: {len(planned_modules)}")
    if mapping:
        print(f"Custom mapping entries: {len(mapping)}")
    print("-" * 72)
    for module_name, count in planned_modules.most_common():
        print(f"{module_name}: {count}")
        for sample in samples_by_module[module_name]:
            print(f"  - {sample}")
    print("=" * 72)


def apply_plan(
    project_id: int,
    definitions: list[ApiDefinition],
    mapping: Dict[str, str],
    fallback_module: str,
) -> None:
    db = SessionLocal()
    try:
        existing_modules = {
            module.name: module
            for module in db.query(ApiEndpointGroup)
            .filter(ApiEndpointGroup.project_id == project_id)
            .order_by(ApiEndpointGroup.sort_order.asc(), ApiEndpointGroup.id.asc())
            .all()
        }

        module_order = list(existing_modules.keys())
        assignments: list[tuple[int, str]] = []
        for definition in definitions:
            module_name = resolve_module_name(definition, mapping, fallback_module)
            if module_name not in existing_modules:
                new_module = ApiEndpointGroup(
                    project_id=project_id,
                    name=module_name,
                    description=f"{module_name} module",
                    sort_order=len(module_order),
                )
                db.add(new_module)
                db.flush()
                existing_modules[module_name] = new_module
                module_order.append(module_name)
            assignments.append((definition.id, module_name))

        updated_count = 0
        for definition_id, module_name in assignments:
            module = existing_modules[module_name]
            definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
            if definition is None:
                continue
            if definition.group_id != module.id:
                definition.group_id = module.id
                updated_count += 1

        db.commit()
        print(f"Created or reused modules: {len(existing_modules)}")
        print(f"Updated definitions: {updated_count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    args = parse_args()
    mapping = load_mapping(args.mapping_file)
    definitions = fetch_definitions(
        project_id=args.project_id,
        include_assigned=args.include_assigned,
        limit=args.limit,
    )

    if not definitions:
        print("No API definitions matched the selection.")
        return

    print_plan(definitions, mapping, args.fallback_module)

    if not args.apply:
        print("Dry-run only. Re-run with --apply to persist changes.")
        return

    apply_plan(
        project_id=args.project_id,
        definitions=definitions,
        mapping=mapping,
        fallback_module=args.fallback_module,
    )
    print("Module initialization completed.")


if __name__ == "__main__":
    main()
