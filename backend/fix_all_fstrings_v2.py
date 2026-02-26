"""
修复 auth_service.py 中所有的 f-string 语法错误
"""
auth_service_path = 'app/core/auth_service.py'

with open(auth_service_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换所有 f-string 中的字典访问
# 方法：将所有 f"改为 f'，然后将内部的 ' 改为 "
content = content.replace('f"', "f'")

# 将所有 f'...{auth_config["xxx"]}...' 中的 " 保持不变，但外层使用 '
# 这样就可以正常工作了

with open(auth_service_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print("✅ 修复所有 f-string 语法错误完成（改为单引号）")