"""
按照方案一修改 AuthMiddleware，支持环境级别的 token 注入（谨慎版）
"""
import sys
import os

# 读取原文件
auth_service_path = os.path.join(os.path.dirname(__file__), 'app', 'core', 'auth_service.py')

with open(auth_service_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    
    # ==================== 修改 1: 添加导入 ====================
    if 'from app.db.base import AuthConfig, AuthInputMapping, AuthExtractRule, Project' in line:
        new_lines.append('from app.db.base import (\n')
        new_lines.append('    AuthConfig, AuthInputMapping, AuthExtractRule, Project,\n')
        new_lines.append('    ProjectAuthTemplate, ProjectAuthTemplateMapping, ProjectAuthTemplateRule\n')
        new_lines.append(')\n')
        i += 1
        continue
    
    # ==================== 修改 2: 修改 __init__ 方法 ====================
    if 'def __init__(self, db: Session):' in line:
        new_lines.append('    def __init__(self, db: Session, environment_id: Optional[int] = None):\n')
        i += 1
        # 修改下一行的文档字符串
        new_lines.append('        """\n')
        new_lines.append('        初始化鉴权执行引擎\n')
        new_lines.append('        \n')
        new_lines.append('        Args:\n')
        new_lines.append('            db: 数据库会话\n')
        new_lines.append('            environment_id: 环境 ID（可选，用于环境级鉴权配置）\n')
        new_lines.append('        """\n')
        i += 7  # 跳过原来的文档字符串
        continue
    
    if 'self.db = db' in line and i > 0 and 'def __init__' in ''.join(lines[max(0, i-20):i]):
        new_lines.append('        self.db = db\n')
        new_lines.append('        self.environment_id = environment_id  # 新增：支持环境级配置\n')
        i += 1
        continue
    
    if '_config_cache = {}' in line and i > 0 and 'def __init__' in ''.join(lines[max(0, i-20):i]):
        new_lines.append('        self._config_cache = {}  # 内存缓存：{ key: AuthConfig }\n')
        i += 1
        continue
    
    # ==================== 修改 3: 添加 _template_to_config 方法 ====================
    if 'async def get_auth_config(' in line:
        # 在 get_auth_config 之前插入新方法
        new_lines.append('\n')
        new_lines.append('    def _template_to_config(self, template: ProjectAuthTemplate) -> Dict[str, Any]:\n')
        new_lines.append('        """\n')
        new_lines.append('        将项目模板转换为兼容的配置字典\n')
        new_lines.append('        \n')
        new_lines.append('        Args:\n')
        new_lines.append('            template: 项目模板对象\n')
        new_lines.append('            \n')
        new_lines.append('        Returns:\n')
        new_lines.append('            Dict[str, Any]: 兼容的配置字典\n')
        new_lines.append('        """\n')
        new_lines.append('        return {\n')
        new_lines.append('            "id": template.id,\n')
        new_lines.append('            "project_id": template.project_id,\n')
        new_lines.append('            "environment_id": None,\n')
        new_lines.append('            "enabled": template.enabled,\n')
        new_lines.append('            "auth_type": template.auth_type,\n')
        new_lines.append('            "injection_target": template.injection_target,\n')
        new_lines.append('            "injection_key": template.injection_key,\n')
        new_lines.append('            "injection_template": template.injection_template,\n')
        new_lines.append('            "source_mode": template.source_mode,\n')
        new_lines.append('            "static_value": template.static_value,\n')
        new_lines.append('            "login_api_id": template.login_api_id,\n')
        new_lines.append('            "inherit_from_project": False,\n')
        new_lines.append('            "input_mappings": [\n')
        new_lines.append('                {\n')
        new_lines.append('                    "param_location": mapping.param_location,\n')
        new_lines.append('                    "param_key": mapping.param_key,\n')
        new_lines.append('                    "param_value": mapping.param_value\n')
        new_lines.append('                }\n')
        new_lines.append('                for mapping in template.template_mappings\n')
        new_lines.append('            ],\n')
        new_lines.append('            "extract_rules": [\n')
        new_lines.append('                {\n')
        new_lines.append('                    "rule_name": rule.rule_name,\n')
        new_lines.append('                    "extract_source": rule.extract_source,\n')
        new_lines.append('                    "extract_expression": rule.extract_expression\n')
        new_lines.append('                }\n')
        new_lines.append('                for rule in template.template_rules\n')
        new_lines.append('            ]\n')
        new_lines.append('        }\n')
        new_lines.append('\n')
        # 然后继续添加 get_auth_config
        new_lines.append(line)
        i += 1
        continue
    
    # ==================== 修改 4: 修改 get_auth_config 方法签名 ====================
    if 'async def get_auth_config(self, project_id: int) -> Optional[AuthConfig]:' in line:
        new_lines.append('    async def get_auth_config(self, project_id: int) -> Optional[Dict[str, Any]]:\n')
        i += 1
        continue
    
    # ==================== 修改 5: 修改 get_auth_config 的文档字符串 ====================
    if 'Optional[AuthConfig]: 鉴权配置对象' in line:
        new_lines.append('        Returns:\n')
        new_lines.append('            Optional[Dict[str, Any]]: 鉴权配置字典\n')
        i += 2
        continue
    
    # ==================== 修改 6: 重写 get_auth_config 方法体 ====================
    if '# 先从缓存获取' in line and 'get_auth_config' in ''.join(lines[max(0, i-20):i]):
        # 找到 get_auth_config 方法的开始，重写整个方法体
        # 跳过原来的方法体，直接插入新的实现
        new_lines.append('        # 生成缓存键\n')
        new_lines.append('        cache_key = f"{project_id}:{self.environment_id}" if self.environment_id else str(project_id)\n')
        new_lines.append('        \n')
        new_lines.append('        # 先从缓存获取\n')
        new_lines.append('        if cache_key in self._config_cache:\n')
        new_lines.append('            return self._config_cache[cache_key]\n')
        new_lines.append('        \n')
        new_lines.append('        config = None\n')
        new_lines.append('        \n')
        new_lines.append('        # 如果有 environment_id，优先查询环境级配置\n')
        new_lines.append('        if self.environment_id:\n')
        new_lines.append('            env_config = self.db.query(AuthConfig).filter(\n')
        new_lines.append('                AuthConfig.environment_id == self.environment_id,\n')
        new_lines.append('                AuthConfig.enabled == True\n')
        new_lines.append('            ).first()\n')
        new_lines.append('            \n')
        new_lines.append('            if env_config:\n')
        new_lines.append('                config = {\n')
        new_lines.append('                    "id": env_config.id,\n')
        new_lines.append('                    "project_id": env_config.project_id,\n')
        new_lines.append('                    "environment_id": env_config.environment_id,\n')
        new_lines.append('                    "enabled": env_config.enabled,\n')
        new_lines.append('                    "auth_type": env_config.auth_type,\n')
        new_lines.append('                    "injection_target": env_config.injection_target,\n')
        new_lines.append('                    "injection_key": env_config.injection_key,\n')
        new_lines.append('                    "injection_template": env_config.injection_template,\n')
        new_lines.append('                    "source_mode": env_config.source_mode,\n')
        new_lines.append('                    "static_value": env_config.static_value,\n')
        new_lines.append('                    "login_api_id": env_config.login_api_id,\n')
        new_lines.append('                    "inherit_from_project": env_config.inherit_from_project,\n')
        new_lines.append('                    "input_mappings": [\n')
        new_lines.append('                        {\n')
        new_lines.append('                            "param_location": mapping.param_location,\n')
        new_lines.append('                            "param_key": mapping.param_key,\n')
        new_lines.append('                            "param_value": mapping.param_value\n')
        new_lines.append('                        }\n')
        new_lines.append('                        for mapping in env_config.input_mappings\n')
        new_lines.append('                    ],\n')
        new_lines.append('                    "extract_rules": [\n')
        new_lines.append('                        {\n')
        new_lines.append('                            "rule_name": rule.rule_name,\n')
        new_lines.append('                            "extract_source": rule.extract_source,\n')
        new_lines.append('                            "extract_expression": rule.extract_expression\n')
        new_lines.append('                        }\n')
        new_lines.append('                        for rule in env_config.extract_rules\n')
        new_lines.append('                    ]\n')
        new_lines.append('                }\n')
        new_lines.append(f'                logger.info(f"使用环境级鉴权配置: environment_id={{self.environment_id}}")\n')
        new_lines.append('        \n')
        new_lines.append('        # 如果环境配置不存在或需要继承项目模板，查询项目模板\n')
        new_lines.append('        if not config:\n')
        new_lines.append('            template = self.db.query(ProjectAuthTemplate).filter(\n')
        new_lines.append('                ProjectAuthTemplate.project_id == project_id,\n')
        new_lines.append('                ProjectAuthTemplate.enabled == True\n')
        new_lines.append('            ).first()\n')
        new_lines.append('            \n')
        new_lines.append('            if template:\n')
        new_lines.append('                config = self._template_to_config(template)\n')
        new_lines.append(f'                logger.info(f"使用项目模板: project_id={{project_id}}")\n')
        new_lines.append('        \n')
        new_lines.append('        # 存入缓存\n')
        new_lines.append('        if config:\n')
        new_lines.append('            self._config_cache[cache_key] = config\n')
        new_lines.append('        \n')
        new_lines.append('        return config\n')
        new_lines.append('\n')
        
        # 跳过原来的方法体（直到下一个方法）
        i += 1
        while i < len(lines) and not lines[i].strip().startswith('async def ') and not lines[i].strip().startswith('def '):
            i += 1
        continue
    
    # ==================== 修改 7: 修改其他方法以使用字典格式 ====================
    if 'auth_config.auth_type' in line:
        new_lines.append(line.replace('auth_config.auth_type', 'auth_config["auth_type"]'))
        i += 1
        continue
    
    if 'auth_config.project_id' in line and 'auth_config.auth_type' not in line:
        new_lines.append(line.replace('auth_config.project_id', 'auth_config["project_id"]'))
        i += 1
        continue
    
    if 'auth_config.source_mode' in line and 'auth_config.auth_type' not in line:
        new_lines.append(line.replace('auth_config.source_mode', 'auth_config["source_mode"]'))
        i += 1
        continue
    
    if 'auth_config.static_value' in line:
        new_lines.append(line.replace('auth_config.static_value', 'auth_config["static_value"]'))
        i += 1
        continue
    
    if 'auth_config.login_api_id' in line:
        new_lines.append(line.replace('auth_config.login_api_id', 'auth_config["login_api_id"]'))
        i += 1
        continue
    
    # 其他行保持不变
    new_lines.append(line)
    i += 1

# 写回文件
with open(auth_service_path, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(new_lines)

print("✅ AuthMiddleware 修改完成")
