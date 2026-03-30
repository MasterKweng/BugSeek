from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.platform.db.base import Environment, TestExecution, TestExecutionResult, Version


def _apply_execution_filters(
    query,
    project_id: int,
    version_id: Optional[int] = None,
    environment_id: Optional[int] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
):
    query = query.filter(TestExecution.project_id == project_id)
    if version_id is not None:
        query = query.filter(TestExecution.version_id == version_id)
    if environment_id is not None:
        query = query.filter(TestExecution.environment_id == environment_id)
    if started_after:
        query = query.filter(TestExecution.started_at >= started_after)
    if started_before:
        query = query.filter(TestExecution.started_at <= started_before)
    return query


def _build_comparison_query(
    db: Session,
    project_id: int,
    join_model,
    join_condition,
    group_field,
    name_field,
    version_id: Optional[int] = None,
    environment_id: Optional[int] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
):
    query = (
        db.query(
            group_field.label("group_id"),
            name_field.label("group_name"),
            func.count(TestExecutionResult.id).label("total_results"),
            func.sum(case((TestExecutionResult.status == "passed", 1), else_=0)).label("passed_results"),
            func.sum(case((TestExecutionResult.status.in_(["failed", "error"]), 1), else_=0)).label("failed_results"),
            func.avg(TestExecutionResult.response_time).label("avg_response_time"),
        )
        .join(TestExecution, TestExecution.id == TestExecutionResult.execution_id)
        .join(join_model, join_condition)
    )
    query = _apply_execution_filters(
        query,
        project_id=project_id,
        version_id=version_id,
        environment_id=environment_id,
        started_after=started_after,
        started_before=started_before,
    )
    return query.group_by(group_field, name_field).order_by(func.count(TestExecutionResult.id).desc()).all()


def get_execution_report_summary_data(
    db: Session,
    project_id: int,
    version_id: Optional[int] = None,
    environment_id: Optional[int] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    execution_query = _apply_execution_filters(
        db.query(TestExecution),
        project_id=project_id,
        version_id=version_id,
        environment_id=environment_id,
        started_after=started_after,
        started_before=started_before,
    )
    total_executions = execution_query.count()
    result_query = _apply_execution_filters(
        db.query(TestExecutionResult).join(TestExecution, TestExecution.id == TestExecutionResult.execution_id),
        project_id=project_id,
        version_id=version_id,
        environment_id=environment_id,
        started_after=started_after,
        started_before=started_before,
    )
    aggregates = result_query.with_entities(
        func.count(TestExecutionResult.id),
        func.sum(case((TestExecutionResult.status == "passed", 1), else_=0)),
        func.sum(case((TestExecutionResult.status == "failed", 1), else_=0)),
        func.sum(case((TestExecutionResult.status == "error", 1), else_=0)),
        func.sum(case((TestExecutionResult.status == "skipped", 1), else_=0)),
        func.avg(TestExecutionResult.response_time),
    ).first()
    total_results = int(aggregates[0] or 0)
    passed_results = int(aggregates[1] or 0)
    failed_results = int(aggregates[2] or 0)
    error_results = int(aggregates[3] or 0)
    skipped_results = int(aggregates[4] or 0)
    avg_response_time = float(aggregates[5] or 0)
    return {
        "total_executions": total_executions,
        "total_results": total_results,
        "passed_results": passed_results,
        "failed_results": failed_results,
        "error_results": error_results,
        "skipped_results": skipped_results,
        "pass_rate": round((passed_results / total_results) * 100, 2) if total_results else 0.0,
        "fail_rate": round(((failed_results + error_results) / total_results) * 100, 2) if total_results else 0.0,
        "avg_response_time": round(avg_response_time, 2),
    }


def get_execution_report_trends_data(
    db: Session,
    project_id: int,
    group_by: str,
    version_id: Optional[int] = None,
    environment_id: Optional[int] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    base_query = _apply_execution_filters(
        db.query(
            func.date(TestExecution.started_at).label("bucket_date"),
            func.count(TestExecutionResult.id).label("total_results"),
            func.sum(case((TestExecutionResult.status == "passed", 1), else_=0)).label("passed_results"),
            func.sum(case((TestExecutionResult.status == "failed", 1), else_=0)).label("failed_results"),
            func.sum(case((TestExecutionResult.status == "error", 1), else_=0)).label("error_results"),
            func.avg(TestExecutionResult.response_time).label("avg_response_time"),
        ).join(TestExecutionResult, TestExecution.id == TestExecutionResult.execution_id),
        project_id=project_id,
        version_id=version_id,
        environment_id=environment_id,
        started_after=started_after,
        started_before=started_before,
    )
    daily_rows = base_query.group_by(func.date(TestExecution.started_at)).order_by(func.date(TestExecution.started_at).asc()).all()
    buckets: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "total_results": 0,
            "passed_results": 0,
            "failed_results": 0,
            "error_results": 0,
            "avg_response_time_sum": 0.0,
            "avg_response_time_count": 0,
        }
    )
    for row in daily_rows:
        bucket_date = row.bucket_date
        if group_by == "day":
            bucket_key = str(bucket_date)
        elif group_by == "week":
            bucket_key = f"{bucket_date.isocalendar().year}-W{bucket_date.isocalendar().week:02d}"
        else:
            bucket_key = bucket_date.strftime("%Y-%m")
        bucket = buckets[bucket_key]
        bucket["total_results"] += int(row.total_results or 0)
        bucket["passed_results"] += int(row.passed_results or 0)
        bucket["failed_results"] += int(row.failed_results or 0) + int(row.error_results or 0)
        bucket["error_results"] += int(row.error_results or 0)
        if row.avg_response_time is not None:
            bucket["avg_response_time_sum"] += float(row.avg_response_time)
            bucket["avg_response_time_count"] += 1
    items: List[Dict[str, Any]] = []
    for bucket_key in sorted(buckets.keys()):
        bucket = buckets[bucket_key]
        total_results = int(bucket["total_results"])
        passed_results = int(bucket["passed_results"])
        failed_results = int(bucket["failed_results"])
        avg_response_time = bucket["avg_response_time_sum"] / bucket["avg_response_time_count"] if bucket["avg_response_time_count"] else 0
        items.append(
            {
                "bucket": bucket_key,
                "total_results": total_results,
                "passed_results": passed_results,
                "failed_results": failed_results,
                "pass_rate": round((passed_results / total_results) * 100, 2) if total_results else 0.0,
                "avg_response_time": round(avg_response_time, 2),
            }
        )
    return {"group_by": group_by, "items": items}


