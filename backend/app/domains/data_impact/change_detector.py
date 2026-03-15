"""Change detection utilities for snapshots."""
from typing import Any, Dict, List, Tuple


def _build_index(rows: List[Dict[str, Any]]) -> Tuple[Dict[Any, Dict[str, Any]], List[Dict[str, Any]]]:
    index = {}
    no_id_rows = []
    for row in rows:
        if "id" in row:
            index[row["id"]] = row
        else:
            no_id_rows.append(row)
    return index, no_id_rows


def diff_rows(before_rows: List[Dict[str, Any]], after_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return field-level changes between snapshots."""
    changes: List[Dict[str, Any]] = []

    before_index, before_no_id = _build_index(before_rows)
    after_index, after_no_id = _build_index(after_rows)

    for row_id, before_row in before_index.items():
        after_row = after_index.get(row_id)
        if after_row is None:
            for key, old_value in before_row.items():
                changes.append(
                    {
                        "field_name": key,
                        "old_value": old_value,
                        "new_value": None,
                        "change_type": "DELETED",
                        "row_id": row_id,
                    }
                )
            continue

        for key in set(before_row.keys()).union(after_row.keys()):
            old_value = before_row.get(key)
            new_value = after_row.get(key)
            if old_value != new_value:
                changes.append(
                    {
                        "field_name": key,
                        "old_value": old_value,
                        "new_value": new_value,
                        "change_type": "UPDATED",
                        "row_id": row_id,
                    }
                )

    for row_id, after_row in after_index.items():
        if row_id in before_index:
            continue
        for key, new_value in after_row.items():
            changes.append(
                {
                    "field_name": key,
                    "old_value": None,
                    "new_value": new_value,
                    "change_type": "CREATED",
                    "row_id": row_id,
                }
            )

    for after_row in after_no_id:
        if after_row not in before_no_id:
            for key, new_value in after_row.items():
                changes.append(
                    {
                        "field_name": key,
                        "old_value": None,
                        "new_value": new_value,
                        "change_type": "CREATED",
                    }
                )

    for before_row in before_no_id:
        if before_row not in after_no_id:
            for key, old_value in before_row.items():
                changes.append(
                    {
                        "field_name": key,
                        "old_value": old_value,
                        "new_value": None,
                        "change_type": "DELETED",
                    }
                )

    return changes
