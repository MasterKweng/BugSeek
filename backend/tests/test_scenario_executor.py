"""
场景执行主链测试

BSK-SC-031: 测试覆盖 - 场景执行主链

测试范围：
1. DAG 校验（无环、依赖合法、孤点校验）
2. Context 传递（变量从上游节点传递到下游节点）
3. 失败策略（fail_fast、continue_on_failure）
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio

from app.core.test_execution import ScenarioExecutor
from app.db.base import ApiScenario, ApiCase, TestExecution, Environment, Project


class TestScenarioExecutorDAGValidation:
    """测试 DAG 图校验功能"""

    @pytest.fixture
    def executor(self):
        """创建 ScenarioExecutor 实例"""
        return ScenarioExecutor()

    def test_validate_graph_success_serial(self, executor):
        """测试成功的串行图校验"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": ["node1"]},
            {"node_key": "node3", "depends_on": ["node2"]},
        ]
        
        # 不应该抛出异常
        executor._validate_graph(nodes)

    def test_validate_graph_success_parallel(self, executor):
        """测试成功的并行图校验"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": ["node1"]},
            {"node_key": "node3", "depends_on": ["node1"]},  # node2 和 node3 并行
        ]
        
        # 不应该抛出异常
        executor._validate_graph(nodes)

    def test_validate_graph_missing_node_key(self, executor):
        """测试缺少 node_key 的情况"""
        nodes = [
            {"depends_on": []},
            {"node_key": "node2", "depends_on": []},
        ]
        
        with pytest.raises(ValueError, match="Node key is required"):
            executor._validate_graph(nodes)

    def test_validate_graph_duplicate_node_key(self, executor):
        """测试重复的 node_key"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node1", "depends_on": []},
        ]
        
        with pytest.raises(ValueError, match="Duplicate node_key"):
            executor._validate_graph(nodes)

    def test_validate_graph_invalid_depends_on_type(self, executor):
        """测试 depends_on 不是列表的情况"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": "node1"},  # 应该是列表
        ]
        
        with pytest.raises(ValueError, match="depends_on must be list"):
            executor._validate_graph(nodes)

    def test_validate_graph_unknown_dependency(self, executor):
        """测试依赖了不存在的节点"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": ["nonexistent"]},
        ]
        
        with pytest.raises(ValueError, match="Unknown dependency"):
            executor._validate_graph(nodes)

    def test_validate_graph_self_dependency(self, executor):
        """测试自环情况"""
        nodes = [
            {"node_key": "node1", "depends_on": ["node1"]},
        ]
        
        with pytest.raises(ValueError, match="Self-dependency detected"):
            executor._validate_graph(nodes)

    def test_validate_graph_cycle_detection(self, executor):
        """测试环检测"""
        nodes = [
            {"node_key": "node1", "depends_on": ["node3"]},
            {"node_key": "node2", "depends_on": ["node1"]},
            {"node_key": "node3", "depends_on": ["node2"]},
        ]
        
        with pytest.raises(ValueError, match="Cycle detected"):
            executor._validate_graph(nodes)

    def test_validate_graph_complex_cycle(self, executor):
        """测试复杂的环检测"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": ["node1"]},
            {"node_key": "node3", "depends_on": ["node2"]},
            {"node_key": "node4", "depends_on": ["node3", "node1"]},
            {"node_key": "node5", "depends_on": ["node4"]},
            {"node_key": "node6", "depends_on": ["node5", "node2"]},
        ]
        
        # 不应该抛出异常（无环）
        executor._validate_graph(nodes)

    def test_validate_graph_isolated_nodes_warning(self, executor, caplog):
        """测试孤立节点的警告"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": ["node1"]},
            {"node_key": "isolated", "depends_on": []},  # 孤立节点
        ]
        
        with caplog.at_level("WARNING"):
            executor._validate_graph(nodes)
        
        # 检查是否发出了孤立节点警告
        assert any("isolated nodes" in record.message for record in caplog.records)


