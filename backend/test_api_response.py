"""
测试后端 API 返回的执行记录数据
"""
import requests
import json

def test_endpoint_executions():
    """测试接口执行记录 API"""

    # 假设接口 ID 为 2（根据前面的检查结果，GET /api/version-text）
    endpoint_id = 2
    url = f"http://localhost:8000/api/v1/api-integration/endpoints/{endpoint_id}/executions?limit=10"

    try:
        response = requests.get(url)
        print(f"状态码: {response.status_code}")
        print(f"\n完整响应:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        # 检查每条记录的 script_id 和 script_name
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0 and 'data' in data:
                executions = data['data'].get('executions', [])
                print(f"\n\n执行记录详情:")
                print("=" * 100)
                for i, exec_record in enumerate(executions, 1):
                    print(f"\n记录 {i}:")
                    print(f"  执行ID: {exec_record.get('id')}")
                    print(f"  脚本ID: {exec_record.get('script_id')}")
                    print(f"  脚本名称: {exec_record.get('script_name', '未设置')}")
                    print(f"  接口ID: {exec_record.get('endpoint_id')}")
                    print(f"  状态: {exec_record.get('status')}")
                    print(f"  创建时间: {exec_record.get('created_at')}")

    except Exception as e:
        print(f"请求失败: {e}")

def test_script_executions():
    """测试脚本执行记录 API"""

    # 测试脚本 ID 18
    script_id = 18
    url = f"http://localhost:8000/api/v1/api-integration/scripts/{script_id}/executions?limit=10"

    try:
        response = requests.get(url)
        print(f"\n\n{'='*100}")
        print(f"测试脚本执行记录 API (script_id={script_id})")
        print(f"{'='*100}")
        print(f"状态码: {response.status_code}")
        print(f"\n完整响应:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"请求失败: {e}")

if __name__ == "__main__":
    test_endpoint_executions()
    test_script_executions()