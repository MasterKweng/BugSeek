#!/usr/bin/env python3
"""
BugSeek CLI - 场景触发脚本

BSK-SC-027: CLI 触发脚本

功能：
1. 触发场景执行
2. 支持同步/异步模式
3. 支持轮询获取结果
4. 返回标准退出码用于流水线门禁

使用方式：
```bash
# 同步模式
python trigger_scenario.py --base-url http://your-api.com --token your_api_key --scenario-id 123 --environment-id 456

# 异步模式
python trigger_scenario.py --base-url http://your-api.com --token your_api_key --scenario-id 123 --environment-id 456 --async-mode

# 异步模式 + 轮询
python trigger_scenario.py --base-url http://your-api.com --token your_api_key --scenario-id 123 --environment-id 456 --async-mode --poll

# 环境变量方式
export BUGSEEK_BASE_URL=http://your-api.com
export BUGSEEK_TOKEN=your_api_key
python trigger_scenario.py --scenario-id 123 --environment-id 456
```

退出码：
- 0: 执行成功
- 1: 执行失败
- 2: 参数错误
- 3: 网络错误
"""
import argparse
import sys
import os
import time
import json
from typing import Optional

try:
    import requests
except ImportError:
    print("错误: 缺少 requests 库，请运行: pip install requests")
    sys.exit(3)


