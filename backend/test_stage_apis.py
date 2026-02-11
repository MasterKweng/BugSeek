"""
测试阶段化API端点

验证新增的4个API端点是否正确注册
"""
import os
import sys

# 设置环境变量
os.environ.setdefault("ENVIRONMENT", "development")

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("测试阶段化API端点")
print("=" * 60)

# 直接检查路由定义
try:
    from app.api.v1 import field_mappings_async
    router = field_mappings_async.router
    
    # 获取路由列表
    routes = router.routes
    
    print(f"\n✅ 成功导入 field_mappings_async 路由器")
    print(f"路由数量: {len(routes)}")
    print(f"\nfield_mappings_async 路由器中的路由:")
    
    expected_routes = [
        ("GET", "/field-mappings/tasks/{task_id}/stage/{stage_num}"),
        ("POST", "/field-mappings/tasks/{task_id}/resume"),
        ("POST", "/field-mappings/tasks/{task_id}/retry/{stage_num}"),
        ("POST", "/field-mappings/tasks/{task_id}/reset")
    ]
    
    found_routes = []
    missing_routes = []
    
    for route in routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = list(route.methods) if route.methods else []
            path = route.path
            for method in methods:
                found_routes.append((method, path))
                print(f"  - {method:6} {path}")
    
    # 检查预期路由是否存在
    print(f"\n检查预期路由:")
    for method, path in expected_routes:
        if (method, path) in found_routes:
            print(f"  ✅ {method:6} {path}")
        else:
            print(f"  ❌ {method:6} {path} (未找到)")
            missing_routes.append((method, path))
    
    print("=" * 60)
    if missing_routes:
        print(f"❌ 缺失 {len(missing_routes)} 个路由")
        sys.exit(1)
    else:
        print("✅ 所有阶段化API端点已正确注册")
        sys.exit(0)
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
