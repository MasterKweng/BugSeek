"""
字段映射处理器功能测试

符合后端代码规范：
1. 测试覆盖：所有核心功能模块
2. Mock 使用：隔离外部依赖
3. 断言清晰：明确的预期结果
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.field_mapping.processor import (
    FieldMappingProcessor,
    FieldInfo,
    AIRequest,
    ScreeningResult,
    TaskCancelledException,
    PriorityAIQueue
)
from app.db.base import AsyncTask, ApiDefinition, DbSchemaVersion, ApiFieldMapping
from app.api.v1.field_mappings import FieldMappingCandidate, FieldMappingSuggestion


class TestFieldInfo:
    """字段信息数据类测试"""
    
    def test_field_info_initialization(self):
        """测试字段信息初始化"""
        field_info = FieldInfo(
            field_name="order_id",
            field_path="body.order_id",
            source_type="body",
            apis=[],
            total_count=0,
            first_seen="POST /orders"
        )
        
        assert field_info.field_name == "order_id"
        assert field_info.field_path == "body.order_id"
        assert field_info.source_type == "body"
        assert field_info.total_count == 0
        assert field_info.appears_in_multiple_apis is False
        assert field_info.field_name_common is False


class TestScreeningResult:
    """筛选结果数据类测试"""
    
    def test_screening_result_initialization(self):
        """测试筛选结果初始化"""
        result = ScreeningResult(
            ai_priority="high",
            reasons=["ID类字段", "多API共享"],
            action="ai_enhance"
        )
        
        assert result.ai_priority == "high"
        assert len(result.reasons) == 2
        assert result.action == "ai_enhance"


class TestPriorityAIQueue:
    """优先级AI队列测试"""
    
    def test_queue_initialization(self):
        """测试队列初始化"""
        queue = PriorityAIQueue()
        
        assert len(queue.high_queue) == 0
        assert len(queue.medium_queue) == 0
        assert len(queue.low_queue) == 0
        assert queue.batch_sizes == {'high': 5, 'medium': 10, 'low': 15}
    
    def test_enqueue_high_priority(self):
        """测试高优先级入队"""
        queue = PriorityAIQueue()
        field_info = FieldInfo(
            field_name="order_id",
            field_path="body.order_id",
            source_type="body",
            apis=[{'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.order_id'}],
            total_count=1,
            first_seen="POST /orders"
        )
        field_info.ai_priority = "high"
        
        queue.enqueue("order_id", field_info)
        
        assert len(queue.high_queue) == 1
        assert len(queue.medium_queue) == 0
        assert len(queue.low_queue) == 0
    
    def test_enqueue_medium_priority(self):
        """测试中优先级入队"""
        queue = PriorityAIQueue()
        field_info = FieldInfo(
            field_name="status",
            field_path="body.status",
            source_type="body",
            apis=[{'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.status'}],
            total_count=1,
            first_seen="POST /orders"
        )
        field_info.ai_priority = "medium"
        
        queue.enqueue("status", field_info)
        
        assert len(queue.high_queue) == 0
        assert len(queue.medium_queue) == 1
        assert len(queue.low_queue) == 0
    
    def test_enqueue_low_priority(self):
        """测试低优先级入队"""
        queue = PriorityAIQueue()
        field_info = FieldInfo(
            field_name="data",
            field_path="body.data",
            source_type="body",
            apis=[{'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.data'}],
            total_count=1,
            first_seen="POST /orders"
        )
        field_info.ai_priority = "low"
        
        queue.enqueue("data", field_info)
        
        assert len(queue.high_queue) == 0
        assert len(queue.medium_queue) == 0
        assert len(queue.low_queue) == 1
    
    def test_get_next_batch_high_priority(self):
        """测试获取高优先级批次"""
        queue = PriorityAIQueue()
        
        # 添加10个高优先级请求
        for i in range(10):
            field_info = FieldInfo(
                field_name=f"field_{i}",
                field_path=f"body.field_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': f'body.field_{i}'}],
                total_count=1,
                first_seen="POST /orders"
            )
            field_info.ai_priority = "high"
            queue.enqueue(f"field_{i}", field_info)
        
        priority, batch = queue.get_next_batch()
        
        assert priority == "high"
        assert len(batch) == 5  # 批次大小
        assert len(queue.high_queue) == 5  # 剩余5个
    
    def test_is_empty(self):
        """测试队列是否为空"""
        queue = PriorityAIQueue()
        
        assert queue.is_empty() is True
        
        field_info = FieldInfo(
            field_name="order_id",
            field_path="body.order_id",
            source_type="body",
            apis=[{'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.order_id'}],
            total_count=1,
            first_seen="POST /orders"
        )
        queue.enqueue("order_id", field_info)
        
        assert queue.is_empty() is False


class TestFieldMappingProcessor:
    """字段映射处理器测试"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock 数据库会话"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_task(self):
        """Mock 异步任务"""
        task = Mock(spec=AsyncTask)
        task.id = 1
        task.project_id = 1
        task.task_type = "field_mapping_suggest"
        task.task_params = {
            'project_id': 1,
            'version_id': 1,
            'include_paths': True,
            'include_query': True,
            'include_body': True,
            'use_ai': True
        }
        task.progress = 0
        task.progress_message = ""
        task.current_stage = None
        task.stages = []
        task.statistics = {}
        task.status = "pending"
        
        return task
    
    @pytest.fixture
    def processor(self, mock_db, mock_task):
        """创建处理器实例"""
        return FieldMappingProcessor(mock_db, mock_task)
    
    def test_processor_initialization(self, processor, mock_db, mock_task):
        """测试处理器初始化"""
        assert processor.db == mock_db
        assert processor.task == mock_task
        assert processor.max_workers == 4
        assert processor.batch_size == 100
        assert processor.max_ai_retries == 3
        assert processor.ai_retry_delay == 2
        assert processor.ai_timeout == 30
        assert processor._cancelled is False
    
    def test_check_cancelled_not_cancelled(self, processor, mock_task):
        """测试检查取消状态（未取消）"""
        mock_task.status = "running"
        
        result = processor._check_cancelled()
        
        assert result is False
        assert processor._cancelled is False
    
    def test_check_cancelled_cancelled(self, processor, mock_task):
        """测试检查取消状态（已取消）"""
        mock_task.status = "cancelled"
        
        result = processor._check_cancelled()
        
        assert result is True
        assert processor._cancelled is True
    
    def test_raise_if_cancelled(self, processor, mock_task):
        """测试取消异常抛出"""
        mock_task.status = "cancelled"
        
        with pytest.raises(TaskCancelledException, match="任务已被取消"):
            processor._raise_if_cancelled()
    
    def test_raise_if_cancelled_not_cancelled(self, processor, mock_task):
        """测试取消异常抛出（未取消）"""
        mock_task.status = "running"
        
        # 不应该抛出异常
        processor._raise_if_cancelled()
    
    def test_update_progress(self, processor, mock_task):
        """测试进度更新"""
        processor._update_progress(50, "处理中")
        
        assert mock_task.progress == 50
        assert mock_task.progress_message == "处理中"
        mock_db.commit.assert_called_once()
    
    def test_update_realtime_progress(self, processor, mock_task):
        """测试实时进度更新"""
        processor._update_realtime_progress(50, "处理中", 100, 200)
        
        assert mock_task.progress == 50
        assert mock_task.progress_message == "处理中"
        assert mock_task.statistics["processed"] == 100
        assert mock_task.statistics["total"] == 200
        assert mock_task.statistics["remaining"] == 100
        assert mock_task.statistics["completion_rate"] == 50.0
    
    def test_parse_field_path(self, processor):
        """测试字段路径解析"""
        source_type, field_name = processor._parse_field_path("body.order_id")
        
        assert source_type == "body"
        assert field_name == "order_id"
    
    def test_parse_field_path_without_prefix(self, processor):
        """测试字段路径解析（无前缀）"""
        source_type, field_name = processor._parse_field_path("order_id")
        
        assert source_type == "body"
        assert field_name == "order_id"
    
    def test_is_id_field(self, processor):
        """测试ID字段判断"""
        assert processor._is_id_field("id") is True
        assert processor._is_id_field("order_id") is True
        assert processor._is_id_field("userId") is True
        assert processor._is_id_field("uuid") is True
        assert processor._is_id_field("status") is False
        assert processor._is_id_field("name") is False
    
    def test_is_complex_nested(self, processor):
        """测试复杂嵌套字段判断"""
        assert processor._is_complex_nested("a.b.c.d") is True
        assert processor._is_complex_nested("a.b.c") is False
        assert processor._is_complex_nested("a.b") is False
    
    def test_is_array_field(self, processor):
        """测试数组字段判断"""
        assert processor._is_array_field("items[]") is True
        assert processor._is_array_field("body.items") is True
        assert processor._is_array_field("order_id") is False


