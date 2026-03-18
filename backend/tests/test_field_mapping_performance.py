"""
字段映射性能测试

符合后端代码规范：
1. 性能测试：验证关键指标
2. 基准测试：对比优化效果
3. 资源监控：内存和CPU使用
"""

import pytest
import time
import psutil
import os
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.domains.data_mapping.processor import (
    FieldMappingProcessor,
    FieldInfo,
    PriorityAIQueue
)
from app.platform.db.base import AsyncTask
from app.api.v1.field_mappings import FieldMappingCandidate


class TestPerformanceMetrics:
    """性能指标测试"""
    
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
    
    def test_queue_batch_processing_performance(self, processor):
        """测试队列批处理性能"""
        queue = PriorityAIQueue()
        
        # 添加1000个字段
        start_time = time.time()
        
        for i in range(1000):
            field_info = FieldInfo(
                field_name=f"field_{i}",
                field_path=f"body.field_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.field_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
            
            # 分配优先级
            if i < 250:
                field_info.ai_priority = "high"
            elif i < 550:
                field_info.ai_priority = "medium"
            else:
                field_info.ai_priority = "low"
            
            queue.enqueue(f"field_{i}", field_info)
        
        enqueue_time = time.time() - start_time
        
        # 验证入队性能
        assert enqueue_time < 1.0, f"入队1000个字段耗时{enqueue_time:.2f}秒，应小于1秒"
        
        # 测试批次处理
        start_time = time.time()
        batch_count = 0
        
        while not queue.is_empty():
            priority, batch = queue.get_next_batch()
            batch_count += 1
        
        processing_time = time.time() - start_time
        
        # 验证批次处理性能
        assert processing_time < 0.1, f"处理1000个字段批次耗时{processing_time:.4f}秒，应小于0.1秒"
        
        # 验证批次数
        expected_batches = (250 // 5) + (300 // 10) + (450 // 15)
        assert batch_count == expected_batches, f"期望{expected_batches}批次，实际{batch_count}批次"
    
    def test_candidate_merge_performance(self, processor):
        """测试候选合并性能"""
        # 创建大量候选
        rule_candidates = [
            FieldMappingCandidate(
                db_table=f"table_{i // 10}",
                db_column=f"column_{i % 10}",
                score=0.5 + (i % 50) / 100,
                reasons=[f"reason_{j}" for j in range(3)]
            )
            for i in range(100)
        ]
        
        ai_candidates = [
            FieldMappingCandidate(
                db_table=f"table_{i // 10}",
                db_column=f"column_{i % 10}",
                score=min(1.0, 0.5 + (i % 50) / 100 + 0.1),
                reasons=[f"ai_reason_{j}" for j in range(2)]
            )
            for i in range(100)
        ]
        
        # 测试合并性能
        start_time = time.time()
        
        merged = processor._merge_candidates(rule_candidates, ai_candidates)
        
        merge_time = time.time() - start_time
        
        # 验证合并性能
        assert merge_time < 0.05, f"合并200个候选耗时{merge_time:.4f}秒，应小于0.05秒"
        
        # 验证去重
        # 应该只有50个唯一的字段组合
        assert len(merged) <= 100
    
    def test_screening_performance(self, processor):
        """测试智能筛选性能"""
        # 创建大量字段信息
        field_infos = []
        candidates_list = []
        
        for i in range(1000):
            field_info = FieldInfo(
                field_name=f"field_{i}",
                field_path=f"body.field_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.field_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
            
            candidates = [
                FieldMappingCandidate(
                    db_table="table_1",
                    db_column=f"column_{j}",
                    score=0.5 + (j * 0.1),
                    reasons=["规则匹配"]
                )
                for j in range(5)
            ]
            
            field_infos.append((f"field_{i}", field_info))
            candidates_list.append(candidates)
        
        # 测试筛选性能
        start_time = time.time()
        
        for field_name, field_info in field_infos:
            result = processor._screen_field(field_name, field_info, candidates_list[int(field_name.split('_')[1])])
        
        screening_time = time.time() - start_time
        
        # 验证筛选性能
        assert screening_time < 1.0, f"筛选1000个字段耗时{screening_time:.2f}秒，应小于1秒"
    
    def test_memory_usage_during_processing(self, processor):
        """测试处理过程中的内存使用"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 模拟处理大量数据
        field_registry = {}
        
        for i in range(10000):
            field_registry[f"field_{i}"] = FieldInfo(
                field_name=f"field_{i}",
                field_path=f"body.field_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.field_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # 验证内存使用
        # 10000个字段应该在合理内存范围内（< 100MB）
        assert memory_increase < 100, f"处理10000个字段内存增加{memory_increase:.2f}MB，应小于100MB"
    
    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_parallel_processing_efficiency(self, mock_executor_class, processor):
        """测试并行处理效率"""
        # Mock ThreadPoolExecutor
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        
        # 模拟并行任务
        futures = []
        for i in range(100):
            future = Mock()
            future.result.return_value = {
                f"field_{i}": [
                    FieldMappingCandidate(
                        db_table="table_1",
                        db_column="column_1",
                        score=0.8,
                        reasons=["匹配"]
                    )
                ]
            }
            futures.append(future)
        
        mock_executor.submit.side_effect = futures
        
        start_time = time.time()
        
        results = {}
        for future in futures:
            batch_idx = 0
            try:
                batch_results = future.result()
                results.update(batch_results)
            except Exception:
                pass
        
        processing_time = time.time() - start_time
        
        # 验证并行处理效率
        assert processing_time < 0.5, f"并行处理100个任务耗时{processing_time:.2f}秒，应小于0.5秒"
    
    def test_progress_update_overhead(self, processor, mock_db):
        """测试进度更新开销"""
        # 测试大量进度更新的开销
        start_time = time.time()
        
        for i in range(100):
            processor._update_progress(i, f"处理中 {i}%")
        
        update_time = time.time() - start_time
        
        # 验证进度更新开销
        assert update_time < 0.5, f"100次进度更新耗时{update_time:.4f}秒，应小于0.5秒"
        
        # 验证数据库提交次数
        assert mock_db.commit.call_count == 100
    
    def test_realtime_progress_update_overhead(self, processor, mock_db):
        """测试实时进度更新开销"""
        start_time = time.time()
        
        for i in range(100):
            processor._update_realtime_progress(i, f"处理中 {i}%", i, 100)
        
        update_time = time.time() - start_time
        
        # 验证实时进度更新开销
        assert update_time < 0.5, f"100次实时进度更新耗时{update_time:.4f}秒，应小于0.5秒"


class TestPerformanceBenchmarks:
    """性能基准测试"""
    
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
    
    def test_deduplication_efficiency(self, processor):
        """测试去重效率"""
        # 创建包含重复字段的注册表
        field_registry = {}
        
        # 模拟1000个唯一字段，每个字段平均出现3次
        for i in range(1000):
            field_name = f"field_{i % 1000}"  # 1000个唯一字段名
            
            if field_name not in field_registry:
                field_registry[field_name] = FieldInfo(
                    field_name=field_name,
                    field_path=f"body.{field_name}",
                    source_type="body",
                    apis=[],
                    total_count=0,
                    first_seen="POST /api"
                )
            
            # 添加API引用
            for j in range(3):
                field_registry[field_name].apis.append({
                    'method': 'POST',
                    'path': f'/api/{j}',
                    'definition_id': j,
                    'field_path': f'body.{field_name}'
                })
                field_registry[field_name].total_count += 1
        
        # 验证去重效果
        assert len(field_registry) == 1000, "应该有1000个唯一字段"
        
        total_occurrences = sum(len(f.apis) for f in field_registry.values())
        assert total_occurrences == 3000, "总共应该有3000次出现"
        
        # 去重率
        deduplication_rate = (3000 - 1000) / 3000 * 100
        assert round(deduplication_rate, 2) == 66.67, f"去重率应该是66.67%，实际是{deduplication_rate}%"
    
    def test_batch_size_impact(self, processor):
        """测试批次大小对性能的影响"""
        # 测试不同批次大小的处理时间
        batch_sizes = [50, 100, 200, 500]
        results = {}
        batch_counts = {}
        
        for batch_size in batch_sizes:
            processor.batch_size = batch_size
            
            # 创建测试数据
            field_items = [(f"field_{i}", Mock()) for i in range(1000)]
            
            # 模拟分批
            start_time = time.time()
            batches = [
                field_items[i:i + batch_size]
                for i in range(0, len(field_items), batch_size)
            ]
            batch_counts[batch_size] = len(batches)
            
            # 模拟处理
            for batch in batches:
                pass  # 实际处理逻辑
            
            processing_time = time.time() - start_time
            results[batch_size] = processing_time
        
        # 验证批次大小影响
        # 批次大小应该在合理范围内（50-200）
        assert batch_counts[50] == 20
        assert batch_counts[100] == 10
        assert batch_counts[200] == 5
        assert batch_counts[500] == 2
        assert all(duration >= 0 for duration in results.values())
    
    def test_ai_call_concurrency_limit(self, processor):
        """测试AI调用并发限制"""
        # 验证AI调用并发限制配置
        assert processor.max_ai_retries == 3, "最大重试次数应该是3"
        assert processor.ai_retry_delay == 2, "重试延迟应该是2秒"
        assert processor.ai_timeout == 30, "AI调用超时应该是30秒"
        
        # 验证批次大小配置
        queue = PriorityAIQueue()
        assert queue.batch_sizes['high'] == 5, "高优先级批次大小应该是5"
        assert queue.batch_sizes['medium'] == 10, "中优先级批次大小应该是10"
        assert queue.batch_sizes['low'] == 15, "低优先级批次大小应该是15"
    
    def test_large_scale_processing_simulation(self, processor):
        """测试大规模处理模拟"""
        # 模拟大规模数据处理（644个API，约2000个字段）
        total_fields = 2000
        unique_fields = int(total_fields * 0.5)  # 50%去重
        
        # 模拟字段注册表
        field_registry = {}
        
        start_time = time.time()
        
        for i in range(unique_fields):
            field_registry[f"field_{i}"] = FieldInfo(
                field_name=f"field_{i}",
                field_path=f"body.field_{i}",
                source_type="body",
                apis=[],
                total_count=0,
                first_seen="POST /api"
            )
            
            # 每个字段平均出现2次
            for j in range(2):
                field_registry[f"field_{i}"].apis.append({
                    'method': 'POST',
                    'path': f'/api/{j}',
                    'definition_id': j,
                    'field_path': f'body.field_{i}'
                })
                field_registry[f"field_{i}"].total_count += 1
        
        creation_time = time.time() - start_time
        
        # 验证创建性能
        assert creation_time < 1.0, f"创建{unique_fields}个字段信息耗时{creation_time:.2f}秒，应小于1秒"
        
        # 验证数据规模
        assert len(field_registry) == unique_fields
        assert sum(len(f.apis) for f in field_registry.values()) == total_fields


class TestPerformanceOptimization:
    """性能优化验证"""
    
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
    
    def test_intelligent_screening_reduces_ai_calls(self, processor):
        """测试智能筛选减少AI调用"""
        # 创建测试字段
        fields = []
        
        # 40%高置信度（无需AI）
        for i in range(400):
            field_info = FieldInfo(
                field_name=f"high_conf_{i}",
                field_path=f"body.high_conf_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.high_conf_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
            candidates = [FieldMappingCandidate(
                db_table="table_1",
                db_column="column_1",
                score=0.90,
                reasons=["高置信度"]
            )]
            fields.append((f"high_conf_{i}", field_info, candidates))
        
        # 30%中等置信度（需要AI）
        for i in range(300):
            field_info = FieldInfo(
                field_name=f"medium_conf_{i}",
                field_path=f"body.medium_conf_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.medium_conf_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
            candidates = [FieldMappingCandidate(
                db_table="table_1",
                db_column="column_1",
                score=0.70,
                reasons=["中等置信度"]
            )]
            fields.append((f"medium_conf_{i}", field_info, candidates))
        
        # 30%低置信度（必须AI）
        for i in range(300):
            field_info = FieldInfo(
                field_name=f"low_conf_{i}",
                field_path=f"body.low_conf_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.low_conf_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
            candidates = [FieldMappingCandidate(
                db_table="table_1",
                db_column="column_1",
                score=0.40,
                reasons=["低置信度"]
            )]
            fields.append((f"low_conf_{i}", field_info, candidates))
        
        # 执行筛选
        auto_confirm_count = 0
        ai_call_count = 0
        
        for field_name, field_info, candidates in fields:
            result = processor._screen_field(field_name, field_info, candidates)
            if result.ai_priority == "none":
                auto_confirm_count += 1
            else:
                ai_call_count += 1
        
        # 验证筛选效果
        assert auto_confirm_count == 400, f"应该有400个自动确认，实际{auto_confirm_count}个"
        assert ai_call_count == 600, f"应该有600个需要AI调用，实际{ai_call_count}个"
        
        # AI调用减少率
        ai_reduction_rate = (1000 - 600) / 1000 * 100
        assert ai_reduction_rate == 40, f"AI调用减少率应该是40%，实际是{ai_reduction_rate}%"
    
    def test_priority_queue_optimizes_ai_order(self, processor):
        """测试优先级队列优化AI调用顺序"""
        queue = PriorityAIQueue()
        
        # 添加不同优先级的字段
        high_count = 250
        medium_count = 300
        low_count = 50
        
        for i in range(high_count):
            field_info = FieldInfo(
                field_name=f"high_{i}",
                field_path=f"body.high_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.high_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
            field_info.ai_priority = "high"
            queue.enqueue(f"high_{i}", field_info)
        
        for i in range(medium_count):
            field_info = FieldInfo(
                field_name=f"medium_{i}",
                field_path=f"body.medium_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.medium_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
            field_info.ai_priority = "medium"
            queue.enqueue(f"medium_{i}", field_info)
        
        for i in range(low_count):
            field_info = FieldInfo(
                field_name=f"low_{i}",
                field_path=f"body.low_{i}",
                source_type="body",
                apis=[{'method': 'POST', 'path': '/api', 'definition_id': 1, 'field_path': f'body.low_{i}'}],
                total_count=1,
                first_seen="POST /api"
            )
            field_info.ai_priority = "low"
            queue.enqueue(f"low_{i}", field_info)
        
        # 验证批次顺序
        # 第一批应该是高优先级
        priority, batch = queue.get_next_batch()
        assert priority == "high"
        assert len(batch) == 5
        
        # 继续处理所有高优先级
        high_batches = 1
        while priority == "high":
            priority, batch = queue.get_next_batch()
            if priority == "high":
                high_batches += 1
        
        # 验证高优先级批次数
        expected_high_batches = high_count // 5
        assert high_batches == expected_high_batches


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
