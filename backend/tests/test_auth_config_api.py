"""
鉴权配置 API 单元测试

符合后端代码规范：
1. 测试覆盖：所有 CRUD 接口
2. Mock 使用：隔离外部依赖
3. 断言清晰：明确的预期结果
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from fastapi import HTTPException
import asyncio

from app.api.v1.auth_config_append import (
    get_project_template,
    create_project_template,
    update_project_template,
    delete_project_template,
    get_environment_auth_config,
    create_environment_auth_config,
    update_environment_auth_config,
    delete_environment_auth_config
)
from app.domains.auth.schemas import (
    AuthConfigCreate,
    AuthConfigUpdate,
    ProjectAuthTemplateCreate,
    ProjectAuthTemplateUpdate,
    AuthTypeEnum,
    InjectionTargetEnum,
    SourceModeEnum,
    InjectionConfig
)
from app.platform.db.base import AuthConfig, ProjectAuthTemplate, Environment, Project


class TestAuthConfigAPI:
    """鉴权配置 API 测试"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock 数据库会话"""
        db = Mock(spec=Session)
        # 默认让 all() 返回空列表，避免 Mock 不可迭代
        db.query.return_value.filter.return_value.all.return_value = []
        # 默认让 filter 链式调用返回 self
        db.query.return_value.filter.return_value.filter.return_value = db.query.return_value.filter.return_value
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value = db.query.return_value.filter.return_value.filter.return_value
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None
        return db

    def _set_first_results(self, mock_db, *results):
        mock_db.query.return_value.filter.return_value.first.side_effect = list(results)
    
    @pytest.fixture
    def mock_user(self):
        """Mock 当前用户"""
        user = Mock()
        user.id = 1
        user.username = "test_user"
        return user
    
    @pytest.fixture
    def sample_project(self):
        """示例项目"""
        project = Mock()
        project.id = 1
        project.name = "Test Project"
        return project
    
    @pytest.fixture
    def sample_environment(self):
        """示例环境"""
        env = Mock()
        env.id = 1
        env.project_id = 1
        env.name = "Dev"
        env.base_url = "https://dev.example.com"
        return env
    
    @pytest.fixture
    def sample_template(self):
        """示例项目模板"""
        template = Mock()
        template.id = 1
        template.project_id = 1
        template.enabled = True
        template.auth_type = "bearer"
        template.injection_target = "header"
        template.injection_key = "Authorization"
        template.injection_template = "Bearer {{ACCESS_TOKEN}}"
        template.source_mode = "dynamic"
        template.static_value = None
        template.login_api_id = 1
        template.login_auth_type = "none"
        template.created_at = None
        template.updated_at = None
        return template
    
    @pytest.fixture
    def sample_project_template_data(self):
        """示例项目模板数据"""
        return ProjectAuthTemplateCreate(
            enabled=True,
            auth_type=AuthTypeEnum.BEARER,
            injection=InjectionConfig(
                target=InjectionTargetEnum.HEADER,
                key="Authorization",
                value_template="Bearer {{ACCESS_TOKEN}}"
            ),
            source_mode=SourceModeEnum.DYNAMIC,
            login_api_id=1,
            login_auth_type=AuthTypeEnum.NONE,
            input_mappings=[],
            extract_rules=[]
        )

    @pytest.fixture
    def sample_env_config_data(self):
        """示例环境配置数据"""
        return AuthConfigCreate(
            enabled=True,
            auth_type=AuthTypeEnum.BEARER,
            injection=InjectionConfig(
                target=InjectionTargetEnum.HEADER,
                key="Authorization",
                value_template="Bearer {{ACCESS_TOKEN}}"
            ),
            source_mode=SourceModeEnum.DYNAMIC,
            login_api_id=1,
            input_mappings=[],
            extract_rules=[]
        )
    
    # ==================== 获取鉴权配置测试 ====================
    
    def test_get_project_template_success(self, mock_db, sample_project, sample_template, mock_user):
        """测试获取项目模板成功"""
        # 设置 first 返回项目，然后返回模板
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, sample_template]
        
        result = asyncio.run(get_project_template(project_id=1, db=mock_db, current_user=mock_user))
        
        assert result["code"] == 0
        assert result["message"] == "获取成功"
        assert result["data"] is not None
    
    def test_get_project_template_not_found(self, mock_db, sample_project, mock_user):
        """测试项目模板不存在"""
        # 设置 first 返回项目，然后返回 None（模板不存在）
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, None]
        
        result = asyncio.run(get_project_template(project_id=1, db=mock_db, current_user=mock_user))
        
        assert result["code"] == 0
        assert result["message"] == "项目模板不存在"
        assert result["data"] is None
    
    def test_get_auth_config_project_not_found(self, mock_db, mock_user):
        """测试项目不存在"""
        # 设置 first 返回 None（项目不存在）
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_project_template(project_id=999, db=mock_db, current_user=mock_user))
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "项目不存在"
    
    def test_get_environment_config_success(self, mock_db, sample_project, sample_environment, sample_template, mock_user):
        """测试获取环境配置成功"""
        # 配置多个查询的返回值
        project_query = Mock()
        project_query.first.return_value = sample_project
        
        environment_query = Mock()
        environment_query.first.return_value = sample_environment
        
        config_query = Mock()
        config = Mock()
        config.id = 1
        config.environment_id = 1
        config.project_id = 1
        config.enabled = True
        config.auth_type = "bearer"
        config.inherit_from_project = True
        config.input_mappings = []
        config.extract_rules = []
        config_query.first.return_value = config
        
        # 配置 query 方法的 side_effect
        mock_db.query.side_effect = [project_query, environment_query, config_query]
        
        result = asyncio.run(get_environment_auth_config(project_id=1, environment_id=1, db=mock_db, current_user=mock_user))
        
        assert result["code"] == 0
        assert result["message"] == "获取成功"
        assert result["data"] is not None
    
    def test_get_environment_config_not_found(self, mock_db, sample_project, sample_environment, mock_user):
        """测试环境配置不存在"""
        # 设置 first 返回项目，然后返回环境
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, sample_environment]
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None
        
        result = asyncio.run(get_environment_auth_config(project_id=1, environment_id=1, db=mock_db, current_user=mock_user))
        
        assert result["code"] == 0
        assert result["message"] == "环境鉴权配置不存在"
        assert result["data"] is None
    
    def test_get_environment_config_env_not_found(self, mock_db, sample_project, mock_user):
        """测试环境不存在"""
        # 设置 first 返回项目，然后返回 None（环境不存在）
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, None]
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_environment_auth_config(project_id=1, environment_id=999, db=mock_db, current_user=mock_user))
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "环境不存在"
    
    # ==================== 创建项目模板测试 ====================
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_create_project_template_success(self, mock_trace_id, mock_db, sample_project, sample_project_template_data, mock_user):
        """测试创建项目模板成功"""
        mock_trace_id.return_value = "test-trace-id"
        # 设置 first 返回项目，然后返回 None（表示没有现有模板）
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, None]
        
        result = asyncio.run(create_project_template(
            project_id=1,
            template_data=sample_project_template_data,
            db=mock_db,
            current_user=mock_user
        ))
        
        assert result["code"] == 0
        assert result["message"] == "创建成功"
        assert result["data"] is not None
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_create_project_template_project_not_found(self, mock_trace_id, mock_db, sample_project_template_data, mock_user):
        """测试项目不存在"""
        mock_trace_id.return_value = "test-trace-id"
        self._set_first_results(mock_db, None)
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(create_project_template(
                project_id=999,
                template_data=sample_project_template_data,
                db=mock_db,
                current_user=mock_user
            ))
        
        assert exc_info.value.status_code == 404
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_create_project_template_already_exists(self, mock_trace_id, mock_db, sample_project, sample_template, sample_project_template_data, mock_user):
        """测试项目模板已存在"""
        mock_trace_id.return_value = "test-trace-id"
        self._set_first_results(mock_db, sample_project, sample_template)
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(create_project_template(
                project_id=1,
                template_data=sample_project_template_data,
                db=mock_db,
                current_user=mock_user
            ))
        
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "该项目已存在鉴权模板"
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_create_project_template_dynamic_mode_missing_api_id(self, mock_trace_id, mock_db, sample_project, mock_user):
        """测试动态模式缺少登录接口 ID"""
        mock_trace_id.return_value = "test-trace-id"
        # 设置 first 返回项目，然后返回 None（表示没有现有模板）
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, None]
        
        config_data = ProjectAuthTemplateCreate(
            enabled=True,
            auth_type=AuthTypeEnum.BEARER,
            injection=InjectionConfig(
                target=InjectionTargetEnum.HEADER,
                key="Authorization",
                value_template="Bearer {{ACCESS_TOKEN}}"
            ),
            source_mode=SourceModeEnum.DYNAMIC,
            login_api_id=None,
            login_auth_type=AuthTypeEnum.NONE,
            input_mappings=[],
            extract_rules=[]
        )
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(create_project_template(
                project_id=1,
                template_data=config_data,
                db=mock_db,
                current_user=mock_user
            ))
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "动态模式必须提供登录接口 ID"
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_create_project_template_static_mode_missing_value(self, mock_trace_id, mock_db, sample_project, mock_user):
        """测试静态模式缺少凭证值"""
        mock_trace_id.return_value = "test-trace-id"
        # 设置 first 返回项目，然后返回 None（表示没有现有模板）
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, None]
        
        config_data = ProjectAuthTemplateCreate(
            enabled=True,
            auth_type=AuthTypeEnum.BEARER,
            injection=InjectionConfig(
                target=InjectionTargetEnum.HEADER,
                key="Authorization",
                value_template="Bearer {{ACCESS_TOKEN}}"
            ),
            source_mode=SourceModeEnum.STATIC,
            static_value=None,
            login_auth_type=AuthTypeEnum.NONE,
            input_mappings=[],
            extract_rules=[]
        )
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(create_project_template(
                project_id=1,
                template_data=config_data,
                db=mock_db,
                current_user=mock_user
            ))
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "静态模式必须提供凭证值"
    
    # ==================== 更新项目模板测试 ====================
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_update_project_template_success(self, mock_trace_id, mock_db, sample_project, sample_template, sample_project_template_data, mock_user):
        """测试更新项目模板成功"""
        mock_trace_id.return_value = "test-trace-id"
        # 设置 first 返回项目，然后返回模板
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, sample_template]
        
        result = asyncio.run(update_project_template(
            project_id=1,
            template_data=ProjectAuthTemplateUpdate(**sample_project_template_data.dict()),
            db=mock_db,
            current_user=mock_user
        ))
        
        assert result["code"] == 0
        assert result["message"] == "更新成功"
    
    # ==================== 删除项目模板测试 ====================
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_delete_project_template_success(self, mock_trace_id, mock_db, sample_project, sample_template, mock_user):
        """测试删除项目模板成功"""
        mock_trace_id.return_value = "test-trace-id"
        self._set_first_results(mock_db, sample_project, sample_template)
        
        result = asyncio.run(delete_project_template(
            project_id=1,
            db=mock_db,
            current_user=mock_user
        ))
        
        assert result["code"] == 0
        assert result["message"] == "删除成功"
        assert result["data"] is None
    
    # ==================== 创建环境配置测试 ====================
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_create_environment_config_success(self, mock_trace_id, mock_db, sample_project, sample_environment, sample_env_config_data, mock_user):
        """测试创建环境配置成功"""
        mock_trace_id.return_value = "test-trace-id"
        # 设置 first 返回项目，然后返回环境
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, sample_environment]
        # 重置查询链，确保后续查询返回 None（没有现有配置）
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None
        
        result = asyncio.run(create_environment_auth_config(
            project_id=1,
            environment_id=1,
            config_data=sample_env_config_data,
            inherit_from_project=False,
            db=mock_db,
            current_user=mock_user
        ))
        
        assert result["code"] == 0
        assert result["message"] == "创建成功"
    
    # ==================== 更新环境配置测试 ====================
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_update_environment_config_success(self, mock_trace_id, mock_db, sample_project, sample_environment, sample_env_config_data, mock_user):
        """测试更新环境配置成功"""
        mock_trace_id.return_value = "test-trace-id"
        # 设置 first 返回项目，然后返回环境
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_project, sample_environment]
        
        config = Mock()
        config.id = 1
        config.enabled = True
        config.auth_type = "bearer"
        config.inherit_from_project = False
        config.input_mappings = []
        config.extract_rules = []
        
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = config
        
        result = asyncio.run(update_environment_auth_config(
            project_id=1,
            environment_id=1,
            config_data=sample_env_config_data,
            db=mock_db,
            current_user=mock_user
        ))
        
        assert result["code"] == 0
        assert result["message"] == "更新成功"
    
    # ==================== 删除环境配置测试 ====================
    
    @patch('app.api.v1.auth_config_append.get_trace_id')
    def test_delete_environment_config_success(self, mock_trace_id, mock_db, sample_project, sample_environment, mock_user):
        """测试删除环境配置成功"""
        mock_trace_id.return_value = "test-trace-id"
        self._set_first_results(mock_db, sample_project, sample_environment)
        
        config = Mock()
        config.id = 1
        config.environment_id = 1
        config.project_id = 1
        
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = config
        
        result = asyncio.run(delete_environment_auth_config(
            project_id=1,
            environment_id=1,
            db=mock_db,
            current_user=mock_user
        ))
        
        assert result["code"] == 0
        assert result["message"] == "删除成功"