class TestIntelligentScreening:
    """智能筛选功能测试"""
    
    @pytest.fixture
    def processor(self):
        """创建处理器实例"""
        mock_db = Mock(spec=Session)
        mock_task = Mock(spec=AsyncTask)
        return FieldMappingProcessor(mock_db, mock_task)
    
    @pytest.fixture
    def high_confidence_field_info(self):
        """高置信度字段信息"""
        return FieldInfo(
            field_name="order_id",
            field_path="body.order_id",
            source_type="body",
            apis=[{'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.order_id'}],
            total_count=1,
            first_seen="POST /orders"
        )
    
    @pytest.fixture
    def medium_confidence_field_info(self):
        """中等置信度字段信息"""
        return FieldInfo(
            field_name="status",
            field_path="body.status",
            source_type="body",
            apis=[{'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.status'}],
            total_count=1,
            first_seen="POST /orders"
        )
    
    def test_screen_field_high_confidence(self, processor, high_confidence_field_info):
        """测试高置信度字段筛选"""
        candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="id",
                score=0.92,
                reasons=["路径语义匹配", "字段名匹配"]
            )
        ]
        
        result = processor._screen_field("order_id", high_confidence_field_info, candidates)
        
        assert result.ai_priority == "none"
        assert "规则评分高(≥0.85)，无需AI确认" in result.reasons
        assert result.action == "auto_confirm"
    
    def test_screen_field_medium_confidence(self, processor, medium_confidence_field_info):
        """测试中等置信度字段筛选"""
        candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="status",
                score=0.70,
                reasons=["字段名匹配"]
            )
        ]
        
        result = processor._screen_field("status", medium_confidence_field_info, candidates)
        
        assert result.ai_priority == "medium"
        assert "规则评分中等(0.60-0.85)，AI优化候选排序" in result.reasons
    
    def test_screen_field_low_confidence(self, processor, medium_confidence_field_info):
        """测试低置信度字段筛选"""
        candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="description",
                score=0.45,
                reasons=["类型匹配"]
            )
        ]
        
        result = processor._screen_field("description", medium_confidence_field_info, candidates)
        
        assert result.ai_priority == "high"
        assert "规则评分低(<0.60)，需要AI重新推荐" in result.reasons
    
    def test_screen_field_no_candidates(self, processor, medium_confidence_field_info):
        """测试无候选字段筛选"""
        result = processor._screen_field("unknown", medium_confidence_field_info, [])
        
        assert result.ai_priority == "high"
    
    def test_screen_field_id_field(self, processor):
        """测试ID字段筛选"""
        field_info = FieldInfo(
            field_name="order_id",
            field_path="body.order_id",
            source_type="body",
            apis=[{'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.order_id'}],
            total_count=1,
            first_seen="POST /orders"
        )
        candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="id",
                score=0.60,
                reasons=["字段名匹配"]
            )
        ]
        
        result = processor._screen_field("order_id", field_info, candidates)
        
        assert result.ai_priority == "high"
        assert "ID类字段，需要AI精确匹配" in result.reasons
    
    def test_screen_field_multiple_apis(self, processor, medium_confidence_field_info):
        """测试多API共享字段筛选"""
        medium_confidence_field_info.apis = [
            {'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.status'},
            {'method': 'PUT', 'path': '/orders/{id}', 'definition_id': 2, 'field_path': 'body.status'},
            {'method': 'GET', 'path': '/orders', 'definition_id': 3, 'field_path': 'query.status'}
        ]
        medium_confidence_field_info.total_count = 3
        candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="status",
                score=0.90,
                reasons=["字段名匹配"]
            )
        ]
        
        result = processor._screen_field("status", medium_confidence_field_info, candidates)
        
        # 即使置信度高，也会因为多API共享而降低优先级
        assert result.ai_priority == "low"
        assert "字段在3个API中使用" in result.reasons
    
    def test_merge_candidates(self, processor):
        """测试候选合并"""
        rule_candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="id",
                score=0.80,
                reasons=["规则1"]
            ),
            FieldMappingCandidate(
                db_table="users",
                db_column="id",
                score=0.70,
                reasons=["规则2"]
            )
        ]
        
        ai_candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="id",
                score=0.95,
                reasons=["AI优化"]
            ),
            FieldMappingCandidate(
                db_table="order_items",
                db_column="order_id",
                score=0.85,
                reasons=["AI建议"]
            )
        ]
        
        merged = processor._merge_candidates(rule_candidates, ai_candidates)
        
        assert len(merged) == 3
        assert merged[0].db_table == "orders"
        assert merged[0].db_column == "id"
        assert merged[0].score == 0.95  # AI评分更高
        assert merged[1].db_table == "order_items"
        assert merged[1].score == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])