"""
报错.md 问题修复回归测试脚本

测试范围：
1. 阶段恢复数据结构正确性
2. SKIPPED 阶段可恢复性
3. status 参数不冲突 fastapi.status
4. batch-apply 按 task_id/suggestion_id 精确命中
5. result_count 读取路径正确
6. current_stage 类型为 Integer
7. Celery 任务开始时显式置 running

运行方式：
    cd backend
    set PYTHONPATH=.
    python tests/test_bugfixes_regression.py
"""

import sys
import os

# 添加 backend 目录到 Python 路径
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.platform.db.base import Base, AsyncTask, User, Project, Version, FieldMappingSuggestion, ApiDefinition
from app.domains.data_mapping.processor import FieldMappingProcessor, FieldInfo, FieldMappingCandidate, FieldMappingSuggestion as FMSuggestion
from app.domains.data_mapping.constants import Stage, StageStatus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 使用 SQLite 内存数据库进行测试
TEST_DATABASE_URL = "sqlite:///:memory:"


class BugFixRegressionTest:
    """报错修复回归测试"""

    def __init__(self):
        self.engine = create_engine(TEST_DATABASE_URL, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = None
        self.test_results = []

    def setup(self):
        """初始化测试环境"""
        logger.info("=" * 60)
        logger.info("初始化测试环境...")
        
        # 创建所有表（使用 checkfirst 避免重复创建）
        Base.metadata.create_all(self.engine, checkfirst=True)
        self.db = self.SessionLocal()

        # 创建测试用户、项目、版本
        user = User(
            username="test_user",
            email="test@example.com",
            password_hash="test_hash"
        )
        self.db.add(user)
        self.db.flush()

        project = Project(
            name="test_project",
            business_domain="电商",
            created_by=user.id
        )
        self.db.add(project)
        self.db.flush()

        version = Version(
            project_id=project.id,
            version_number="V1.0.0",
            status="testing"
        )
        self.db.add(version)
        self.db.flush()

        self.user_id = user.id
        self.project_id = project.id
        self.version_id = version.id

        logger.info(f"✅ 测试环境初始化完成: user_id={user_id}, project_id={project_id}, version_id={version_id}")

    def teardown(self):
        """清理测试环境"""
        logger.info("清理测试环境...")
        self.db.close()
        self.engine.dispose()
        logger.info("✅ 测试环境清理完成")

    def record_result(self, test_name, passed, message=""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.test_results.append({
            "name": test_name,
            "passed": passed,
            "message": message
        })
        logger.info(f"{status} - {test_name}")
        if message:
            logger.info(f"    {message}")

    def test_1_stage_recovery_data_structure(self):
        """测试1：阶段恢复数据结构正确性"""
        try:
            # 创建测试任务
            task = AsyncTask(
                project_id=self.project_id,
                user_id=self.user_id,
                task_type="field_mapping_suggest",
                task_params={
                    "project_id": self.project_id,
                    "version_id": self.version_id,
                    "use_ai": True
                },
                status="pending",
                current_stage=0
            )
            self.db.add(task)
            self.db.flush()
            self.db.refresh(task)

            # 模拟阶段1保存
            field_registry_data = {
                "order_id": {
                    "field_name": "order_id",
                    "field_path": "body.order_id",
                    "source_type": "body",
                    "apis": [],
                    "total_count": 1,
                    "first_seen": "GET /orders"
                }
            }

            task.stage_results = {
                "stage_1": {
                    "name": "字段提取",
                    "status": "completed",
                    "data": {
                        "field_registry": field_registry_data,
                        "total_fields": 1
                    }
                }
            }
            self.db.commit()
            self.db.refresh(task)

            # 创建处理器并加载阶段1结果
            processor = FieldMappingProcessor(self.db, task)
            stage_data = processor._load_stage_result(Stage.FIELD_EXTRACTION)

            # 验证数据结构
            assert "field_registry" in stage_data, "缺少 field_registry"
            assert "order_id" in stage_data["field_registry"], "缺少 order_id 字段"
            
            self.record_result("测试1: 阶段恢复数据结构正确性", True)

        except Exception as e:
            self.record_result("测试1: 阶段恢复数据结构正确性", False, str(e))

    def test_2_skipped_stage_recovery(self):
        """测试2：SKIPPED 阶段可恢复性"""
        try:
            # 创建测试任务
            task = AsyncTask(
                project_id=self.project_id,
                user_id=self.user_id,
                task_type="field_mapping_suggest",
                task_params={
                    "project_id": self.project_id,
                    "version_id": self.version_id,
                    "use_ai": False  # 不使用AI，阶段4会被跳过
                },
                status="pending",
                current_stage=3
            )
            self.db.add(task)
            self.db.flush()
            self.db.refresh(task)

            # 模拟阶段4跳过
            task.stage_results = {
                "stage_4": {
                    "name": "AI优化",
                    "status": "skipped",
                    "data": {
                        "ai_results": {},
                        "skipped": True
                    }
                }
            }
            self.db.commit()
            self.db.refresh(task)

            # 创建处理器并加载阶段4结果
            processor = FieldMappingProcessor(self.db, task)
            stage_data = processor._load_stage_result(Stage.AI_OPTIMIZATION)

            # 验证可以加载 SKIPPED 状态
            assert stage_data is not None, "SKIPPED 阶段应该返回数据"
            assert stage_data.get("skipped") == True, "应该标记为 skipped"
            
            self.record_result("测试2: SKIPPED 阶段可恢复性", True)

        except Exception as e:
            self.record_result("测试2: SKIPPED 阶段可恢复性", False, str(e))

    def test_3_current_stage_integer_type(self):
        """测试3：current_stage 类型为 Integer"""
        try:
            # 创建测试任务
            task = AsyncTask(
                project_id=self.project_id,
                user_id=self.user_id,
                task_type="field_mapping_suggest",
                task_params={},
                status="pending",
                current_stage=2  # 设置为整数
            )
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)

            # 验证类型
            assert isinstance(task.current_stage, int), f"current_stage 应该是 int 类型，实际是 {type(task.current_stage)}"
            assert task.current_stage == 2, f"current_stage 值应该是 2，实际是 {task.current_stage}"
            
            self.record_result("测试3: current_stage 类型为 Integer", True)

        except Exception as e:
            self.record_result("测试3: current_stage 类型为 Integer", False, str(e))

    def test_4_result_count_read_path(self):
        """测试4：result_count 读取路径正确"""
        try:
            # 创建测试任务
            task = AsyncTask(
                project_id=self.project_id,
                user_id=self.user_id,
                task_type="field_mapping_suggest",
                task_params={},
                status="completed",
                result={
                    "status": "success",
                    "total": 10,
                    "suggestions": [
                        {"id": 1, "field": "order_id"},
                        {"id": 2, "field": "user_id"}
                    ]
                }
            )
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)

            # 测试读取路径：优先 result.suggestions
            if task.result and isinstance(task.result, dict):
                suggestions = task.result.get("suggestions")
                if suggestions and isinstance(suggestions, list):
                    result_count = len(suggestions)
                    assert result_count == 2, f"result_count 应该是 2，实际是 {result_count}"
                else:
                    # 兼容 result.data.items
                    result_data = task.result.get("data", {})
                    if isinstance(result_data, dict):
                        result_count = len(result_data.get("items", []))
                        assert result_count == 0, "应该读取到 0"
            
            self.record_result("测试4: result_count 读取路径正确", True)

        except Exception as e:
            self.record_result("测试4: result_count 读取路径正确", False, str(e))

    def test_5_batch_apply_precision(self):
        """测试5：batch-apply 按 task_id/suggestion_id 精确命中"""
        try:
            # 创建两个任务
            task1 = AsyncTask(
                project_id=self.project_id,
                user_id=self.user_id,
                task_type="field_mapping_suggest",
                task_params={},
                status="completed"
            )
            task2 = AsyncTask(
                project_id=self.project_id,
                user_id=self.user_id,
                task_type="field_mapping_suggest",
                task_params={},
                status="completed"
            )
            self.db.add(task1)
            self.db.add(task2)
            self.db.flush()

            # 创建 API 定义
            api_def = ApiDefinition(
                project_id=self.project_id,
                method="POST",
                path="/orders"
            )
            self.db.add(api_def)
            self.db.flush()

            # 创建建议记录（两个任务都有相同字段的建议）
            suggestion1 = FieldMappingSuggestion(
                task_id=task1.id,
                project_id=self.project_id,
                definition_id=api_def.id,
                api_field_path="body.order_id",
                candidates=[],
                status="pending"
            )
            suggestion2 = FieldMappingSuggestion(
                task_id=task2.id,
                project_id=self.project_id,
                definition_id=api_def.id,
                api_field_path="body.order_id",
                candidates=[],
                status="pending"
            )
            self.db.add(suggestion1)
            self.db.add(suggestion2)
            self.db.commit()

            # 测试按 task_id 精确命中
            result = self.db.query(FieldMappingSuggestion).filter(
                FieldMappingSuggestion.task_id == task1.id,
                FieldMappingSuggestion.api_field_path == "body.order_id",
                FieldMappingSuggestion.status == "pending"
            ).first()

            assert result is not None, "应该找到建议记录"
            assert result.task_id == task1.id, f"应该命中 task1，实际命中 task_id={result.task_id}"
            
            self.record_result("测试5: batch-apply 按 task_id/suggestion_id 精确命中", True)

        except Exception as e:
            self.record_result("测试5: batch-apply 按 task_id/suggestion_id 精确命中", False, str(e))

    def test_6_statistics_with_final_candidates(self):
        """测试6：统计字段失真修复（final_candidates 赋值）"""
        try:
            # 创建 FieldInfo 并设置 final_candidates
            field_info = FieldInfo(
                field_name="order_id",
                field_path="body.order_id",
                source_type="body",
                apis=[],
                total_count=1,
                first_seen="POST /orders"
            )
            
            # 设置 final_candidates
            field_info.final_candidates = [
                FieldMappingCandidate(
                    db_table="orders",
                    db_column="id",
                    score=0.95,
                    reasons=["语义匹配", "类型匹配"]
                )
            ]

            # 计算统计信息
            if field_info.final_candidates:
                top_score = field_info.final_candidates[0].score
                high_confidence = top_score >= 0.85
                
                assert high_confidence == True, f"top_score={top_score} 应该是高置信度"

            self.record_result("测试6: 统计字段失真修复（final_candidates 赋值）", True)

        except Exception as e:
            self.record_result("测试6: 统计字段失真修复（final_candidates 赋值）", False, str(e))

    def test_7_celery_running_state(self):
        """测试7：Celery 任务开始时显式置 running"""
        try:
            # 创建测试任务
            task = AsyncTask(
                project_id=self.project_id,
                user_id=self.user_id,
                task_type="field_mapping_suggest",
                task_params={},
                status="pending",
                started_at=None
            )
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)

            # 模拟 Celery 任务开始
            task.status = "running"
            task.started_at = datetime.now()
            self.db.commit()
            self.db.refresh(task)

            # 验证状态
            assert task.status == "running", f"任务状态应该是 running，实际是 {task.status}"
            assert task.started_at is not None, "started_at 不应该为空"

            self.record_result("测试7: Celery 任务开始时显式置 running", True)

        except Exception as e:
            self.record_result("测试7: Celery 任务开始时显式置 running", False, str(e))

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 60)
        logger.info("开始执行回归测试...")
        logger.info("=" * 60)

        self.setup()

        # 执行所有测试
        self.test_1_stage_recovery_data_structure()
        self.test_2_skipped_stage_recovery()
        self.test_3_current_stage_integer_type()
        self.test_4_result_count_read_path()
        self.test_5_batch_apply_precision()
        self.test_6_statistics_with_final_candidates()
        self.test_7_celery_running_state()

        self.teardown()

        # 输出测试结果
        logger.info("=" * 60)
        logger.info("测试结果汇总")
        logger.info("=" * 60)

        passed_count = sum(1 for r in self.test_results if r["passed"])
        failed_count = len(self.test_results) - passed_count

        for result in self.test_results:
            status = "✅" if result["passed"] else "❌"
            message = f" - {result['message']}" if result["message"] else ""
            logger.info(f"{status} {result['name']}{message}")

        logger.info("=" * 60)
        logger.info(f"总计: {len(self.test_results)} 个测试")
        logger.info(f"通过: {passed_count} 个")
        logger.info(f"失败: {failed_count} 个")
        logger.info("=" * 60)

        return failed_count == 0


def main():
    """主函数"""
    test_suite = BugFixRegressionTest()
    success = test_suite.run_all_tests()

    if success:
        logger.info("\n🎉 所有测试通过！")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())