class TestScenarioExecutorExecutionLevels:
    """测试执行层级构建"""

    @pytest.fixture
    def executor(self):
        """创建 ScenarioExecutor 实例"""
        return ScenarioExecutor()

    def test_build_execution_levels_serial(self, executor):
        """测试串行执行层级"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": ["node1"]},
            {"node_key": "node3", "depends_on": ["node2"]},
        ]
        
        levels = executor._build_execution_levels(nodes)
        
        assert len(levels) == 3
        assert levels[0][0]["node_key"] == "node1"
        assert levels[1][0]["node_key"] == "node2"
        assert levels[2][0]["node_key"] == "node3"

    def test_build_execution_levels_parallel(self, executor):
        """测试并行执行层级"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": ["node1"]},
            {"node_key": "node3", "depends_on": ["node1"]},
        ]
        
        levels = executor._build_execution_levels(nodes)
        
        assert len(levels) == 2
        assert levels[0][0]["node_key"] == "node1"
        assert len(levels[1]) == 2  # 第二层有两个节点
        node_keys = [n["node_key"] for n in levels[1]]
        assert "node2" in node_keys
        assert "node3" in node_keys

    def test_build_execution_levels_complex(self, executor):
        """测试复杂的执行层级"""
        nodes = [
            {"node_key": "node1", "depends_on": []},
            {"node_key": "node2", "depends_on": ["node1"]},
            {"node_key": "node3", "depends_on": ["node1"]},
            {"node_key": "node4", "depends_on": ["node2", "node3"]},
        ]
        
        levels = executor._build_execution_levels(nodes)
        
        assert len(levels) == 3
        assert levels[0][0]["node_key"] == "node1"
        assert len(levels[1]) == 2
        assert len(levels[2]) == 1
        assert levels[2][0]["node_key"] == "node4"


class TestScenarioExecutorContextBus:
    """测试 Context Bus 变量传递"""

    @pytest.fixture
    def executor(self):
        """创建 ScenarioExecutor 实例"""
        return ScenarioExecutor()

    def test_merge_context_with_extraction(self, executor):
        """测试合并提取的变量到上下文"""
        context = {"vars": {}, "node": {}}
        node_key = "node1"
        extracted = {"user_id": "123", "token": "abc123"}
        
        executor._merge_context(context, node_key, extracted)
        
        # 检查全局变量
        assert context["vars"]["user_id"] == "123"
        assert context["vars"]["token"] == "abc123"
        
        # 检查节点级变量
        assert context["node"][node_key]["user_id"] == "123"
        assert context["node"][node_key]["token"] == "abc123"

    def test_merge_context_overwrite(self, executor):
        """测试变量覆盖"""
        context = {"vars": {"user_id": "old_value"}, "node": {}}
        node_key = "node1"
        extracted = {"user_id": "new_value"}
        
        executor._merge_context(context, node_key, extracted)
        
        # 应该覆盖旧值
        assert context["vars"]["user_id"] == "new_value"
        assert context["node"][node_key]["user_id"] == "new_value"

    def test_merge_context_multiple_nodes(self, executor):
        """测试多个节点的变量合并"""
        context = {"vars": {}, "node": {}}
        
        # 节点1提取变量
        executor._merge_context(context, "node1", {"user_id": "123"})
        
        # 节点2提取变量
        executor._merge_context(context, "node2", {"order_id": "456"})
        
        # 节点3也提取user_id（应该覆盖）
        executor._merge_context(context, "node3", {"user_id": "789"})
        
        # 检查全局变量
        assert context["vars"]["user_id"] == "789"  # 最后的值
        assert context["vars"]["order_id"] == "456"
        
        # 检查节点级变量（每个节点保留自己的值）
        assert context["node"]["node1"]["user_id"] == "123"
        assert context["node"]["node2"]["order_id"] == "456"
        assert context["node"]["node3"]["user_id"] == "789"


