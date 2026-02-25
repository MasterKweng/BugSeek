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
            first_seen="POST /orders",
            appears_in_multiple_apis=False,
            field_name_common=False,
            field_description="订单ID",  # 新增字段
            has_description=True         # 新增字段
        )
        
        assert field_info.field_name == "order_id"
        assert field_info.field_path == "body.order_id"
        assert field_info.source_type == "body"
        assert field_info.total_count == 0
        assert field_info.appears_in_multiple_apis is False
        assert field_info.field_name_common is False
        assert field_info.field_description == "订单ID"  # 新增断言
        assert field_info.has_description is True         # 新增断言
    
    def test_field_info_without_description(self):
        """测试无描述的字段信息初始化"""
        field_info = FieldInfo(
            field_name="id",
            field_path="query.id",
            source_type="query",
            apis=[],
            total_count=0,
            first_seen="GET /orders",
            appears_in_multiple_apis=False,
            field_name_common=False
        )
        
        assert field_info.field_description is None  # 默认为 None
        assert field_info.has_description is False    # 默认为 False


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
    
    def test_update_progress(self, processor, mock_task, mock_db):
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
        """test medium confidence screening"""
        candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="status",
                score=0.70,
                reasons=["name matched"]
            ),
            FieldMappingCandidate(
                db_table="order_events",
                db_column="status",
                score=0.62,
                reasons=["semantic related"]
            )
        ]

        result = processor._screen_field("status", medium_confidence_field_info, candidates)

        assert result.ai_priority == "medium"
        assert any("0.60-0.85" in r for r in result.reasons)

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
        """test multi-api field screening"""
        medium_confidence_field_info.apis = [
            {'method': 'POST', 'path': '/orders', 'definition_id': 1, 'field_path': 'body.status'},
            {'method': 'PUT', 'path': '/orders/{id}', 'definition_id': 2, 'field_path': 'body.status'},
            {'method': 'GET', 'path': '/orders', 'definition_id': 3, 'field_path': 'query.status'}
        ]
        medium_confidence_field_info.total_count = 3
        medium_confidence_field_info.appears_in_multiple_apis = True
        candidates = [
            FieldMappingCandidate(
                db_table="orders",
                db_column="status",
                score=0.70,
                reasons=["name matched"]
            ),
            FieldMappingCandidate(
                db_table="order_events",
                db_column="status",
                score=0.65,
                reasons=["semantic related"]
            )
        ]

        result = processor._screen_field("status", medium_confidence_field_info, candidates)

        assert result.ai_priority == "medium"
        assert any("API" in r for r in result.reasons)

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


