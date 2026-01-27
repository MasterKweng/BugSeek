"""测试接口分组功能"""
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

# 测试1: 获取接口分组列表
print("=" * 80)
print("测试1: 获取接口分组列表")
print("=" * 80)
try:
    response = requests.get(f'{BASE_URL}/api-integration/endpoints/groups', headers=headers)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"返回数据: {result}")
    if result.get('code') == 0:
        data = result.get('data', {})
        groups = data.get('groups', [])
        print(f"分组数量: {data.get('total', 0)}")
        print(f"分组列表:")
        for group in groups:
            print(f"  - ID: {group['id']}, 名称: {group['name']}")
            # 检查是否有未分组虚拟分组
            if group['id'] == 0:
                print(f"    ✓ 找到'未分组'虚拟分组")
except Exception as e:
    print(f"请求失败: {e}")

# 测试2: 获取脚本列表（按分组组织）
print("\n" + "=" * 80)
print("测试2: 获取脚本列表（按分组组织）")
print("=" * 80)
try:
    response = requests.get(f'{BASE_URL}/api-integration/scripts', headers=headers)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"返回数据: {result}")
    if result.get('code') == 0:
        data = result.get('data', {})
        groups = data.get('groups', [])
        print(f"分组数量: {data.get('total_groups', 0)}")
        print(f"脚本总数: {data.get('total_scripts', 0)}")
        print(f"分组列表:")
        for group in groups:
            print(f"  - ID: {group['group_id']}, 名称: {group['group_name']}, 接口数: {len(group['endpoints'])}")
            # 检查是否有未分组虚拟分组
            if group['group_id'] == 0:
                print(f"    ✓ 找到'未分组'虚拟分组")
                print(f"    未分组接口数: {len(group['endpoints'])}")
except Exception as e:
    print(f"请求失败: {e}")

# 测试3: 获取未分组的脚本
print("\n" + "=" * 80)
print("测试3: 获取未分组的脚本 (group_id=0)")
print("=" * 80)
try:
    response = requests.get(f'{BASE_URL}/api-integration/scripts?group_id=0', headers=headers)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"返回数据: {result}")
    if result.get('code') == 0:
        data = result.get('data', {})
        groups = data.get('groups', [])
        if groups:
            group = groups[0]
            print(f"分组名称: {group['group_name']}")
            print(f"接口数: {len(group['endpoints'])}")
            print(f"脚本总数: {data.get('total_scripts', 0)}")
except Exception as e:
    print(f"请求失败: {e}")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)