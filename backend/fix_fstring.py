"""
修复 auth_service.py 中的 f-string 语法错误
"""
auth_service_path = 'app/core/auth_service.py'

with open(auth_service_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复 f-string 中的引号问题
content = content.replace(
    'f"未知的来源模式: {auth_config["source_mode"]}"',
    'f\'未知的来源模式: {auth_config["source_mode"]}\''
)

with open(auth_service_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print("✅ 修复 f-string 语法错误完成")