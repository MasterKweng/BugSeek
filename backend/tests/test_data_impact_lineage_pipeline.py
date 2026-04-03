from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from app.domains.data_impact.engine import DataImpactEngine
from app.domains.data_impact.impact_analyzer import ImpactAnalyzer
from app.domains.data_impact.code_analysis_pipeline import (
    CodeAnalysisPipeline,
    JavaAstCodeAnalyzer,
    PythonAstCodeAnalyzer,
)
from app.domains.data_impact.code_analysis.java_ir import JavaAssignmentFact
from app.domains.data_impact.code_analysis.java_adapter_registry import JavaAdapterRegistry
from app.domains.data_impact.code_recall.file_recaller import RuleBasedFileRecaller
from app.domains.data_impact.code_recall.recall_models import FileRecallCandidate
from app.domains.data_impact.lineage_service import LineageService
from app.domains.data_impact.repository_workspace import RepositoryWorkspaceService


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


def test_lineage_service_falls_back_to_workspace_scan_when_recall_is_empty(tmp_path: Path):
    service = LineageService(db=None)
    code_file = tmp_path / "UserAssembler.java"
    code_file.write_text(
        """
        dto.setUserName(user.name);
        """,
        encoding="utf-8",
    )
    definition = SimpleNamespace(
        id=12,
        project_id=13,
        response_schema={"type": "object", "properties": {"userName": {"type": "string"}}},
    )
    service.file_recaller.recall_files = lambda **kwargs: SimpleNamespace(candidates=[], used_fallback_scan=True)
    saved = []
    service.repo.save_lineage_edges = lambda **kwargs: saved.append(kwargs) or len(kwargs["edges"])

    created = service.build_and_persist_code_lineage_from_workspace(
        workspace_root=str(tmp_path),
        definition=definition,
    )

    assert created == 1
    assert saved[0]["api_field_path"] == "body.userName"


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


def test_repository_workspace_service_uses_existing_configured_workspace(tmp_path: Path):
    service = RepositoryWorkspaceService(db=None)
    workspace = tmp_path / "repo"
    workspace.mkdir()

    result = service.prepare_workspace(
        project_id=1,
        repository_config={
            "repo_url": "https://github.com/acme/demo.git",
            "default_branch": "main",
            "workspace_root": str(workspace),
        },
    )

    assert result["workspace_root"] == str(workspace)
    assert result["source"] == "configured_workspace"


def test_repository_workspace_service_clones_managed_workspace_when_configured_path_missing(tmp_path: Path):
    service = RepositoryWorkspaceService(db=None)

    def fake_root(*, project_id: int, repo_url: str) -> Path:
        assert project_id == 7
        assert repo_url == "https://github.com/acme/demo.git"
        return tmp_path / "managed" / "demo"

    calls = []

    def fake_run_git(command: list[str], *, cwd: Path) -> None:
        calls.append((command, cwd))
        if command[:2] == ["git", "clone"]:
            target = Path(command[-1])
            (target / ".git").mkdir(parents=True, exist_ok=True)

    service._managed_workspace_root = fake_root
    service._run_git = fake_run_git

    result = service.prepare_workspace(
        project_id=7,
        repository_config={
            "repo_url": "https://github.com/acme/demo.git",
            "default_branch": "main",
            "workspace_root": str(tmp_path / "missing"),
        },
    )

    assert result["workspace_root"] == str(tmp_path / "managed" / "demo")
    assert result["source"] == "managed_workspace_clone"
    assert calls[0][0][:4] == ["git", "clone", "--branch", "main"]


