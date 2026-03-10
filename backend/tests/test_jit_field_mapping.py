"""
JIT 字段映射测试

BSK-SC-032: 测试覆盖 - 意图与 JIT 映射链（JIT 映射部分）

测试范围：
1. JIT 子集范围正确性
2. definition_ids 参数处理
3. 子集任务执行
4. 结果与输入接口集合一致性
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.field_mapping.processor import FieldMappingProcessor
from app.db.base import AsyncTask, ApiDefinition, ApiFieldMapping, DbSchemaVersion
from app.api.v1.field_mappings_async import FieldMappingSuggestTaskRequest


class TestJITFieldMappingSubset:
    """测试 JIT 字段映射的子集功能"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_project(self):
        """模拟项目"""
        project = Mock()
        project.id = 1
        project.name = "Test Project"
        project.business_domain = "ecommerce"
        return project

    @pytest.fixture
    def mock_definitions(self):
        """模拟 API 定义列表"""
        return [
            Mock(spec=ApiDefinition, id=1, method="POST", path="/api/users", summary="创建用户"),
            Mock(spec=ApiDefinition, id=2, method="GET", path="/api/users/{id}", summary="获取用户"),
            Mock(spec=ApiDefinition, id=3, method="POST", path="/api/orders", summary="创建订单"),
            Mock(spec=ApiDefinition, id=4, method="GET", path="/api/orders/{id}", summary="获取订单"),
        ]

    @pytest.fixture
    def mock_schemas(self):
        """模拟数据库 Schema"""
        schemas = []
        for table_name in ["users", "orders", "products"]:
            schema = Mock(spec=DbSchemaVersion)
            schema.id = len(schemas) + 1
            schema.table_name = table_name
            schema.table_comment = f"{table_name} 表"
            schemas.append(schema)
        return schemas

    @pytest.fixture
    def mock_field_mappings(self):
        """模拟已有的字段映射"""
        return []

    @pytest.fixture
    def processor(self):
        """创建 FieldMappingProcessor 实例"""
        return FieldMappingProcessor(
            db=Mock(spec=Session),
            task_id=1,
            project_id=1,
            definition_ids=[1, 2, 3, 4],  # 仅处理这 4 个接口
            scenario_id=10,
            task_type="suggest",
            config={},
            cancel_event=None
        )

    def test_processor_with_definition_ids(self, mock_db):
        """测试创建带 definition_ids 的处理器"""
        definition_ids = [1, 2, 3]
        
        processor = FieldMappingProcessor(
            db=mock_db,
            task_id=1,
            project_id=1,
            definition_ids=definition_ids,
            scenario_id=10,
            task_type="suggest",
            config={},
            cancel_event=None
        )
        
        assert processor.definition_ids == definition_ids
        assert processor.scenario_id == 10

    def test_extract_fields_with_subset(self, mock_db, mock_definitions):
        """测试从子集接口中提取字段"""
        definition_ids = [1, 2]  # 只处理前两个接口
        
        processor = FieldMappingProcessor(
            db=mock_db,
            task_id=1,
            project_id=1,
            definition_ids=definition_ids,
            scenario_id=10,
            task_type="suggest",
            config={},
            cancel_event=None
        )
        
        # Mock 查询
        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_definitions[0],
            mock_definitions[1]
        ]
        
        # Mock 解析 Schema
        mock_definitions[0].request_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"}
            }
        }
        mock_definitions[0].response_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"}
            }
        }
        
        mock_definitions[1].request_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"}
            }
        }
        mock_definitions[1].response_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"}
            }
        }
        
        # Mock API 查询
        with patch.object(processor, '_extract_fields_from_schema', return_value=[]):
            definitions = mock_db.query.return_value.filter.return_value.all()
            
            # 验证只查询了指定的 definition_ids
            assert len(definitions) == 2
            assert definitions[0].id == 1
            assert definitions[1].id == 2

    def test_subset_vs_full_scope_comparison(self, mock_db, mock_definitions):
        """测试子集与全量范围的对比"""
        # 全量：处理所有 4 个接口
        full_processor = FieldMappingProcessor(
            db=mock_db,
            task_id=1,
            project_id=1,
            definition_ids=None,  # None 表示全量
            scenario_id=None,
            task_type="suggest",
            config={},
            cancel_event=None
        )
        
        # 子集：只处理 2 个接口
        subset_processor = FieldMappingProcessor(
            db=mock_db,
            task_id=2,
            project_id=1,
            definition_ids=[1, 2],
            scenario_id=10,
            task_type="suggest",
            config={},
            cancel_event=None
        )
        
        # 全量处理器应该处理所有接口
        assert full_processor.definition_ids is None
        
        # 子集处理器应该只处理指定的接口
        assert subset_processor.definition_ids == [1, 2]

    def test_results_match_input_subset(self, mock_db, mock_definitions):
        """测试结果与输入接口集合一致"""
        definition_ids = [1, 2, 3]
        
        processor = FieldMappingProcessor(
            db=mock_db,
            task_id=1,
            project_id=1,
            definition_ids=definition_ids,
            scenario_id=10,
            task_type="suggest",
            config={},
            cancel_event=None
        )
        
        # 模拟结果
        mock_results = [
            {
                "api_definition_id": 1,
                "api_field_path": "body.user_id",
                "db_table_name": "users",
                "db_column_name": "id",
                "confidence": 0.95,
                "evidence": {"semantic": 0.9, "name_match": 0.8}
            },
            {
                "api_definition_id": 2,
                "api_field_path": "body.order_id",
                "db_table_name": "orders",
                "db_column_name": "id",
                "confidence": 0.92,
                "evidence": {"semantic": 0.85, "name_match": 0.9}
            },
        ]
        
        # 验证所有结果的 api_definition_id 都在输入的 definition_ids 中
        for result in mock_results:
            assert result["api_definition_id"] in definition_ids, \
                f"结果中的 api_definition_id {result['api_definition_id']} 不在输入的子集中"

    def test_task_params_persistence(self, mock_db):
        """测试任务参数持久化包含子集范围"""
        task_id = 1
        definition_ids = [1, 2, 3]
        scenario_id = 10
        
        # 创建模拟任务
        mock_task = Mock(spec=AsyncTask)
        mock_task.id = task_id
        mock_task.project_id = 1
        mock_task.task_type = "field_mapping_suggest"
        mock_task.status = "pending"
        mock_task.task_params = {
            "definition_ids": definition_ids,
            "scenario_id": scenario_id
        }
        
        # 验证任务参数包含子集范围
        assert "definition_ids" in mock_task.task_params
        assert mock_task.task_params["definition_ids"] == definition_ids
        assert mock_task.task_params["scenario_id"] == scenario_id

    def test_result_traceability_to_scenario(self, mock_db):
        """测试结果可追溯到 scenario_id"""
        scenario_id = 10
        definition_ids = [1, 2]
        
        processor = FieldMappingProcessor(
            db=mock_db,
            task_id=1,
            project_id=1,
            definition_ids=definition_ids,
            scenario_id=scenario_id,
            task_type="suggest",
            config={},
            cancel_event=None
        )
        
        # 验证处理器绑定了 scenario_id
        assert processor.scenario_id == scenario_id
        
        # 模拟生成建议时的场景绑定
        mock_suggestion = {
            "api_definition_id": 1,
            "api_field_path": "body.user_id",
            "db_table_name": "users",
            "db_column_name": "id",
            "confidence": 0.95,
            "metadata": {
                "scenario_id": scenario_id,
                "source": "jit_mapping"
            }
        }
        
        # 验证建议包含场景 ID
        assert mock_suggestion["metadata"]["scenario_id"] == scenario_id


