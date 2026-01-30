"""
更新 modules.py，集成 ModuleAnalyzerV2

将原有的 ModuleAnalyzer 替换为 ModuleAnalyzerV2
"""

import re

def update_modules_py():
    """更新 modules.py，集成 ModuleAnalyzerV2"""
    modules_file_path = r'D:\code\BugSeek\backend\app\api\v1\modules.py'
    
    with open(modules_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已更新
    if 'ModuleAnalyzerV2' in content:
        print("modules.py 已集成 ModuleAnalyzerV2，跳过")
        return
    
    # 替换导入语句
    content = content.replace(
        'from app.core.dependency import ModuleAnalyzer, ModuleDependencyAnalyzer',
        'from app.core.dependency import ModuleAnalyzerV2, ModuleDependencyAnalyzer'
    )
    
    # 替换使用 ModuleAnalyzer 的地方
    content = content.replace(
        'analyzer = ModuleAnalyzer(db)',
        'analyzer = ModuleAnalyzerV2(db)'
    )
    
    with open(modules_file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("modules.py 已更新，集成 ModuleAnalyzerV2")

if __name__ == "__main__":
    update_modules_py()