def test_rule_based_file_recaller_prioritizes_matching_files(tmp_path: Path):
    controller = tmp_path / "users" / "UserController.java"
    controller.parent.mkdir(parents=True, exist_ok=True)
    controller.write_text("class UserController {}", encoding="utf-8")
    mapper = tmp_path / "users" / "UserMapper.xml"
    mapper.write_text("<mapper />", encoding="utf-8")
    unrelated = tmp_path / "billing" / "InvoiceService.java"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_text("class InvoiceService {}", encoding="utf-8")
    definition = SimpleNamespace(
        path="/api/users/profile",
        method="GET",
        name="GetUserProfile",
        response_schema={
            "type": "object",
            "properties": {
                "userName": {"type": "string"},
                "statusText": {"type": "string"},
            },
        },
    )

    recaller = RuleBasedFileRecaller()
    result = recaller.recall_files(
        workspace_root=str(tmp_path),
        definition=definition,
        response_field_paths=["body.userName", "body.statusText"],
        max_candidates=5,
    )

    assert result.used_fallback_scan is False
    assert result.candidates
    assert result.candidates[0].path in {str(controller), str(mapper)}
    assert all(candidate.path != str(unrelated) or candidate.score < result.candidates[0].score for candidate in result.candidates)


def test_rule_based_file_recaller_uses_lightweight_content_hits(tmp_path: Path):
    content_hit = tmp_path / "misc" / "Assembler.java"
    content_hit.parent.mkdir(parents=True, exist_ok=True)
    content_hit.write_text(
        """
package misc;
public class Assembler {
    public void buildProfile(UserDto dto, User user) {
        dto.setUserName(user.getName());
        dto.setStatusText(user.getStatus());
    }
}
""",
        encoding="utf-8",
    )
    weak_path = tmp_path / "misc" / "RandomThing.java"
    weak_path.write_text("class RandomThing {}", encoding="utf-8")
    definition = SimpleNamespace(
        path="/api/profile",
        method="GET",
        name="GetUserProfile",
        response_schema={
            "type": "object",
            "properties": {
                "userName": {"type": "string"},
                "statusText": {"type": "string"},
            },
        },
    )

    recaller = RuleBasedFileRecaller()
    result = recaller.recall_files(
        workspace_root=str(tmp_path),
        definition=definition,
        response_field_paths=["body.userName", "body.statusText"],
        max_candidates=5,
    )

    assert result.candidates
    assert result.candidates[0].path == str(content_hit)
    assert any(reason.startswith("content:") for reason in result.candidates[0].reasons)


def test_lineage_service_summarizes_recall_candidates():
    service = LineageService(db=None)

    summary = service._summarize_recall_candidates(
        [
            FileRecallCandidate(
                path="D:/repo/users/UserController.java",
                score=4.236,
                reasons=["path:user", "name:profile", "role:+1.4"],
            )
        ]
    )

    assert summary == [
        {
            "path": "D:/repo/users/UserController.java",
            "score": 4.24,
            "reasons": ["path:user", "name:profile", "role:+1.4"],
        }
    ]


def test_python_ast_code_analyzer_extracts_assignment_edges():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
dto.user_name = user.name
dto.status_text = order.status
dto.set_code(project.code)
""",
        file_path="service.py",
    )

    assert {edge["api_field_path"] for edge in edges} == {"body.user_name", "body.status_text", "body.code"}
    assert any(edge["evidence_type"] == "code_assignment_ast" for edge in edges)


def test_python_ast_code_analyzer_tracks_intermediate_variables_and_wrappers():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
display_name = user.profile.name
dto.display_name = str(display_name)
""",
        file_path="service.py",
    )

    edge = next(edge for edge in edges if edge["api_field_path"] == "body.display_name")
    assert edge["source_chain"] == "user.profile.name"
    assert edge["intermediate_variable_hit"] is True
    assert edge["transform_hint"] == "str"


def test_python_ast_code_analyzer_extracts_dict_and_return_mappings():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
payload = {"user_name": user.name, "status_text": order.status}
result.update({"code": project.code})
return {"email": user.email}
""",
        file_path="serializer.py",
    )

    assert {edge["api_field_path"] for edge in edges} >= {"body.user_name", "body.status_text", "body.code", "body.email"}


def test_python_ast_code_analyzer_extracts_constructor_keyword_mappings():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
return UserDTO(user_name=user.name, status_text=order.status)
""",
        file_path="dto_builder.py",
    )

    assert {edge["api_field_path"] for edge in edges} == {"body.user_name", "body.status_text"}