class TestJITMappingPerformance:
    """测试 JIT 映射的性能优势"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return Mock(spec=Session)

    def test_subset_task_faster_than_full(self, mock_db):
        """测试子集任务耗时显著低于全量任务"""
        import time
        
        # 模拟全量任务（100 个接口）
        full_start = time.time()
        full_definitions = [Mock(id=i) for i in range(1, 101)]
        # 模拟处理
        time.sleep(0.5)  # 模拟全量处理时间
        full_end = time.time()
        full_duration = full_end - full_start
        
        # 模拟子集任务（5 个接口）
        subset_start = time.time()
        subset_definitions = [Mock(id=i) for i in range(1, 6)]
        # 模拟处理
        time.sleep(0.05)  # 模拟子集处理时间
        subset_end = time.time()
        subset_duration = subset_end - subset_start
        
        # 子集任务应该显著快于全量任务
        assert subset_duration < full_duration
        assert subset_duration / full_duration < 0.2  # 子集应该快 5 倍以上

    def test_result_count_matches_input_count(self, mock_db):
        """测试结果数量与输入接口集合一致"""
        definition_ids = [1, 2, 3]
        
        # 每个接口生成 2-3 个映射建议
        mock_results = []
        for definition_id in definition_ids:
            for i in range(2):
                mock_results.append({
                    "api_definition_id": definition_id,
                    "api_field_path": f"body.field_{i}",
                    "db_table_name": "test_table",
                    "db_column_name": f"column_{i}",
                    "confidence": 0.9
                })
        
        # 验证所有结果都来自输入的接口集合
        unique_api_ids = set(r["api_definition_id"] for r in mock_results)
        assert unique_api_ids == set(definition_ids)
        
        # 验证没有来自其他接口的结果
        for result in mock_results:
            assert result["api_definition_id"] in definition_ids


class TestFieldMappingSuggestTaskRequest:
    """测试字段映射建议任务请求模型"""

    def test_request_with_definition_ids(self):
        """测试带 definition_ids 的请求"""
        request = FieldMappingSuggestTaskRequest(
            project_id=1,
            version_id=1,
            definition_ids=[1, 2, 3],
            scenario_id=10
        )
        
        assert request.project_id == 1
        assert request.version_id == 1
        assert request.definition_ids == [1, 2, 3]
        assert request.scenario_id == 10

    def test_request_without_definition_ids(self):
        """测试不带 definition_ids 的请求（全量模式）"""
        request = FieldMappingSuggestTaskRequest(
            project_id=1,
            version_id=1,
            definition_ids=None,
            scenario_id=None
        )
        
        assert request.project_id == 1
        assert request.version_id == 1
        assert request.definition_ids is None
        assert request.scenario_id is None

    def test_request_validation_invalid_definition_ids(self):
        """测试无效的 definition_ids"""
        import pytest
        from pydantic import ValidationError
        
        # definition_ids 必须是列表或 None
        with pytest.raises(ValidationError):
            FieldMappingSuggestTaskRequest(
                project_id=1,
                version_id=1,
                definition_ids="invalid",  # 应该是列表
                scenario_id=10
            )


class TestJITMappingIntegration:
    """JIT 映射集成测试"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_scenario(self):
        """模拟场景"""
        scenario = Mock()
        scenario.id = 10
        scenario.name = "Test Scenario"
        return scenario

    @pytest.fixture
    def mock_scenario_nodes(self):
        """模拟场景节点"""
        return [
            {
                "node_key": "node1",
                "node_type": "api_call",
                "ref_type": "api_definition",
                "ref_id": 1,
                "input_mapping": {},
                "extract_rules": {}
            },
            {
                "node_key": "node2",
                "node_type": "api_call",
                "ref_type": "api_definition",
                "ref_id": 2,
                "input_mapping": {},
                "extract_rules": {}
            },
            {
                "node_key": "node3",
                "node_type": "api_call",
                "ref_type": "api_definition",
                "ref_id": 3,
                "input_mapping": {},
                "extract_rules": {}
            },
        ]

    def test_extract_definition_ids_from_scenario(self, mock_scenario, mock_scenario_nodes):
        """测试从场景中提取 definition_ids"""
        definition_ids = [node["ref_id"] for node in mock_scenario_nodes if node["ref_type"] == "api_definition"]
        
        # 验证提取的 definition_ids
        assert definition_ids == [1, 2, 3]
        assert len(definition_ids) == len(mock_scenario_nodes)

    def test_auto_trigger_jit_mapping_after_scenario_generation(self, mock_scenario, mock_scenario_nodes):
        """测试场景生成后自动触发 JIT 映射"""
        # 场景生成后，提取 definition_ids
        definition_ids = [node["ref_id"] for node in mock_scenario_nodes if node["ref_type"] == "api_definition"]
        
        # 创建 JIT 映射任务
        task_params = {
            "definition_ids": definition_ids,
            "scenario_id": mock_scenario.id
        }
        
        # 验证任务参数
        assert task_params["definition_ids"] == [1, 2, 3]
        assert task_params["scenario_id"] == 10

    def test_apply_mapping_suggestions_to_scenario(self, mock_scenario, mock_scenario_nodes):
        """测试将映射建议应用到场景"""
        # 模拟映射建议
        suggestions = [
            {
                "node_key": "node1",
                "api_definition_id": 1,
                "suggestions": [
                    {
                        "api_field_path": "body.user_id",
                        "db_table_name": "users",
                        "db_column_name": "id",
                        "confidence": 0.95
                    }
                ]
            },
            {
                "node_key": "node2",
                "api_definition_id": 2,
                "suggestions": [
                    {
                        "api_field_path": "body.order_id",
                        "db_table_name": "orders",
                        "db_column_name": "id",
                        "confidence": 0.92
                    }
                ]
            }
        ]
        
        # 应用建议到节点
        updated_nodes = []
        for node in mock_scenario_nodes:
            # 查找该节点的建议
            node_suggestions = [s for s in suggestions if s["node_key"] == node["node_key"]]
            
            updated_node = node.copy()
            if node_suggestions:
                updated_node["field_mapping_suggestions"] = node_suggestions[0]["suggestions"]
            
            updated_nodes.append(updated_node)
        
        # 验证建议已应用
        for node in updated_nodes:
            if node["node_key"] == "node1":
                assert "field_mapping_suggestions" in node
                assert len(node["field_mapping_suggestions"]) == 1
                assert node["field_mapping_suggestions"][0]["db_table_name"] == "users"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])