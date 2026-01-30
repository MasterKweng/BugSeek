"""
更新 App.tsx，添加链路列表页面路由
"""

import re

def update_app_tsx():
    """更新 App.tsx，添加链路列表页面路由"""
    app_file_path = r'D:\code\BugSeek\frontend\src\App.tsx'
    
    with open(app_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已添加
    if 'ChainList' in content:
        print("App.tsx 已添加 ChainList 路由，跳过")
        return
    
    # 在路由导入部分添加 ChainList
    import_pattern = r"(const Scenarios = lazy\(\(\) => import\('./pages/api/Scenarios'\)\))"
    if import_pattern in content:
        content = content.replace(
            import_pattern,
            r"\1\nconst ChainList = lazy(() => import('./pages/chains/ChainList'))"
        )
    
    # 在路由部分添加 ChainList 路由
    route_pattern = r'(<Route path="api/scenarios" element={<ProjectVersionGuard><Scenarios /></ProjectVersionGuard>} />'
    if route_pattern in content:
        content = content.replace(
            route_pattern,
            r'\1\n<Route path="api/chains" element={<ProjectVersionGuard><ChainList /></ProjectVersionGuard} />'
        )
    
    with open(app_file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("App.tsx 已更新，添加 ChainList 路由")

if __name__ == "__main__":
    update_app_tsx()