def test_python_ast_code_analyzer_extracts_list_comprehension_mappings():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
dto.items = [item.code for item in order.items]
""",
        file_path="service.py",
    )

    edge = next(edge for edge in edges if edge["api_field_path"] == "body.items")
    assert edge["assignment_kind"] == "collection_map"
    assert edge["transform_hint"] == "list_comp"


def test_python_ast_code_analyzer_extracts_model_variable_return_edges():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
dto = UserDTO(user_name=user.name, status_text=order.status)
return dto
""",
        file_path="dto_builder.py",
    )

    assert {edge["api_field_path"] for edge in edges} == {"body.user_name", "body.status_text"}


def test_python_ast_code_analyzer_extracts_from_orm_and_model_dump_edges():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
dto = UserDTO.from_orm(user)
payload = dto.model_dump()
return payload
""",
        file_path="dto_builder.py",
    )

    wildcard = next(edge for edge in edges if edge["target_field"] == "*")
    assert wildcard["assignment_kind"] == "bean_copy"
    assert wildcard["transform_hint"] in {"from_orm", "model_dump"}


def test_python_ast_code_analyzer_extracts_asdict_edges():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
payload = asdict(user_dto)
return payload
""",
        file_path="dto_builder.py",
    )

    wildcard = next(edge for edge in edges if edge["target_field"] == "*")
    assert wildcard["transform_hint"] == "asdict"


def test_python_ast_code_analyzer_extracts_serializer_source_edges():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
class UserSerializer(serializers.Serializer):
    user_name = serializers.CharField(source="profile.name")
    status_text = serializers.CharField(source="status.label")
""",
        file_path="serializers.py",
    )

    assert {edge["api_field_path"] for edge in edges} == {"body.user_name", "body.status_text"}
    assert any(edge["transform_hint"] == "serializer_source" for edge in edges)


def test_python_ast_code_analyzer_extracts_serializer_method_field_edges():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
class UserSerializer(serializers.Serializer):
    status_text = serializers.SerializerMethodField()

    def get_status_text(self, obj):
        return obj.status.label
""",
        file_path="serializers.py",
    )

    edge = next(edge for edge in edges if edge["api_field_path"] == "body.status_text")
    assert edge["source_chain"] == "obj.status.label"
    assert edge["transform_hint"] == "serializer_method"


def test_python_ast_code_analyzer_extracts_sqlalchemy_row_and_model_edges():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
user = session.query(User).first()
row = result.mappings().first()
dto.name = user.name
dto.code = row["code"]
dto.status = row.get("status")
""",
        file_path="service.py",
    )

    by_path = {edge["api_field_path"]: edge for edge in edges}
    assert by_path["body.name"]["source_chain"] == "User.name"
    assert by_path["body.code"]["source_chain"] == "result.code"
    assert by_path["body.status"]["source_chain"] == "result.status"


def test_python_ast_code_analyzer_tracks_execute_statement_source_chain():
    analyzer = PythonAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
stmt = select(User)
result = session.execute(stmt)
user = result.scalar_one()
dto.name = user.name
rows = session.execute(stmt).mappings().first()
dto.code = rows["code"]
""",
        file_path="service.py",
    )

    by_path = {edge["api_field_path"]: edge for edge in edges}
    assert by_path["body.name"]["source_chain"] == "User.name"
    assert by_path["body.name"]["assignment_kind"] == "nested"
    assert by_path["body.code"]["source_chain"] == "User.code"