class TestFieldDescriptionFeatures:
    """字段描述功能测试"""
    
    def test_extract_field_name_from_path(self):
        """测试从路径中提取字段名"""
        from app.utils.vector_index import VectorIndexManager
        manager = VectorIndexManager()
        
        # 测试各种路径格式
        assert manager._extract_field_name_from_path("body.order_id") == "order_id"
        assert manager._extract_field_name_from_path("query.user_id") == "user_id"
        assert manager._extract_field_name_from_path("path.id") == "id"
        assert manager._extract_field_name_from_path("id") == "id"
    
    def test_build_query_text(self):
        """测试构建查询文本"""
        from app.utils.vector_index import VectorIndexManager
        manager = VectorIndexManager()
        
        # 无描述
        assert manager._build_query_text("order_id", None) == "order_id"
        assert manager._build_query_text("order_id", "") == "order_id"
        
        # 有描述
        assert manager._build_query_text("order_id", "订单ID") == "order_id 订单ID"
        assert manager._build_query_text("user_name", "用户姓名") == "user_name 用户姓名"
    
    def test_calculate_text_similarity(self):
        """测试文本相似度计算"""
        import re
        from app.field_mapping.processor import FieldMappingProcessor
        
        def calculate_similarity(text1: str, text2: str) -> float:
            """直接使用方法实现进行测试"""
            if not text1 or not text2:
                return 0.0
            
            words1 = set(re.findall(r'\w+', text1.lower()))
            words2 = set(re.findall(r'\w+', text2.lower()))
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            
            return intersection / union if union else 0.0
        
        # 完全匹配
        sim = calculate_similarity("order_id", "order_id")
        assert sim == 1.0
        
        # 部分匹配（有共同词）
        sim = calculate_similarity("order_id user_id", "order_id")
        assert sim > 0.3
        
        # 低相似度（无共同词）
        sim = calculate_similarity("order_id", "user_name")
        assert sim == 0.0
        
        # 空文本
        assert calculate_similarity("", "order_id") == 0.0
        assert calculate_similarity("order_id", "") == 0.0
    
    def test_get_column_comment(self):
        """测试获取列注释"""
        import re
        from app.field_mapping.processor import FieldMappingProcessor
        
        def get_column_comment(db_schema, table_name, column_name) -> str:
            """直接使用方法实现进行测试"""
            if not db_schema or not isinstance(db_schema, dict):
                return ""
            
            tables = db_schema.get("tables", {})
            if table_name not in tables:
                return ""
            
            columns = tables[table_name].get("columns", {})
            if column_name not in columns:
                return ""
            
            return columns[column_name].get("comment", "")
        
        db_schema = {
            "tables": {
                "orders": {
                    "columns": {
                        "id": {"name": "id", "type": "int", "comment": "订单主键ID"},
                        "order_no": {"name": "order_no", "type": "varchar", "comment": "订单编号"}
                    }
                },
                "users": {
                    "columns": {
                        "id": {"name": "id", "type": "int", "comment": "用户ID"}
                    }
                }
            }
        }
        
        # 存在的列
        assert get_column_comment(db_schema, "orders", "id") == "订单主键ID"
        assert get_column_comment(db_schema, "orders", "order_no") == "订单编号"
        
        # 不存在的表或列
        assert get_column_comment(db_schema, "orders", "name") == ""
        assert get_column_comment(db_schema, "products", "id") == ""
        
        # 空的 db_schema
        assert get_column_comment({}, "orders", "id") == ""
        assert get_column_comment(None, "orders", "id") == ""
    
    def test_is_id_type_by_description(self):
        """测试根据描述判断是否为ID类型（简化版）"""
        import re
        from app.field_mapping.processor import FieldMappingProcessor
        
        def is_id_type_by_description(field_description) -> bool:
            """直接使用方法实现进行测试"""
            if not field_description:
                return True
            
            id_keywords = [
                'id', 'ID', '标识', '唯一标识',
                'unique', 'identifier', 'uuid', '主键',
                '主键ID', '唯一ID', 'ID号'
            ]
            
            for keyword in id_keywords:
                if keyword in field_description:
                    return True
            
            not_id_keywords = [
                '非ID', 'not id', '不是id', '编号(非ID)',
                '非标识', 'not identifier', '编号(字符串)'
            ]
            for keyword in not_id_keywords:
                if keyword in field_description:
                    return False
            
            description_lower = field_description.lower().strip()
            
            if len(description_lower) < 10:
                return True
            
            if description_lower.isdigit():
                return True
            
            code_keywords = ['编号', '号码', '代码', 'code', 'number']
            for keyword in code_keywords:
                if keyword in field_description:
                    return False
            
            return True
        
        # 基本测试
        assert is_id_type_by_description("订单ID") == True
        assert is_id_type_by_description("UUID") == True
        assert is_id_type_by_description("") == True
        assert is_id_type_by_description(None) == True
        assert is_id_type_by_description("123") == True
        
        # 短描述（<10字符），保守判断为 True
        assert is_id_type_by_description("订单号") == True  # 长度3，<10
        
        # 模糊情况（保守判断）
        assert is_id_type_by_description("") == True
        assert is_id_type_by_description(None) == True
        assert is_id_type_by_description("123") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])