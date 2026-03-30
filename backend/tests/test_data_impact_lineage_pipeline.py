from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from app.domains.data_impact.engine import DataImpactEngine
from app.domains.data_impact.impact_analyzer import ImpactAnalyzer
from app.domains.data_impact.lineage_service import LineageService


def test_lineage_service_builds_and_persists_sql_lineage_from_execution_trace():
    service = LineageService(db=None)
    service.repo.list_sql_traces = lambda execution_id: [
        SimpleNamespace(sql_text="SELECT u.name AS user_name FROM users u")
    ]
    saved = []

    def fake_save(**kwargs):
        saved.append(kwargs)
        return len(kwargs["edges"])

    service.repo.save_lineage_edges = fake_save
    definition = SimpleNamespace(
        id=1,
        project_id=2,
        response_schema={
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                }
            },
        },
    )

    created = service.build_and_persist_sql_lineage_for_execution(
        execution_id="exec-1",
        definition=definition,
    )

    assert created == 1
    assert saved[0]["definition_id"] == 1
    assert saved[0]["project_id"] == 2
    assert saved[0]["api_field_path"] == "body.user.name"
    assert saved[0]["evidence_type"] == "sql_lineage"
    assert saved[0]["edges"][0]["payload"]["execution_id"] == "exec-1"


def test_impact_analyzer_triggers_sql_lineage_persistence_during_analysis():
    definition = SimpleNamespace(id=3, project_id=4)

    class _QueryStub:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return definition

    class _DbStub:
        def query(self, *args, **kwargs):
            return _QueryStub()

    analyzer = ImpactAnalyzer(db=_DbStub())
    analyzer._get_latest_schema_snapshot = lambda api_id, definition=None: {}
    analyzer.repo.get_sql_traces = lambda execution_id: [
        SimpleNamespace(table_name="users", operation_type="SELECT")
    ]
    analyzer.snapshots.list_snapshots = lambda execution_id, table_name: []
    calls = []
    analyzer.lineage_service.build_and_persist_sql_lineage_for_execution = lambda **kwargs: calls.append(kwargs) or 0

    result = analyzer.analyze_execution("exec-1", api_id=3)

    assert result == {"tables": 0, "fields": 0}
    assert calls[0]["execution_id"] == "exec-1"
    assert calls[0]["definition"] is definition


def test_lineage_service_scans_workspace_and_persists_code_lineage(tmp_path: Path):
    service = LineageService(db=None)
    mapper_file = tmp_path / "UserMapper.xml"
    mapper_file.write_text(
        """
        <resultMap id="UserMap" type="UserVO">
            <result property="userName" column="user_name"/>
        </resultMap>
        <select id="queryUser">
            select u.user_name from users u
        </select>
        """,
        encoding="utf-8",
    )
    code_file = tmp_path / "UserAssembler.java"
    code_file.write_text(
        """
        dto.setUserName(user.name);
        dto.setStatusText(order.status);
        """,
        encoding="utf-8",
    )
    saved = []
    service.repo.save_lineage_edges = lambda **kwargs: saved.append(kwargs) or len(kwargs["edges"])
    definition = SimpleNamespace(
        id=10,
        project_id=11,
        response_schema={
            "type": "object",
            "properties": {
                "userName": {"type": "string"},
                "statusText": {"type": "string"},
            },
        },
    )

    created = service.build_and_persist_code_lineage_from_workspace(
        workspace_root=str(tmp_path),
        definition=definition,
    )

    assert created == 3
    assert {item["api_field_path"] for item in saved} == {"body.userName", "body.statusText"}
    assert any(edge["evidence_type"] == "orm_mapping" for item in saved for edge in item["edges"])
    assert any(edge["evidence_type"] == "code_assignment" for item in saved for edge in item["edges"])


def test_data_impact_engine_builds_lineage_assets_from_execution_and_workspace():
    definition = SimpleNamespace(id=21, project_id=22)

    class _QueryStub:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return definition

    class _DbStub:
        def query(self, *args, **kwargs):
            return _QueryStub()

    with patch.object(DataImpactEngine, "_ensure_tracer", lambda self: None):
        engine = DataImpactEngine(db=_DbStub(), engine=SimpleNamespace())
    engine.lineage_service.build_and_persist_sql_lineage_for_execution = lambda **kwargs: 2
    engine.lineage_service.build_and_persist_code_lineage_from_workspace = lambda **kwargs: 3

    result = engine.build_lineage_assets(
        definition_id=21,
        execution_id="exec-21",
        workspace_root="D:/workspace",
        version_id=7,
        max_files=50,
    )

    assert result["definition_id"] == 21
    assert result["sql_lineage_edges_created"] == 2
    assert result["code_lineage_edges_created"] == 3
