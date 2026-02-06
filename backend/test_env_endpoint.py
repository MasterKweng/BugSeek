"""
直接测试环境端点
"""
import requests

# 测试环境列表 API
url = "http://localhost:8000/api/v1/projects/1/environments"
headers = {
    "Content-Type": "application/json"
    # 注意：没有 token，会返回 401
}

try:
    response = requests.get(url, headers=headers, timeout=5)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text}")
except Exception as e:
    print(f"请求失败: {e}")

print("\n" + "="*50 + "\n")

# 测试带错误信息的响应
print("注意：如果没有提供 token，应该返回 401 未授权")
print("如果返回 200 但 items 为空，可能是数据库查询有问题")
print("如果返回 500，说明后端代码有错误")