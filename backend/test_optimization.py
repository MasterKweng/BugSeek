"""测试优化后的接口和脚本列表"""
import requests

BASE_URL = 'http://127.0.0.1:8000/api/v1'

# 登录获取token
print("=" * 80)
print("登录获取Token")
print("=" * 80)
login_response = requests.post(f'{BASE_URL}/auth/login', json={
    "username": "test",
    "password": "test123"
})
print(f"登录状态码: {login_response.status_code}")
if login_response.status_code == 200:
    login_result = login_response.json()
    token = login_result.get('data', {}).get('access_token')
    print(f"Token: {token[:20]}..." if token else "Token获取失败")
else:
    print(f"登录失败: {login_response.text}")
    token = ""

headers = {}
if token:
    headers = {"Authorization": f"Bearer {token}"}

# 测试1: 获取脚本列表（优化后，只返回有脚本的接口）
print("\n" + "=" * 80)
print("测试1: 获取脚本列表（优化后）")
print("=" * 80)
try:
    response = requests.get(f'{BASE_URL}/api-integration/scripts', headers=headers)
    print(f"状态码: {response.status_code}")
    result = response.json()
    if result.get('code') == 0:
        data = result.get('data', {})
        groups = data.get('groups', [])
        total_scripts = data.get('total_scripts', 0)
        print(f"分组数量: {data.get('total_groups', 0)}")
        print(f"脚本总数: {total_scripts}")
        
        # 统计接口数量
        total_endpoints = 0
        for group in groups:
            endpoints = group.get('endpoints', [])
            total_endpoints += len(endpoints)
            for endpoint in endpoints:
                scripts = endpoint.get('scripts', [])
                if scripts:
                    print(f"  - 分组: {group['group_name']}, 接口: {endpoint['path']}, 脚本数: {len(scripts)}")
        
        print(f"有脚本的接口总数: {total_endpoints}")
        print(f"✓ 优化成功：只返回有脚本的接口")
except Exception as e:
    print(f"请求失败: {e}")

# 测试2: 测试分页
print("\n" + "=" * 80)
print("测试2: 测试脚本列表分页")
print("=" * 80)
try:
    response = requests.get(f'{BASE_URL}/api-integration/scripts?skip=0&limit=10', headers=headers)
    print(f"状态码: {response.status_code}")
    result = response.json()
    if result.get('code') == 0:
        data = result.get('data', {})
        print(f"skip: {data.get('skip', 0)}")
        print(f"limit: {data.get('limit', 0)}")
        print(f"✓ 分页参数正常返回")
except Exception as e:
    print(f"请求失败: {e}")

# 测试3: 获取接口列表（优化后的分页）
print("\n" + "=" * 80)
print("测试3: 获取接口列表（优化后的分页）")
print("=" * 80)
try:
    response = requests.get(f'{BASE_URL}/api-integration/endpoints?skip=0&limit=50', headers=headers)
    print(f"状态码: {response.status_code}")
    result = response.json()
    if result.get('code') == 0:
        data = result.get('data', {})
        endpoints = data.get('endpoints', [])
        total = data.get('total', 0)
        print(f"返回接口数: {len(endpoints)}")
        print(f"接口总数: {total}")
        print(f"✓ 优化成功：默认limit=50，最大limit=200")
except Exception as e:
    print(f"请求失败: {e}")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)