def get_execution_report_failures_data(
    db: Session,
    project_id: int,
    version_id: Optional[int] = None,
    environment_id: Optional[int] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    base_query = _apply_execution_filters(
        db.query(TestExecutionResult).join(TestExecution, TestExecution.id == TestExecutionResult.execution_id),
        project_id=project_id,
        version_id=version_id,
        environment_id=environment_id,
        started_after=started_after,
        started_before=started_before,
    ).filter(TestExecutionResult.status.in_(["failed", "error"]))
    by_definition = (
        base_query.with_entities(
            TestExecutionResult.definition_id,
            TestExecutionResult.target_name,
            func.count(TestExecutionResult.id).label("failed_count"),
        )
        .group_by(TestExecutionResult.definition_id, TestExecutionResult.target_name)
        .order_by(func.count(TestExecutionResult.id).desc())
        .limit(10)
        .all()
    )
    by_case = (
        base_query.with_entities(
            TestExecutionResult.case_id,
            TestExecutionResult.target_name,
            func.count(TestExecutionResult.id).label("failed_count"),
        )
        .group_by(TestExecutionResult.case_id, TestExecutionResult.target_name)
        .order_by(func.count(TestExecutionResult.id).desc())
        .limit(10)
        .all()
    )
    by_status_code = (
        base_query.with_entities(
            TestExecutionResult.response_code,
            func.count(TestExecutionResult.id).label("count"),
        )
        .group_by(TestExecutionResult.response_code)
        .order_by(func.count(TestExecutionResult.id).desc())
        .limit(10)
        .all()
    )
    by_error_message = (
        base_query.with_entities(
            TestExecutionResult.error_message,
            func.count(TestExecutionResult.id).label("count"),
        )
        .filter(TestExecutionResult.error_message.isnot(None))
        .group_by(TestExecutionResult.error_message)
        .order_by(func.count(TestExecutionResult.id).desc())
        .limit(10)
        .all()
    )
    return {
        "by_definition": [
            {"definition_id": row.definition_id, "target_name": row.target_name, "failed_count": int(row.failed_count or 0)}
            for row in by_definition
        ],
        "by_case": [
            {"case_id": row.case_id, "target_name": row.target_name, "failed_count": int(row.failed_count or 0)}
            for row in by_case
        ],
        "by_status_code": [
            {"response_code": row.response_code, "count": int(row.count or 0)}
            for row in by_status_code
        ],
        "by_error_message": [
            {"error_message": row.error_message, "count": int(row.count or 0)}
            for row in by_error_message
        ],
    }


def get_execution_report_performance_data(
    db: Session,
    project_id: int,
    version_id: Optional[int] = None,
    environment_id: Optional[int] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    base_query = _apply_execution_filters(
        db.query(TestExecutionResult).join(TestExecution, TestExecution.id == TestExecutionResult.execution_id),
        project_id=project_id,
        version_id=version_id,
        environment_id=environment_id,
        started_after=started_after,
        started_before=started_before,
    )
    slowest_cases = (
        base_query.with_entities(
            TestExecutionResult.case_id,
            TestExecutionResult.target_name,
            func.avg(TestExecutionResult.response_time).label("avg_response_time"),
            func.max(TestExecutionResult.response_time).label("max_response_time"),
        )
        .filter(TestExecutionResult.case_id.isnot(None))
        .group_by(TestExecutionResult.case_id, TestExecutionResult.target_name)
        .order_by(func.avg(TestExecutionResult.response_time).desc())
        .limit(10)
        .all()
    )
    slowest_definitions = (
        base_query.with_entities(
            TestExecutionResult.definition_id,
            TestExecutionResult.target_name,
            func.avg(TestExecutionResult.response_time).label("avg_response_time"),
            func.max(TestExecutionResult.response_time).label("max_response_time"),
        )
        .filter(TestExecutionResult.definition_id.isnot(None))
        .group_by(TestExecutionResult.definition_id, TestExecutionResult.target_name)
        .order_by(func.avg(TestExecutionResult.response_time).desc())
        .limit(10)
        .all()
    )
    return {
        "slowest_cases": [
            {
                "case_id": row.case_id,
                "target_name": row.target_name,
                "avg_response_time": round(float(row.avg_response_time or 0), 2),
                "max_response_time": int(row.max_response_time or 0),
            }
            for row in slowest_cases
        ],
        "slowest_definitions": [
            {
                "definition_id": row.definition_id,
                "target_name": row.target_name,
                "avg_response_time": round(float(row.avg_response_time or 0), 2),
                "max_response_time": int(row.max_response_time or 0),
            }
            for row in slowest_definitions
        ],
    }


def get_execution_report_environment_comparison_data(
    db: Session,
    project_id: int,
    version_id: Optional[int] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    rows = _build_comparison_query(
        db=db,
        project_id=project_id,
        join_model=Environment,
        join_condition=Environment.id == TestExecution.environment_id,
        group_field=Environment.id,
        name_field=Environment.name,
        version_id=version_id,
        started_after=started_after,
        started_before=started_before,
    )
    return {
        "items": [
            {
                "environment_id": row.group_id,
                "environment_name": row.group_name,
                "total_results": int(row.total_results or 0),
                "pass_rate": round((int(row.passed_results or 0) / int(row.total_results or 1)) * 100, 2) if row.total_results else 0.0,
                "avg_response_time": round(float(row.avg_response_time or 0), 2),
            }
            for row in rows
        ]
    }


def get_execution_report_version_comparison_data(
    db: Session,
    project_id: int,
    environment_id: Optional[int] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    rows = _build_comparison_query(
        db=db,
        project_id=project_id,
        join_model=Version,
        join_condition=Version.id == TestExecution.version_id,
        group_field=Version.id,
        name_field=Version.version_number,
        environment_id=environment_id,
        started_after=started_after,
        started_before=started_before,
    )
    return {
        "items": [
            {
                "version_id": row.group_id,
                "version_number": row.group_name,
                "total_results": int(row.total_results or 0),
                "pass_rate": round((int(row.passed_results or 0) / int(row.total_results or 1)) * 100, 2) if row.total_results else 0.0,
                "avg_response_time": round(float(row.avg_response_time or 0), 2),
            }
            for row in rows
        ]
    }