class BugSeekCLI:
    """BugSeek CLI 客户端"""
    
    def __init__(self, base_url: str, token: str):
        """
        初始化客户端
        
        Args:
            base_url: API 基础 URL
            token: API Token
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': token,
            'Content-Type': 'application/json'
        })
    
    def trigger_scenario(
        self,
        scenario_id: int,
        environment_id: int,
        async_mode: bool = False,
        callback_url: Optional[str] = None
    ) -> dict:
        """
        触发场景执行
        
        Args:
            scenario_id: 场景 ID
            environment_id: 环境 ID
            async_mode: 是否异步执行
            callback_url: 回调 URL
            
        Returns:
            dict: 执行结果
        """
        url = f"{self.base_url}/api/v1/scenarios/{scenario_id}/trigger"
        
        payload = {
            "environment_id": environment_id,
            "async_mode": async_mode
        }
        
        if callback_url:
            payload["callback_url"] = callback_url
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()
    
    def get_execution_result(
        self,
        scenario_id: int,
        execution_id: int
    ) -> dict:
        """
        获取执行结果
        
        Args:
            scenario_id: 场景 ID
            execution_id: 执行 ID
            
        Returns:
            dict: 执行结果
        """
        url = f"{self.base_url}/api/v1/scenarios/{scenario_id}/trigger/{execution_id}"
        
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def poll_execution_result(
        self,
        scenario_id: int,
        execution_id: int,
        max_attempts: int = 60,
        poll_interval: int = 5
    ) -> dict:
        """
        轮询获取执行结果
        
        Args:
            scenario_id: 场景 ID
            execution_id: 执行 ID
            max_attempts: 最大轮询次数
            poll_interval: 轮询间隔（秒）
            
        Returns:
            dict: 执行结果
        """
        for attempt in range(max_attempts):
            result = self.get_execution_result(scenario_id, execution_id)
            
            status = result['data']['status']
            
            if status in ['completed', 'failed', 'success']:
                return result
            
            print(f"等待中... ({attempt + 1}/{max_attempts})")
            time.sleep(poll_interval)
        
        raise TimeoutError(f"轮询超时: {max_attempts * poll_interval} 秒")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='BugSeek CLI - 场景触发脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  %(prog)s --scenario-id 123 --environment-id 456
  %(prog)s --scenario-id 123 --environment-id 456 --async-mode
  %(prog)s --scenario-id 123 --environment-id 456 --async-mode --poll
        """
    )
    
    # 必需参数
    parser.add_argument(
        '--scenario-id',
        type=int,
        required=True,
        help='场景 ID'
    )
    parser.add_argument(
        '--environment-id',
        type=int,
        required=True,
        help='环境 ID'
    )
    
    # 连接参数（可通过环境变量设置）
    parser.add_argument(
        '--base-url',
        type=str,
        default=os.getenv('BUGSEEK_BASE_URL'),
        help='API 基础 URL（默认: BUGSEEK_BASE_URL 环境变量）'
    )
    parser.add_argument(
        '--token',
        type=str,
        default=os.getenv('BUGSEEK_TOKEN'),
        help='API Token（默认: BUGSEEK_TOKEN 环境变量）'
    )
    
    # 可选参数
    parser.add_argument(
        '--async-mode',
        action='store_true',
        help='异步执行模式'
    )
    parser.add_argument(
        '--callback-url',
        type=str,
        help='异步回调 URL'
    )
    parser.add_argument(
        '--poll',
        action='store_true',
        help='轮询获取结果（仅在异步模式下有效）'
    )
    parser.add_argument(
        '--poll-interval',
        type=int,
        default=5,
        help='轮询间隔（秒，默认: 5）'
    )
    parser.add_argument(
        '--max-poll-attempts',
        type=int,
        default=60,
        help='最大轮询次数（默认: 60）'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='详细输出'
    )
    
    args = parser.parse_args()
    
    # 验证参数
    if not args.base_url:
        print("错误: 缺少 base_url，请通过 --base-url 参数或 BUGSEEK_BASE_URL 环境变量设置")
        sys.exit(2)
    
    if not args.token:
        print("错误: 缺少 token，请通过 --token 参数或 BUGSEEK_TOKEN 环境变量设置")
        sys.exit(2)
    
    # 创建客户端
    cli = BugSeekCLI(args.base_url, args.token)
    
    try:
        # 触发场景
        if args.verbose:
            print(f"触发场景: scenario_id={args.scenario_id}, environment_id={args.environment_id}")
            print(f"模式: {'异步' if args.async_mode else '同步'}")
        
        result = cli.trigger_scenario(
            scenario_id=args.scenario_id,
            environment_id=args.environment_id,
            async_mode=args.async_mode,
            callback_url=args.callback_url
        )
        
        if args.verbose:
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if result['code'] != 0:
            print(f"错误: {result['message']}")
            sys.exit(1)
        
        data = result['data']
        
        if data['async_mode']:
            # 异步模式
            print(f"异步任务已提交: execution_id={data['execution_id']}")
            
            if args.poll:
                # 轮询获取结果
                print(f"轮询获取结果...")
                result = cli.poll_execution_result(
                    scenario_id=args.scenario_id,
                    execution_id=data['execution_id'],
                    max_attempts=args.max_poll_attempts,
                    poll_interval=args.poll_interval
                )
                
                if args.verbose:
                    print(f"最终结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                if result['code'] != 0:
                    print(f"错误: {result['message']}")
                    sys.exit(1)
                
                execution_data = result['data']
                summary = execution_data.get('summary', {})
                
                print(f"\n执行结果:")
                print(f"  状态: {execution_data['status']}")
                print(f"  总节点数: {summary.get('total', 0)}")
                print(f"  成功: {summary.get('passed', 0)}")
                print(f"  失败: {summary.get('failed', 0)}")
                print(f"  跳过: {summary.get('skipped', 0)}")
                print(f"  耗时: {summary.get('duration_ms', 0)}ms")
                
                # 判断退出码
                if execution_data['status'] == 'completed' and summary.get('failed', 0) == 0:
                    print("\n✓ 执行成功")
                    sys.exit(0)
                else:
                    print("\n✗ 执行失败")
                    sys.exit(1)
            else:
                # 异步模式但不轮询
                print(f"提示: 使用 --poll 参数轮询获取结果")
                print(f"执行 ID: {data['execution_id']}")
                sys.exit(0)
        else:
            # 同步模式
            summary = data['summary']
            
            print(f"\n执行结果:")
            print(f"  状态: {data['status']}")
            print(f"  总节点数: {summary.get('total', 0)}")
            print(f"  成功: {summary.get('passed', 0)}")
            print(f"  失败: {summary.get('failed', 0)}")
            print(f"  跳过: {summary.get('skipped', 0)}")
            print(f"  耗时: {summary.get('duration_ms', 0)}ms")
            
            # 判断退出码
            if data['status'] == 'completed' and summary.get('failed', 0) == 0:
                print("\n✓ 执行成功")
                sys.exit(0)
            else:
                print("\n✗ 执行失败")
                sys.exit(1)
                
    except requests.exceptions.RequestException as e:
        print(f"网络错误: {str(e)}")
        sys.exit(3)
    except TimeoutError as e:
        print(f"超时错误: {str(e)}")
        sys.exit(3)
    except Exception as e:
        print(f"未知错误: {str(e)}")
        sys.exit(3)


if __name__ == '__main__':
    main()