class TestScenarioExecutorFailureStrategy:
    """测试失败策略"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_scenario(self):
        """模拟场景对象"""
        scenario = Mock(spec=ApiScenario)
        scenario.id = 1
        scenario.name = "Test Scenario"
        scenario.context_init = {}
        scenario.continue_on_failure = False
        return scenario

    @pytest.fixture
    def executor(self):
        """创建 ScenarioExecutor 实例"""
        return ScenarioExecutor()

    @pytest.mark.asyncio
    async def test_execute_scenario_fail_fast(self, executor, mock_scenario, mock_db):
        """测试 fail_fast 策略（默认）"""
        # 模拟节点数据
        graph_data = {
            "nodes": [
                {"node_key": "node1", "depends_on": []},
                {"node_key": "node2", "depends_on": ["node1"]},
                {"node_key": "node3", "depends_on": ["node2"]},
            ]
        }
        
        # Mock 查询场景
        mock_db.query.return_value.filter.return_value.first.return_value = mock_scenario
        
        # Mock 单节点执行
        with patch.object(executor, '_execute_single_node', new_callable=AsyncMock) as mock_execute:
            # 第一个节点成功
            mock_execute.side_effect = [
                {
                    "node_key": "node1",
                    "status": "passed",
                    "extracted_variables": {"var1": "value1"},
                    "result": {"data": "success"}
                },
                # 第二个节点失败
                {
                    "node_key": "node2",
                    "status": "failed",
                    "error_message": "Test failure",
                    "result": None,
                    "extracted_variables": {}
                },
                # 第三个节点不应该执行（因为 fail_fast）
            ]
            
            # Mock 保存执行记录
            with patch.object(executor, '_save_scenario_execution_record') as mock_save:
                mock_save.return_value = 123
                
                result = await executor.execute_scenario(
                    scenario_id=1,
                    graph_data=graph_data,
                    variables={},
                    db=mock_db
                )
                
                # 验证只有前两个节点执行了
                assert mock_execute.call_count == 2
                
                # 验证执行结果
                assert result["status"] == "failed"
                assert result["passed_nodes"] == 1
                assert result["failed_nodes"] == 1

    @pytest.mark.asyncio
    async def test_execute_scenario_continue_on_failure(self, executor, mock_scenario, mock_db):
        """测试 continue_on_failure 策略"""
        # 设置场景允许失败后继续
        mock_scenario.continue_on_failure = True
        
        # 模拟节点数据
        graph_data = {
            "nodes": [
                {"node_key": "node1", "depends_on": []},
                {"node_key": "node2", "depends_on": ["node1"]},
                {"node_key": "node3", "depends_on": ["node2"]},
            ]
        }
        
        # Mock 查询场景
        mock_db.query.return_value.filter.return_value.first.return_value = mock_scenario
        
        # Mock 单节点执行
        with patch.object(executor, '_execute_single_node', new_callable=AsyncMock) as mock_execute:
            # 第一个节点成功
            mock_execute.side_effect = [
                {
                    "node_key": "node1",
                    "status": "passed",
                    "extracted_variables": {"var1": "value1"},
                    "result": {"data": "success"}
                },
                # 第二个节点失败
                {
                    "node_key": "node2",
                    "status": "failed",
                    "error_message": "Test failure",
                    "result": None,
                    "extracted_variables": {}
                },
                # 第三个节点应该执行（因为 continue_on_failure）
                {
                    "node_key": "node3",
                    "status": "passed",
                    "extracted_variables": {"var3": "value3"},
                    "result": {"data": "success"}
                },
            ]
            
            # Mock 保存执行记录
            with patch.object(executor, '_save_scenario_execution_record') as mock_save:
                mock_save.return_value = 123
                
                result = await executor.execute_scenario(
                    scenario_id=1,
                    graph_data=graph_data,
                    variables={},
                    db=mock_db
                )
                
                # 验证所有节点都执行了
                assert mock_execute.call_count == 3
                
                # 验证执行结果
                assert result["status"] == "failed"  # 有失败节点
                assert result["passed_nodes"] == 2
                assert result["failed_nodes"] == 1

    @pytest.mark.asyncio
    async def test_execute_scenario_node_continue_on_failure(self, executor, mock_scenario, mock_db):
        """测试节点级别的 continue_on_failure 策略"""
        # 模拟节点数据（node2 设置了 continue_on_failure）
        graph_data = {
            "nodes": [
                {"node_key": "node1", "depends_on": []},
                {"node_key": "node2", "depends_on": ["node1"], "continue_on_failure": True},
                {"node_key": "node3", "depends_on": ["node2"]},
            ]
        }
        
        # Mock 查询场景
        mock_db.query.return_value.filter.return_value.first.return_value = mock_scenario
        
        # Mock 单节点执行
        with patch.object(executor, '_execute_single_node', new_callable=AsyncMock) as mock_execute:
            # 第一个节点成功
            mock_execute.side_effect = [
                {
                    "node_key": "node1",
                    "status": "passed",
                    "extracted_variables": {"var1": "value1"},
                    "result": {"data": "success"}
                },
                # 第二个节点失败（但设置了 continue_on_failure）
                {
                    "node_key": "node2",
                    "status": "failed",
                    "error_message": "Test failure",
                    "result": None,
                    "extracted_variables": {}
                },
                # 第三个节点应该执行
                {
                    "node_key": "node3",
                    "status": "passed",
                    "extracted_variables": {"var3": "value3"},
                    "result": {"data": "success"}
                },
            ]
            
            # Mock 保存执行记录
            with patch.object(executor, '_save_scenario_execution_record') as mock_save:
                mock_save.return_value = 123
                
                result = await executor.execute_scenario(
                    scenario_id=1,
                    graph_data=graph_data,
                    variables={},
                    db=mock_db
                )
                
                # 验证所有节点都执行了
                assert mock_execute.call_count == 3
                
                # 验证执行结果
                assert result["status"] == "failed"
                assert result["passed_nodes"] == 2
                assert result["failed_nodes"] == 1


class TestScenarioExecutorIntegration:
    """集成测试：完整的场景执行流程"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_scenario(self):
        """模拟场景对象"""
        scenario = Mock(spec=ApiScenario)
        scenario.id = 1
        scenario.name = "Test Scenario"
        scenario.description = "Integration test scenario"
        scenario.project_id = 1
        scenario.version_id = 1
        scenario.context_init = {"global_var": "test_value"}
        scenario.continue_on_failure = False
        return scenario

    @pytest.fixture
    def executor(self):
        """创建 ScenarioExecutor 实例"""
        return ScenarioExecutor()

    @pytest.mark.asyncio
    async def test_full_scenario_execution_with_context_passing(self, executor, mock_scenario, mock_db):
        """测试完整的场景执行流程，包括变量传递"""
        # 模拟 3 节点链路：node1 提取变量 -> node2 使用变量 -> node3 断言
        graph_data = {
            "nodes": [
                {
                    "node_key": "create_user",
                    "depends_on": [],
                    "ref_id": 1,
                    "ref_type": "case",
                    "extract_rules": {
                        "user_id": "$.data.id"
                    }
                },
                {
                    "node_key": "get_user",
                    "depends_on": ["create_user"],
                    "ref_id": 2,
                    "ref_type": "case",
                    "input_mapping": {
                        "path_params": {
                            "id": "{{vars.user_id}}"
                        }
                    }
                },
                {
                    "node_key": "delete_user",
                    "depends_on": ["get_user"],
                    "ref_id": 3,
                    "ref_type": "case",
                    "input_mapping": {
                        "path_params": {
                            "id": "{{vars.user_id}}"
                        }
                    }
                },
            ]
        }
        
        # Mock 查询场景
        mock_db.query.return_value.filter.return_value.first.return_value = mock_scenario
        
        # Mock 单节点执行
        with patch.object(executor, '_execute_single_node', new_callable=AsyncMock) as mock_execute:
            # 模拟各节点的执行结果
            mock_execute.side_effect = [
                {
                    "node_key": "create_user",
                    "status": "passed",
                    "response_time": 100,
                    "response_code": 200,
                    "request_body": {"name": "test_user"},
                    "response_body": {"data": {"id": "12345"}},
                    "assertion_results": {"status_code": {"passed": True}},
                    "extracted_variables": {"user_id": "12345"},
                    "result": {"data": {"id": "12345"}}
                },
                {
                    "node_key": "get_user",
                    "status": "passed",
                    "response_time": 50,
                    "response_code": 200,
                    "request_body": {},
                    "response_body": {"data": {"id": "12345", "name": "test_user"}},
                    "assertion_results": {"status_code": {"passed": True}},
                    "extracted_variables": {},
                    "result": {"data": {"id": "12345", "name": "test_user"}}
                },
                {
                    "node_key": "delete_user",
                    "status": "passed",
                    "response_time": 80,
                    "response_code": 204,
                    "request_body": {},
                    "response_body": {},
                    "assertion_results": {"status_code": {"passed": True}},
                    "extracted_variables": {},
                    "result": {}
                },
            ]
            
            # Mock 保存执行记录
            with patch.object(executor, '_save_scenario_execution_record') as mock_save:
                mock_save.return_value = 123
                
                result = await executor.execute_scenario(
                    scenario_id=1,
                    graph_data=graph_data,
                    variables={},
                    db=mock_db
                )
                
                # 验证执行结果
                assert result["execution_id"] == 123
                assert result["status"] == "completed"
                assert result["total_nodes"] == 3
                assert result["passed_nodes"] == 3
                assert result["failed_nodes"] == 0
                assert result["total_duration_ms"] == 230  # 100 + 50 + 80
                
                # 验证所有节点都执行了
                assert mock_execute.call_count == 3
                
                # 验证变量传递
                calls = mock_execute.call_args_list
                # node2 应该接收到 user_id 变量
                node2_context = calls[1][1]["context"]
                assert "user_id" in node2_context["vars"]
                assert node2_context["vars"]["user_id"] == "12345"
                
                # node3 也应该接收到 user_id 变量
                node3_context = calls[2][1]["context"]
                assert "user_id" in node3_context["vars"]
                assert node3_context["vars"]["user_id"] == "12345"

    @pytest.mark.asyncio
    async def test_parallel_execution(self, executor, mock_scenario, mock_db):
        """测试并行执行"""
        # 模拟并行场景：node1 后，node2 和 node3 并行执行
        graph_data = {
            "nodes": [
                {
                    "node_key": "node1",
                    "depends_on": [],
                },
                {
                    "node_key": "node2",
                    "depends_on": ["node1"],
                },
                {
                    "node_key": "node3",
                    "depends_on": ["node1"],
                },
                {
                    "node_key": "node4",
                    "depends_on": ["node2", "node3"],
                },
            ]
        }
        
        # Mock 查询场景
        mock_db.query.return_value.filter.return_value.first.return_value = mock_scenario
        
        # Mock 单节点执行
        execution_times = []
        
        async def mock_execute_with_timing(*args, **kwargs):
            import time
            start = time.time()
            await asyncio.sleep(0.1)  # 模拟执行时间
            end = time.time()
            execution_times.append((kwargs["node"]["node_key"], end - start))
            
            return {
                "node_key": kwargs["node"]["node_key"],
                "status": "passed",
                "response_time": int((end - start) * 1000),
                "response_code": 200,
                "request_body": {},
                "response_body": {},
                "assertion_results": {},
                "extracted_variables": {},
                "result": {}
            }
        
        with patch.object(executor, '_execute_single_node', new_callable=AsyncMock, side_effect=mock_execute_with_timing):
            # Mock 保存执行记录
            with patch.object(executor, '_save_scenario_execution_record') as mock_save:
                mock_save.return_value = 123
                
                result = await executor.execute_scenario(
                    scenario_id=1,
                    graph_data=graph_data,
                    variables={},
                    db=mock_db
                )
                
                # 验证执行结果
                assert result["status"] == "completed"
                assert result["total_nodes"] == 4
                assert result["passed_nodes"] == 4
                
                # 验证执行顺序
                assert execution_times[0][0] == "node1"
                
                # node2 和 node3 应该在 node1 之后并行执行
                node2_time = execution_times[1][1]
                node3_time = execution_times[2][1]
                # 并行执行的时间差应该很小
                assert abs(node2_time - node3_time) < 0.2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])