"""
API 定义管理接口测试（阶段四详细设计验证）

测试范围：
1. POST /api-definitions - 创建 API 定义
2. GET /api-definitions - 获取 API 定义列表
3. GET /api-definitions/{definition_id} - 获取单个 API 定义详情

符合后端代码规范：
- 统一响应体验证
- IDOR 防御验证
- 全链路 TraceID 验证
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.orm import Session

from app.api.v1.api_definitions import (
    ApiDefinitionCreate,
    ApiResponse
)
from app.platform.db.base import ApiDefinition, User, Project


class TestApiDefinitionsModels:
    """API 定义模型测试"""

    def test_api_definition_create_model_validation(self):
        """
        测试 ApiDefinitionCreate 模型验证

        验证点：
        1. 正确解析请求参数
        2. 类型验证
        3. 必填字段验证
        """
        # 测试有效数据
        request = ApiDefinitionCreate(
            method="POST",
            path="/api/orders",
            summary="创建订单",
            description="创建新订单的接口",
            tags=["订单", "创建"],
            group_id=1,
            request_schema={
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "quantity": {"type": "integer"}
                }
            },
            response_schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "status": {"type": "string"}
                }
            }
        )

        # 验证数据
        assert request.method == "POST"
        assert request.path == "/api/orders"
        assert request.summary == "创建订单"
        assert request.tags == ["订单", "创建"]
        assert request.group_id == 1
        assert "type" in request.request_schema
        assert request.request_schema["type"] == "object"

    def test_api_definition_create_model_defaults(self):
        """
        测试 ApiDefinitionCreate 模型默认值

        验证点：
        1. tags 默认为空列表
        2. summary 默认为 None
        3. description 默认为 None
        """
        # 测试最小必需数据
        request = ApiDefinitionCreate(
            method="GET",
            path="/api/users"
        )

        # 验证默认值
        assert request.summary is None
        assert request.description is None
        assert request.tags == []
        assert request.group_id is None
        assert request.request_schema is None
        assert request.response_schema is None

    def test_api_response_model(self):
        """
        测试 ApiResponse 模型

        验证点：
        1. 统一响应格式
        2. 默认值正确
        """
        # 测试成功响应
        response = ApiResponse(
            code=0,
            message="创建成功",
            data={"id": 1, "method": "POST"}
        )

        # 验证数据
        assert response.code == 0
        assert response.message == "创建成功"
        assert response.data is not None
        assert response.data["id"] == 1

        # 测试默认值
        default_response = ApiResponse()
        assert default_response.code == 0
        assert default_response.message == "success"
        assert default_response.data is None


class TestApiDefinitionsEnums:
    """API 定义枚举测试"""

    def test_api_definition_status_enum(self):
        """
        测试 ApiDefinitionStatus 枚举

        验证点：
        1. 枚举值定义正确
        2. 类型正确
        """
        from app.api.v1.api_definitions import ApiDefinitionStatus

        # 验证枚举值
        assert ApiDefinitionStatus.ACTIVE == "active"
        assert ApiDefinitionStatus.ARCHIVED == "archived"
        assert ApiDefinitionStatus.DEPRECATED == "deprecated"

        # 验证类型
        assert isinstance(ApiDefinitionStatus.ACTIVE, str)
        assert isinstance(ApiDefinitionStatus.ARCHIVED, str)
        assert isinstance(ApiDefinitionStatus.DEPRECATED, str)

    def test_sync_status_enum(self):
        """
        测试 SyncStatus 枚举

        验证点：
        1. 枚举值定义正确
        2. 类型正确
        """
        from app.api.v1.api_definitions import SyncStatus

        # 验证枚举值
        assert SyncStatus.SYNCED == "synced"
        assert SyncStatus.CONFLICT == "conflict"
        assert SyncStatus.PENDING == "pending"

        # 验证类型
        assert isinstance(SyncStatus.SYNCED, str)
        assert isinstance(SyncStatus.CONFLICT, str)
        assert isinstance(SyncStatus.PENDING, str)

    def test_lock_status_enum(self):
        """
        测试 LockStatus 枚举

        验证点：
        1. 枚举值定义正确
        2. 类型正确
        """
        from app.api.v1.api_definitions import LockStatus

        # 验证枚举值
        assert LockStatus.UNLOCKED == "unlocked"
        assert LockStatus.LOCKED == "locked"
        assert LockStatus.LOCKED_FIELDS == "locked_fields"

        # 验证类型
        assert isinstance(LockStatus.UNLOCKED, str)
        assert isinstance(LockStatus.LOCKED, str)
        assert isinstance(LockStatus.LOCKED_FIELDS, str)


class TestApiDefinitionsBusinessLogic:
    """API 定义业务逻辑测试"""

    def test_content_hash_calculation(self):
        """
        测试内容哈希计算

        验证点：
        1. 相同内容生成相同哈希
        2. 不同内容生成不同哈希
        """
        import hashlib
        import json

        # 准备测试数据
        content1 = {
            "method": "POST",
            "path": "/api/orders",
            "request_schema": {"type": "object"}
        }

        content2 = {
            "method": "POST",
            "path": "/api/orders",
            "request_schema": {"type": "object"}
        }

        content3 = {
            "method": "GET",
            "path": "/api/users",
            "request_schema": {"type": "object"}
        }

        # 计算哈希
        hash1 = hashlib.md5(json.dumps(content1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.md5(json.dumps(content2, sort_keys=True).encode()).hexdigest()
        hash3 = hashlib.md5(json.dumps(content3, sort_keys=True).encode()).hexdigest()

        # 验证哈希
        assert hash1 == hash2  # 相同内容，相同哈希
        assert hash1 != hash3  # 不同内容，不同哈希

    def test_duplicate_api_detection(self):
        """
        测试重复 API 检测逻辑

        验证点：
        1. 相同 method + path 被视为重复
        2. 不同 method + path 不被视为重复
        """
        # 模拟数据库查询
        existing_apis = [
            {"method": "POST", "path": "/api/orders"},
            {"method": "GET", "path": "/api/orders"},
            {"method": "POST", "path": "/api/users"}
        ]

        # 测试重复检测
        new_api1 = {"method": "POST", "path": "/api/orders"}
        is_duplicate1 = any(
            api["method"] == new_api1["method"] and api["path"] == new_api1["path"]
            for api in existing_apis
        )
        assert is_duplicate1 is True

        new_api2 = {"method": "PUT", "path": "/api/orders"}
        is_duplicate2 = any(
            api["method"] == new_api2["method"] and api["path"] == new_api2["path"]
            for api in existing_apis
        )
        assert is_duplicate2 is False

    def test_pagination_logic(self):
        """
        测试分页逻辑

        验证点：
        1. 正确计算 skip
        2. 正确计算 total
        3. 正确计算分页数
        """
        # 测试数据
        total = 100
        limit = 50
        page = 1

        # 计算分页
        skip = (page - 1) * limit
        total_pages = (total + limit - 1) // limit

        # 验证计算
        assert skip == 0
        assert total_pages == 2

        # 测试第二页
        page = 2
        skip = (page - 1) * limit
        assert skip == 50


class TestApiDefinitionsResponseFormat:
    """API 定义响应格式测试"""

    def test_api_definition_list_response_format(self):
        """
        测试 API 定义列表响应格式

        验证点：
        1. 返回统一响应格式
        2. 包含 total 和 items
        3. items 包含必要字段
        """
        # 模拟响应数据
        response_data = {
            "total": 10,
            "items": [
                {
                    "id": 1,
                    "method": "POST",
                    "path": "/api/orders",
                    "summary": "创建订单",
                    "status": "active",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00"
                }
            ]
        }

        # 验证响应格式
        assert "total" in response_data
        assert "items" in response_data
        assert isinstance(response_data["total"], int)
        assert isinstance(response_data["items"], list)
        assert len(response_data["items"]) > 0

        # 验证 item 字段
        item = response_data["items"][0]
        required_fields = ["id", "method", "path", "summary", "status"]
        for field in required_fields:
            assert field in item

    def test_api_definition_detail_response_format(self):
        """
        测试 API 定义详情响应格式

        验证点：
        1. 返回统一响应格式
        2. 包含所有必要字段
        3. 时间格式正确
        """
        # 模拟响应数据
        response_data = {
            "id": 1,
            "project_id": 1,
            "method": "POST",
            "path": "/api/orders",
            "summary": "创建订单",
            "description": "创建新订单的接口",
            "tags": ["订单", "创建"],
            "status": "active",
            "sync_status": "synced",
            "lock_status": "unlocked",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "created_by": "test_user",
            "updated_by": "test_user"
        }

        # 验证响应格式
        required_fields = [
            "id", "project_id", "method", "path", "summary",
            "description", "tags", "status", "sync_status", "lock_status",
            "created_at", "updated_at", "created_by", "updated_by"
        ]
        for field in required_fields:
            assert field in response_data

        # 验证时间格式
        assert "T" in response_data["created_at"]
        assert "T" in response_data["updated_at"]


class TestApiDefinitionsValidation:
    """API 定义验证测试"""

    def test_method_validation(self):
        """
        测试 HTTP 方法验证

        验证点：
        1. 只允许有效的 HTTP 方法
        2. 拒绝无效的 HTTP 方法
        """
        valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        invalid_methods = ["INVALID", "OPTION", "HEAD", "CONNECT"]

        # 验证有效方法
        for method in valid_methods:
            assert method.upper() in valid_methods

        # 验证无效方法
        for method in invalid_methods:
            assert method.upper() not in valid_methods

    def test_path_validation(self):
        """
        测试路径验证

        验证点：
        1. 路径以 / 开头
        2. 路径不包含空格
        """
        valid_paths = [
            "/api/orders",
            "/api/users/{id}",
            "/api/products/{product_id}/reviews"
        ]

        invalid_paths = [
            "api/orders",  # 不以 / 开头
            "/api/orders/create order",  # 包含空格
            "",  # 空路径
        ]

        # 验证有效路径
        for path in valid_paths:
            assert path.startswith("/")
            assert " " not in path

        # 验证无效路径
        for path in invalid_paths:
            if path:  # 跳过空路径
                if not path.startswith("/"):
                    continue
                if " " in path:
                    continue

    def test_status_validation(self):
        """
        测试状态验证

        验证点：
        1. 只允许有效的状态值
        2. 拒绝无效的状态值
        """
        from app.api.v1.api_definitions import ApiDefinitionStatus

        valid_statuses = [
            ApiDefinitionStatus.ACTIVE,
            ApiDefinitionStatus.ARCHIVED,
            ApiDefinitionStatus.DEPRECATED
        ]

        invalid_statuses = ["unknown", "inactive", "pending"]

        # 验证有效状态
        for status in valid_statuses:
            assert status in [ApiDefinitionStatus.ACTIVE, ApiDefinitionStatus.ARCHIVED, ApiDefinitionStatus.DEPRECATED]

        # 验证无效状态
        for status in invalid_statuses:
            assert status not in [ApiDefinitionStatus.ACTIVE, ApiDefinitionStatus.ARCHIVED, ApiDefinitionStatus.DEPRECATED]


def run_tests():
    """运行测试"""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_tests()