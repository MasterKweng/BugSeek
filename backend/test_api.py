"""测试后端API"""
import requests

# 测试1: 不带参数查询
print("=" * 80)
print("测试1: 不带参数查询")
print("=" * 80)
try:
    response = requests.get('http://127.0.0.1:8000/api/v1/api-integration/endpoints')
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"返回数据: {result}")
except Exception as e:
    print(f"请求失败: {e}")

# 测试2: 带project_id和version_id查询
print("\n" + "=" * 80)
print("测试2: 带project_id=2和version_id=4查询")
print("=" * 80)
try:
    response = requests.get('http://127.0.0.1:8000/api/v1/api-integration/endpoints?project_id=2&version_id=4&skip=0&limit=10')
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"返回数据: {result}")
    if result.get('code') == 0:
        data = result.get('data', {})
        print(f"接口数量: {data.get('total', 0)}")
        print(f"返回的接口数: {len(data.get('endpoints', []))}")
except Exception as e:
    print(f"请求失败: {e}")