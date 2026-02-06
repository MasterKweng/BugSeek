"""
按照方案一修改 AuthMiddleware，支持环境级别的 token 注入
"""
import sys
import os

# 读取原文件
auth_service_path = os.path.join(os.path.dirname(__file__), 'app', 'core', 'auth_service.py')

with open(auth_service_path, 'r', encoding='utf-8') as f:
    content = f.read()

# ==================== 修改 1: 添加导入 ====================
old_imports = '''from app.db.base import AuthConfig, AuthInputMapping, AuthExtractRule, Project'''
new_imports = '''from app.db.base import (
    AuthConfig, AuthInputMapping, AuthExtractRule, Project,
    ProjectAuthTemplate, ProjectAuthTemplateMapping, ProjectAuthTemplateRule
)'''
content = content.replace(old_imports, new_imports)

# ==================== 修改 2: 修改 __init__ 方法 ====================
old_init = '''    def __init__(self, db: Session):
        """
        初始化鉴权执行引擎
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()
        self._redis_client = None  # TODO: 替换为真实的 Redis 客户端
        self._http_client = AsyncClient(timeout=30.0)
        self._config_cache = {}  # 内存缓存：{ project_id: AuthConfig }'''

new_init = '''    def __init__(self, db: Session, environment_id: Optional[int] = None):
        """
        初始化鉴权执行引擎
        
        Args:
            db: 数据库会话
            environment_id: 环境 ID（可选，用于环境级鉴权配置）
        """
        self.db = db
        self.environment_id = environment_id  # 新增：支持环境级配置
        self.trace_id = get_trace_id()
        self._redis_client = None  # TODO: 替换为真实的 Redis 客户端
        self._http_client = AsyncClient(timeout=30.0)
        self._config_cache = {}  # 内存缓存：{ key: AuthConfig }'''

content = content.replace(old_init, new_init)

# ==================== 修改 3: 添加 _template_to_config 方法 ====================
# 在 get_auth_config 方法之前添加新方法
template_to_config_method = '''
    def _template_to_config(self, template: ProjectAuthTemplate) -> Dict[str, Any]:
        """
        将项目模板转换为兼容的配置字典
        
        Args:
            template: 项目模板对象
            
        Returns:
            Dict[str, Any]: 兼容的配置字典
        """
        return {
            "id": template.id,
            "project_id": template.project_id,
            "environment_id": None,
            "enabled": template.enabled,
            "auth_type": template.auth_type,
            "injection_target": template.injection_target,
            "injection_key": template.injection_key,
            "injection_template": template.injection_template,
            "source_mode": template.source_mode,
            "static_value": template.static_value,
            "login_api_id": template.login_api_id,
            "inherit_from_project": False,
            "input_mappings": [
                {
                    "param_location": mapping.param_location,
                    "param_key": mapping.param_key,
                    "param_value": mapping.param_value
                }
                for mapping in template.template_mappings
            ],
            "extract_rules": [
                {
                    "rule_name": rule.rule_name,
                    "extract_source": rule.extract_source,
                    "extract_expression": rule.extract_expression
                }
                for rule in template.template_rules
            ]
        }

'''

# 在 "async def get_auth_config" 之前插入
insert_point = content.find('    async def get_auth_config(')
if insert_point != -1:
    content = content[:insert_point] + template_to_config_method + '\n' + content[insert_point:]

# ==================== 修改 4: 修改 get_auth_config 方法 ====================
old_get_auth_config = '''    async def get_auth_config(self, project_id: int) -> Optional[AuthConfig]:
        """
        获取项目鉴权配置（带缓存）
        
        Args:
            project_id: 项目 ID
            
        Returns:
            Optional[AuthConfig]: 鉴权配置对象
        """
        # 先从缓存获取
        if project_id in self._config_cache:
            return self._config_cache[project_id]
        
        # 缓存未命中，从数据库查询
        auth_config = self.db.query(AuthConfig).filter(
            AuthConfig.project_id == project_id,
            AuthConfig.enabled == True
        ).first()
        
        # 存入缓存
        if auth_config:
            self._config_cache[project_id] = auth_config
        
        return auth_config'''

new_get_auth_config = '''    async def get_auth_config(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        获取鉴权配置（支持环境级和项目级）
        
        Args:
            project_id: 项目 ID
            
        Returns:
            Optional[Dict[str, Any]]: 鉴权配置字典
        """
        # 生成缓存键
        cache_key = f"{project_id}:{self.environment_id}" if self.environment_id else str(project_id)
        
        # 先从缓存获取
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        config = None
        
        # 如果有 environment_id，优先查询环境级配置
        if self.environment_id:
            env_config = self.db.query(AuthConfig).filter(
                AuthConfig.environment_id == self.environment_id,
                AuthConfig.enabled == True
            ).first()
            
            if env_config:
                config = {
                    "id": env_config.id,
                    "project_id": env_config.project_id,
                    "environment_id": env_config.environment_id,
                    "enabled": env_config.enabled,
                    "auth_type": env_config.auth_type,
                    "injection_target": env_config.injection_target,
                    "injection_key": env_config.injection_key,
                    "injection_template": env_config.injection_template,
                    "source_mode": env_config.source_mode,
                    "static_value": env_config.static_value,
                    "login_api_id": env_config.login_api_id,
                    "inherit_from_project": env_config.inherit_from_project,
                    "input_mappings": [
                        {
                            "param_location": mapping.param_location,
                            "param_key": mapping.param_key,
                            "param_value": mapping.param_value
                        }
                        for mapping in env_config.input_mappings
                    ],
                    "extract_rules": [
                        {
                            "rule_name": rule.rule_name,
                            "extract_source": rule.extract_source,
                            "extract_expression": rule.extract_expression
                        }
                        for rule in env_config.extract_rules
                    ]
                }
                logger.info(f"[{self.trace_id}] 使用环境级鉴权配置: environment_id={self.environment_id}")
        
        # 如果环境配置不存在或需要继承项目模板，查询项目模板
        if not config:
            template = self.db.query(ProjectAuthTemplate).filter(
                ProjectAuthTemplate.project_id == project_id,
                ProjectAuthTemplate.enabled == True
            ).first()
            
            if template:
                config = self._template_to_config(template)
                logger.info(f"[{self.trace_id}] 使用项目模板: project_id={project_id}")
        
        # 存入缓存
        if config:
            self._config_cache[cache_key] = config
        
        return config'''

content = content.replace(old_get_auth_config, new_get_auth_config)

# ==================== 修改 5: 修改 _handle_static_mode 以支持字典格式 ====================
# 将 auth_config.auth_type 改为 auth_config["auth_type"]
content = content.replace('auth_config.auth_type', 'auth_config["auth_type"]')
content = content.replace('auth_config.project_id', 'auth_config["project_id"]')
content = content.replace('auth_config.source_mode', 'auth_config["source_mode"]')
content = content.replace('auth_config.static_value', 'auth_config["static_value"]')
content = content.replace('auth_config.login_api_id', 'auth_config["login_api_id"]')

# ==================== 写回文件 ====================
with open(auth_service_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print("✅ AuthMiddleware 修改完成")
print("   - 添加了 environment_id 参数支持")
print("   - 添加了 _template_to_config 方法")
print("   - 修改了 get_auth_config 以支持环境级配置")
print("   - 配置返回格式统一为字典")