def test_lineage_service_uses_sql_lineage_to_backfill_code_edge_table(tmp_path: Path):
    service = LineageService(db=None)
    code_file = tmp_path / "user_service.py"
    code_file.write_text(
        """
row = result.mappings().first()
dto.user_name = row["name"]
""",
        encoding="utf-8",
    )
    saved = []
    service.repo.save_lineage_edges = lambda **kwargs: saved.append(kwargs) or len(kwargs["edges"])
    service.list_sql_lineage_candidates = lambda **kwargs: [
        {
            "source_table": "users",
            "source_column": "name",
            "projection_alias": "user_name",
        }
    ]
    definition = SimpleNamespace(
        id=41,
        project_id=42,
        response_schema={"type": "object", "properties": {"userName": {"type": "string"}}},
    )

    created = service.build_and_persist_code_lineage_from_workspace(
        workspace_root=str(tmp_path),
        definition=definition,
    )

    assert created == 1
    edge = saved[0]["edges"][0]
    assert edge["db_table"] == "users"
    assert edge["payload"]["sql_lineage_table_hints"] == ["users"]
    assert edge["payload"]["db_table_inferred_from"] == "sql_lineage"


def test_code_analysis_pipeline_prefers_python_ast_for_python_files():
    pipeline = CodeAnalysisPipeline()
    edges = pipeline.analyze(
        source_text="""
dto.user_name = user.name
""",
        file_path="handler.py",
    )

    assert len(edges) == 1
    assert edges[0]["evidence_type"] == "code_assignment_ast"


def test_java_ast_code_analyzer_extracts_assignment_edges():
    analyzer = JavaAstCodeAnalyzer()
    edges = analyzer.analyze(
        source_text="""
public class UserAssembler {
    public void fill(UserDto dto, User user) {
        dto.setUserName(user.getName());
        dto.statusText = user.status;
    }
}
""",
        file_path="UserAssembler.java",
    )

    assert {edge["api_field_path"] for edge in edges} == {"body.user_name", "body.statusText"}
    assert any(edge["evidence_type"] == "code_assignment_java_ast" for edge in edges)
    assert any(edge["payload"]["fact_kind"] == "setter" for edge in edges)
    assert any(edge["payload"]["analyzer"] == "java_javalang" for edge in edges)


def test_code_analysis_pipeline_enriches_java_builder_patterns():
    pipeline = CodeAnalysisPipeline()
    edges = pipeline.analyze(
        source_text="""
public class UserAssembler {
    public UserDto build(User user, Order order) {
        return UserDto.builder()
            .userName(user.getName())
            .statusText(order.getStatus())
            .build();
    }
}
""",
        file_path="UserAssembler.java",
    )

    assert any(edge["assignment_kind"] == "builder" for edge in edges)
    assert any(edge["target_field"] == "userName" for edge in edges)


def test_code_analysis_pipeline_enriches_java_bean_copy_patterns():
    pipeline = CodeAnalysisPipeline()
    edges = pipeline.analyze(
        source_text="""
public class UserAssembler {
    public void fill(UserDto dto, User user) {
        BeanUtils.copyProperties(user, dto, "ignoredField");
    }
}
""",
        file_path="UserAssembler.java",
    )

    assert any(edge["evidence_type"] == "bean_copy" for edge in edges)
    assert any(edge["assignment_kind"] == "bean_copy" for edge in edges)


def test_code_analysis_pipeline_reports_source_stats():
    pipeline = CodeAnalysisPipeline()
    result = pipeline.analyze_with_stats(
        source_text="""
public class UserAssembler {
    public UserDto build(User user, Order order) {
        BeanUtils.copyProperties(user, dto, "ignoredField");
        return UserDto.builder()
            .userName(user.getName())
            .statusText(order.getStatus())
            .build();
    }
}
""",
        file_path="UserAssembler.java",
    )

    stats = result["stats"]
    assert stats["edge_count"] == len(result["edges"])
    assert stats["primary_hit"] is False or isinstance(stats["primary_hit"], bool)
    assert "bean_copy_enricher" in stats["pipeline_sources"]
    assert "builder_enricher" in stats["pipeline_sources"]


