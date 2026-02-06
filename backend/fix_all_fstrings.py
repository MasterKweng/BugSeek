"""
修复 auth_service.py 中所有的 f-string 语法错误
"""
auth_service_path = 'app/core/auth_service.py'

with open(auth_service_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换所有 f-string 中的字典访问
# 将 f"...{auth_config["xxx"]}..." 改为 f'...{auth_config["xxx"]}...'
import re

# 匹配模式: f"...{auth_config["xxx"]}..."
pattern = r'f"([^"]*)\{auth_config\["([^"]+)"\]\}([^"]*)"'
replacement = r"f'\1{auth_config["\2"]}\3'"

content = re.sub(pattern, replacement, content)

with open(auth_service_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print("✅ 修复所有 f-string 语法错误完成")