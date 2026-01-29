"""断言验证器 - 负责验证断言条件"""
from typing import Dict, Any, List
import logging
from app.constants.script import AssertionType

logger = logging.getLogger(__name__)


class AssertionChecker:
    """断言验证器"""

    def __init__(self, assertions: List[Dict[str, Any]]):
        """
        初始化断言验证器
        
        Args:
            assertions: 断言列表
        """
        self.assertions = assertions or []

    def check(self, response_status_code: int, response_body: Any) -> List[Dict[str, Any]]:
        """
        验证所有断言
        
        Args:
            response_status_code: 响应状态码
            response_body: 响应体
            
        Returns:
            断言结果列表
        """
        results = []
        
        for assertion in self.assertions:
            result = self._check_single_assertion(
                assertion,
                response_status_code,
                response_body
            )
            results.append(result)
        
        return results

    def _check_single_assertion(
        self,
        assertion: Dict[str, Any],
        response_status_code: int,
        response_body: Any
    ) -> Dict[str, Any]:
        """
        验证单个断言
        
        Args:
            assertion: 断言配置
            response_status_code: 响应状态码
            response_body: 响应体
            
        Returns:
            断言结果
        """
        assertion_type = assertion.get('type')
        description = assertion.get('description', '')
        
        try:
            if assertion_type == AssertionType.STATUS_CODE:
                passed = self._check_status_code(
                    assertion,
                    response_status_code
                )
            elif assertion_type == AssertionType.JSON_PATH:
                passed = self._check_json_path(
                    assertion,
                    response_body
                )
            elif assertion_type == AssertionType.CONTAINS:
                passed = self._check_contains(
                    assertion,
                    response_body
                )
            elif assertion_type == AssertionType.EQUALS:
                passed = self._check_equals(
                    assertion,
                    response_body
                )
            elif assertion_type == AssertionType.NOT_EQUALS:
                passed = self._check_not_equals(
                    assertion,
                    response_body
                )
            elif assertion_type == AssertionType.REGEX:
                passed = self._check_regex(
                    assertion,
                    response_body
                )
            elif assertion_type == AssertionType.RESPONSE_TIME:
                # 响应时间断言在外部处理
                passed = True
            else:
                logger.warning(f"未知的断言类型: {assertion_type}")
                passed = False
            
            return {
                'type': assertion_type,
                'description': description,
                'passed': passed,
                'expected': assertion.get('expected'),
                'actual': self._get_actual_value(
                    assertion_type,
                    assertion,
                    response_status_code,
                    response_body
                ),
                'error': None,
            }
        
        except Exception as e:
            logger.error(f"断言验证失败: {str(e)}", exc_info=True)
            return {
                'type': assertion_type,
                'description': description,
                'passed': False,
                'expected': assertion.get('expected'),
                'actual': None,
                'error': str(e),
            }

    def _check_status_code(
        self,
        assertion: Dict[str, Any],
        response_status_code: int
    ) -> bool:
        """检查状态码"""
        expected_status = assertion.get('expected')
        
        # 支持范围和多个值
        if isinstance(expected_status, list):
            return response_status_code in expected_status
        elif isinstance(expected_status, dict) and 'min' in expected_status and 'max' in expected_status:
            return expected_status['min'] <= response_status_code <= expected_status['max']
        else:
            return response_status_code == expected_status

    def _check_json_path(
        self,
        assertion: Dict[str, Any],
        response_body: Any
    ) -> bool:
        """检查JSON路径"""
        path = assertion.get('path')
        expected = assertion.get('expected')
        operator = assertion.get('operator', '==')  # ==, !=, >, <, >=, <=, in, not in
        
        # 获取实际值
        actual = self._get_value_by_json_path(response_body, path)
        
        # 比较操作
        if operator == '==':
            return actual == expected
        elif operator == '!=':
            return actual != expected
        elif operator == '>':
            return actual > expected
        elif operator == '<':
            return actual < expected
        elif operator == '>=':
            return actual >= expected
        elif operator == '<=':
            return actual <= expected
        elif operator == 'in':
            return actual in expected
        elif operator == 'not in':
            return actual not in expected
        else:
            logger.warning(f"未知的操作符: {operator}")
            return False

    def _check_contains(
        self,
        assertion: Dict[str, Any],
        response_body: Any
    ) -> bool:
        """检查包含关系"""
        expected = assertion.get('expected')
        
        if isinstance(response_body, str):
            return expected in response_body
        elif isinstance(response_body, dict):
            import json
            return expected in json.dumps(response_body)
        else:
            return expected in str(response_body)

    def _check_equals(
        self,
        assertion: Dict[str, Any],
        response_body: Any
    ) -> bool:
        """检查相等"""
        expected = assertion.get('expected')
        path = assertion.get('path')
        
        if path:
            actual = self._get_value_by_json_path(response_body, path)
        else:
            actual = response_body
        
        return actual == expected

    def _check_not_equals(
        self,
        assertion: Dict[str, Any],
        response_body: Any
    ) -> bool:
        """检查不等"""
        expected = assertion.get('expected')
        path = assertion.get('path')
        
        if path:
            actual = self._get_value_by_json_path(response_body, path)
        else:
            actual = response_body
        
        return actual != expected

    def _check_regex(
        self,
        assertion: Dict[str, Any],
        response_body: Any
    ) -> bool:
        """检查正则表达式"""
        pattern = assertion.get('expected')
        path = assertion.get('path')
        
        if path:
            actual = self._get_value_by_json_path(response_body, path)
        else:
            actual = str(response_body)
        
        import re
        return bool(re.search(pattern, str(actual)))

    def _get_value_by_json_path(
        self,
        data: Any,
        path: str
    ) -> Any:
        """
        根据JSON路径获取值
        
        Args:
            data: 数据对象
            path: JSON路径（如 data.users[0].name）
            
        Returns:
            路径对应的值
        """
        if not path:
            return data
        
        try:
            # 支持简单的路径解析，如 data.user.name
            keys = path.split('.')
            result = data
            
            for key in keys:
                # 处理数组索引，如 users[0]
                if '[' in key and key.endswith(']'):
                    index_key = key.split('[')[0]
                    index = int(key.split('[')[1].split(']')[0])
                    result = result.get(index_key, [])
                    if isinstance(result, list) and len(result) > index:
                        result = result[index]
                    else:
                        return None
                else:
                    if isinstance(result, dict):
                        result = result.get(key)
                    else:
                        return None
                
                if result is None:
                    return None
            
            return result
        
        except Exception as e:
            logger.error(f"解析JSON路径失败: {path}, error: {str(e)}")
            return None

    def _get_actual_value(
        self,
        assertion_type: str,
        assertion: Dict[str, Any],
        response_status_code: int,
        response_body: Any
    ) -> Any:
        """
        获取实际值用于断言结果
        
        Args:
            assertion_type: 断言类型
            assertion: 断言配置
            response_status_code: 响应状态码
            response_body: 响应体
            
        Returns:
            实际值
        """
        if assertion_type == AssertionType.STATUS_CODE:
            return response_status_code
        elif assertion_type in [AssertionType.JSON_PATH, AssertionType.EQUALS, AssertionType.NOT_EQUALS]:
            path = assertion.get('path')
            if path:
                return self._get_value_by_json_path(response_body, path)
            else:
                return response_body
        elif assertion_type in [AssertionType.CONTAINS, AssertionType.REGEX]:
            return str(response_body)
        else:
            return None

    def get_assertion_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取断言摘要
        
        Args:
            results: 断言结果列表
            
        Returns:
            断言摘要
        """
        total = len(results)
        passed = sum(1 for r in results if r.get('passed', False))
        failed = total - passed
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
        }