def test_java_ast_code_analyzer_uses_adapter_contract():
    class _Adapter:
        adapter_name = "test_adapter"

        def parse_facts(self, *, source_text: str):
            assert "dto.setUserName" in source_text
            return [JavaAssignmentFact(target_ref="user_name", source_ref="user.name", adapter_name=self.adapter_name)]

        def to_lineage_edges(self, *, facts, default_api_prefix: str = "body"):
            assert len(facts) == 1
            return [
                {
                    "api_field_path": f"{default_api_prefix}.user_name",
                    "target_field": "user_name",
                    "target_object": "",
                    "target_chain": "user_name",
                    "source_field": "name",
                    "source_object": "user",
                    "source_chain": "user.name",
                    "db_table": None,
                    "db_column": "name",
                    "chain_depth": 2,
                    "assignment_kind": "nested",
                    "transform_hint": "",
                    "intermediate_variable_hit": False,
                    "evidence_type": "code_assignment_java_ast",
                    "confidence": 0.93,
                    "payload": {"analyzer": "test_adapter"},
                }
            ]

    analyzer = JavaAstCodeAnalyzer(adapter=_Adapter())
    edges = analyzer.analyze(
        source_text="dto.setUserName(user.getName());",
        file_path="UserAssembler.java",
    )

    assert edges[0]["api_field_path"] == "body.user_name"


def test_java_adapter_registry_picks_first_available_adapter():
    class _UnavailableAdapter:
        def is_available(self) -> bool:
            return False

    class _AvailableAdapter:
        def is_available(self) -> bool:
            return True

    registry = JavaAdapterRegistry(adapters=[_UnavailableAdapter(), _AvailableAdapter()])

    assert registry.resolve().__class__ is _AvailableAdapter


def test_java_adapter_registry_defaults_to_javalang_when_external_unavailable():
    registry = JavaAdapterRegistry()

    assert registry.resolve().__class__.__name__ == "JavalangJavaAdapter"


def test_java_adapter_registry_honors_preferred_adapter_name_when_available():
    class _AdapterA:
        adapter_name = "adapter_a"

        def is_available(self) -> bool:
            return True

    class _AdapterB:
        adapter_name = "adapter_b"

        def is_available(self) -> bool:
            return True

    registry = JavaAdapterRegistry(
        adapters=[_AdapterA(), _AdapterB()],
        preferred_adapter_name="adapter_b",
    )

    assert registry.resolve().__class__ is _AdapterB


def test_java_ast_code_analyzer_passes_preferred_adapter_name_to_registry():
    class _Adapter:
        adapter_name = "adapter_a"

        def parse_facts(self, *, source_text: str):
            return [JavaAssignmentFact(target_ref="user_name", source_ref="user.name", adapter_name=self.adapter_name)]

        def to_lineage_edges(self, *, facts, default_api_prefix: str = "body"):
            return [
                {
                    "api_field_path": f"{default_api_prefix}.user_name",
                    "target_field": "user_name",
                    "target_object": "",
                    "target_chain": "user_name",
                    "source_field": "name",
                    "source_object": "user",
                    "source_chain": "user.name",
                    "db_table": None,
                    "db_column": "name",
                    "chain_depth": 2,
                    "assignment_kind": "nested",
                    "transform_hint": "",
                    "intermediate_variable_hit": False,
                    "evidence_type": "code_assignment_java_ast",
                    "confidence": 0.93,
                    "payload": {"analyzer": "adapter_a"},
                }
            ]

    analyzer = JavaAstCodeAnalyzer(adapter=_Adapter(), preferred_adapter_name="adapter_a")
    edges = analyzer.analyze(source_text="dto.setUserName(user.getName());", file_path="UserAssembler.java")

    assert edges[0]["payload"]["analyzer"] == "adapter_a"
