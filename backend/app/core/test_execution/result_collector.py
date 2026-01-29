"""结果收集器 - 负责收集和格式化执行结果"""
from typing import Dict, Any, Optional
import logging
import json
from app.db.base import ScriptExecution
from app.constants.script import ExecutionStatus

logger = logging.getLogger(__name__)


class ResultCollector:
    """结果收集器"""

    def __init__(self, execution_id: int):
        """
        初始化结果收集器
        
        Args:
            execution_id: 执行记录ID
        """
        self.execution_id = execution_id
        self.result = {
            'request': {},
            'response': {},
            'performance': {},
            'assertions': [],
        }

    def collect_request_info(
        self,
        request: Dict[str, Any],
        request_size: int
    ) -> None:
        """
        收集请求信息
        
        Args:
            request: 构建的请求字典
            request_size: 请求大小（字节）
        """
        self.result['request'] = {
            'url': request.get('url'),
            'method': request.get('method'),
            'headers': request.get('headers', {}),
            'body': request.get('json'),
            'size': request_size,
        }

    def collect_response_info(
        self,
        response,
        response_time_ms: int
    ) -> None:
        """
        收集响应信息
        
        Args:
            response: HTTP响应对象
            response_time_ms: 响应时间（毫秒）
        """
        # 计算响应大小
        response_size = 0
        try:
            response_text = response.text
            response_size = len(response_text.encode('utf-8'))
        except:
            pass
        
        # 解析响应体
        response_body = None
        try:
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                response_body = response.json()
            else:
                response_body = response.text
        except:
            response_body = response.text

        # 收集性能数据
        self.result['performance'] = {
            'response_time_ms': response_time_ms,
        }
        
        # 如果有性能数据（DNS、TCP、TLS等）
        if hasattr(response, 'elapsed'):
            elapsed = response.elapsed.total_seconds() * 1000
            self.result['performance']['elapsed_ms'] = elapsed
        
        # 收集响应信息
        self.result['response'] = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': response_body,
            'size': response_size,
            'response_time_ms': response_time_ms,
        }

    def collect_assertions(
        self,
        assertion_results: list
    ) -> None:
        """
        收集断言结果
        
        Args:
            assertion_results: 断言结果列表
        """
        self.result['assertions'] = assertion_results

    def get_execution_status(self) -> str:
        """
        根据断言结果确定执行状态
        
        Returns:
            执行状态
        """
        # 检查是否有响应错误
        if 'error' in self.result.get('response', {}):
            return ExecutionStatus.FAILED
        
        # 检查断言结果
        assertions = self.result.get('assertions', [])
        if not assertions:
            return ExecutionStatus.PASSED
        
        # 如果有断言失败，返回失败状态
        failed_assertions = [a for a in assertions if not a.get('passed', False)]
        if failed_assertions:
            return ExecutionStatus.FAILED
        
        return ExecutionStatus.PASSED

    def to_dict(self) -> Dict[str, Any]:
        """
        将结果转换为字典
        
        Returns:
            结果字典
        """
        return self.result

    def to_script_execution_dict(
        self,
        project_id: int,
        script_id: int,
        endpoint_id: int,
        environment_id: int,
        started_at,
        finished_at
    ) -> Dict[str, Any]:
        """
        将结果转换为 ScriptExecution 模型字典
        
        Args:
            project_id: 项目ID
            script_id: 脚本ID
            endpoint_id: 接口ID
            environment_id: 环境ID
            started_at: 开始时间
            finished_at: 结束时间
            
        Returns:
            ScriptExecution 模型字典
        """
        request_info = self.result.get('request', {})
        response_info = self.result.get('response', {})
        performance_info = self.result.get('performance', {})
        
        # 计算执行时长
        duration_ms = None
        if started_at and finished_at:
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        
        # 确定执行状态
        status = self.get_execution_status()
        
        # 构建数据字典
        return {
            'project_id': project_id,
            'script_id': script_id,
            'endpoint_id': endpoint_id,
            'environment_id': environment_id,
            'status': status,
            'duration_ms': duration_ms,
            
            # 请求信息
            'request_url': request_info.get('url'),
            'request_method': request_info.get('method'),
            'request_headers': request_info.get('headers'),
            'request_body': request_info.get('body'),
            'request_size': request_info.get('size'),
            
            # 响应信息
            'response_status_code': response_info.get('status_code'),
            'response_headers': response_info.get('headers'),
            'response_body': response_info.get('body'),
            'response_size': response_info.get('size'),
            'response_time_ms': performance_info.get('response_time_ms'),
            
            # 性能数据（预留）
            'dns_time_ms': performance_info.get('dns_time_ms'),
            'tcp_time_ms': performance_info.get('tcp_time_ms'),
            'tls_time_ms': performance_info.get('tls_time_ms'),
            'transfer_time_ms': performance_info.get('transfer_time_ms'),
            
            # 断言结果
            'assertion_results': self.result.get('assertions', []),
            
            # 错误信息
            'error_message': response_info.get('error'),
        }

    def get_error_message(self, exception: Exception) -> str:
        """
        获取错误信息
        
        Args:
            exception: 异常对象
            
        Returns:
            错误信息字符串
        """
        return f"{type(exception).__name__}: {str(exception)}"