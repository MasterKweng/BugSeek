"""
检查项目1的鉴权配置数据
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.db.base import AuthConfig, ProjectAuthTemplate

db = SessionLocal()

print("=== 检查项目1的鉴权配置 ===")

# 检查项目模板
template = db.query(ProjectAuthTemplate).filter(ProjectAuthTemplate.project_id == 1).first()
if template:
    print(f"\n✅ 项目模板存在:")
    print(f"   ID: {template.id}")
    print(f"   项目ID: {template.project_id}")
    print(f"   是否启用: {template.enabled}")
    print(f"   鉴权类型: {template.auth_type}")
    print(f"   来源模式: {template.source_mode}")
else:
    print(f"\n❌ 项目模板不存在")

# 检查项目级 AuthConfig（旧版本）
project_auth = db.query(AuthConfig).filter(
    AuthConfig.project_id == 1,
    AuthConfig.environment_id == None
).first()
if project_auth:
    print(f"\n✅ 项目级 AuthConfig 存在（旧版本）:")
    print(f"   ID: {project_auth.id}")
    print(f"   项目ID: {project_auth.project_id}")
    print(f"   环境ID: {project_auth.environment_id}")
    print(f"   是否启用: {project_auth.enabled}")
else:
    print(f"\n❌ 项目级 AuthConfig 不存在")

# 检查环境级 AuthConfig
env_auths = db.query(AuthConfig).filter(
    AuthConfig.project_id == 1,
    AuthConfig.environment_id != None
).all()
if env_auths:
    print(f"\n✅ 环境级 AuthConfig 存在 ({len(env_auths)}个):")
    for auth in env_auths:
        print(f"   ID: {auth.id}, 环境ID: {auth.environment_id}, 是否启用: {auth.enabled}")
else:
    print(f"\n❌ 环境级 AuthConfig 不存在")

# 检查所有环境的环境ID
from app.db.base import Environment
envs = db.query(Environment).filter(Environment.project_id == 1).all()
if envs:
    print(f"\n📋 项目1的环境列表:")
    for env in envs:
        print(f"   ID: {env.id}, 名称: {env.name}")
else:
    print(f"\n❌ 项目1没有环境")

db.close()
