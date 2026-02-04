"""用例执行引擎（V2.0 层级一 - API 资产库）
符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. 全链路 TraceID：使用 get_trace_id()
3. 魔法值清理：使用枚举定义状态
4. 断言检查：支持多种断言类型
5. 变量提取：支持 JSON Path 提取
6. 自动鉴权：支持项目级别鉴权策略，自动获取并注入 Token
"""
import json
import time
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)


class ExecutionStatus:
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class AssertionOperator:
    """断言操作符枚举"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    TYPE_IS = "type_is"
    NOT_EMPTY = "not_empty"


class AssertionSource:
    """断言来源枚举"""
    STATUS = "status"
    HEADER = "header"
    BODY = "body"
    RESPONSE_TIME = "response_time"


class AuthType:
    """鉴权类型枚举"""
    BEARER = "bearer"
    API_KEY = "api_key"
    CUSTOM = "custom"


class AuthManager:
    """自动鉴权管理器"""
    
    def __init__(self, db, project_id: int, environment: Any):
        self.db = db
        self.project_id = project_id
        self.environment = environment
        self.auth_config = None
        self.trace_id = f"auth_{int(time.time())}"
    
    async def get_auth_token(self) -> Optional[Dict[str, Any]]:
        """
        获取鉴权 Token
        
        Returns:
            Dict: { header_name: header_value } 或 None
        """
        try:
            # 1. 加载鉴权配置
            self._load_auth_config()
            
            if not self.auth_config or not self.auth_config.enabled:
                logger.debug(f"[{self.trace_id}] 鉴权未启用")
                return None
            
            # 2. 尝试从缓存获取 Token（暂未实现 Redis 缓存，直接登录）
            token = await self._perform_login()
            
            if token:
                # 3. 构建注入 Header
                header_name = self.auth_config.token_inject_header or "Authorization"
                inject_template = self.auth_config.token_inject_template or "Bearer {token}"
                header_value = inject_template.replace("{token}", token)
                
                logger.info(f"[{self.trace_id}] 获取鉴权 Token 成功: header={header_name}")
                return {header_name: header_value}
            
            return None
            
        except Exception as e:
            logger.error(f"[{self.trace_id}] 获取鉴权 Token 失败: {str(e)}")
            return None
    
    def _load_auth_config(self):
        """加载鉴权配置"""
        from app.db.base import ApiProjectAuthConfig
        
        self.auth_config = self.db.query(ApiProjectAuthConfig).filter(
            ApiProjectAuthConfig.project_id == self.project_id
        ).first()
    
    async def _perform_login(self) -> Optional[str]:
        """
        执行登录流程
        
        Returns:
            str: Token 或 None
        """
        if not self.auth_config or not self.auth_config.login_url:
            return None
        
        try:
            # 1. 构建登录请求
            login_url = self.auth_config.login_url
            login_method = self.auth_config.login_method or "POST"
            login_body_template = self.auth_config.login_body_template or {}
            
            # 2. 用环境变量替换模板
            env_variables = self.environment.variables or {}
            login_body = self._resolve_variables(login_body_template, env_variables)
            
            logger.debug(f"[{self.trace_id}] 执行登录: url={login_url}, method={login_method}")
            
            # 3. 发送登录请求
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=login_method,
                    url=login_url,
                    json=login_body,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    logger.error(f"[{self.trace_id}] 登录失败: status_code={response.status_code}")
                    return None
                
                # 4. 提取 Token
                response_body = response.json()
                token = self._extract_token(response_body)
                
                if token:
                    logger.info(f"[{self.trace_id}] 登录成功，Token 提取成功")
                else:
                    logger.warning(f"[{self.trace_id}] 登录成功，但无法提取 Token")
                
                return token
                
        except Exception as e:
            logger.error(f"[{self.trace_id}] 登录失败: {str(e)}")
            return None
    
    def _resolve_variables(self, template: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """解析变量"""
        result = {}
        
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                var_name = value[2:-2].strip()
                result[key] = variables.get(var_name, value)
            elif isinstance(value, dict):
                result[key] = self._resolve_variables(value, variables)
            else:
                result[key] = value
        
        return result
    
    def _extract_token(self, response_body: Dict[str, Any]) -> Optional[str]:
        """从响应中提取 Token"""
        if not self.auth_config or not self.auth_config.token_extract_expression:
            return None
        
        try:
            # 支持 JSONPath 表达式，如：$.data.token
            expression = self.auth_config.token_extract_expression
            
            # 简化版 JSONPath 实现
            if expression.startswith("$."):
                path_parts = expression[2:].split(".")
                value = response_body
                
                for part in path_parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        return None
                
                if isinstance(value, str):
                    return value
                
            return None
            
        except Exception as e:
            logger.error(f"[{self.trace_id}] Token 提取失败: {str(e)}")
            return None


class CaseExecutor:
    """用例执行引擎"""

    def __init__(self):
        self.http_client = None

    async def _get_http_client(self):
        """获取 HTTP 客户端（延迟初始化）"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self.http_client

    async def execute_case(
        self,
        case: Any,
        definition: Any,
        environment: Any,
        variables: Optional[Dict[str, Any]] = None,
        db: Optional[Any] = None,
        project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行单个用例

        Args:
            case: 用例对象
            definition: 接口定义对象
            environment: 环境对象
            variables: 变量字典
            db: 数据库会话（用于鉴权）
            project_id: 项目 ID（用于鉴权）

        Returns:
            Dict: 执行结果
        """
        start_time = time.time()

        result = {
            "case_id": case.id,
            "case_name": case.name,
            "status": ExecutionStatus.RUNNING,
            "start_time": start_time,
            "end_time": None,
            "response_time": None,
            "request": None,
            "response": None,
            "assertions": [],
            "extractions": {},
            "error": None
        }

        try:
            # 1. 获取鉴权 Token（V2.0 自动鉴权）
            auth_headers = {}
            if db and project_id:
                auth_manager = AuthManager(db, project_id, environment)
                auth_headers = await auth_manager.get_auth_token()
                if auth_headers:
                    logger.info(f"自动鉴权成功，将注入 Header: {list(auth_headers.keys())}")

            # 2. 构建请求参数
            request_data = self._build_request_data(
                case,
                definition,
                environment,
                variables or {},
                auth_headers  # 传入鉴权 Header
            )

            result["request"] = request_data

            # 3. 发送请求
            response_data = await self._send_request(request_data)
            result["response"] = response_data

            # 4. 检查断言
            assertion_results = self._check_assertions(
                case.assertion_rules or [],
                response_data
            )
            result["assertions"] = assertion_results

            # 5. 提取变量
            extractions = self._extract_variables(
                case.extraction_rules or [],
                response_data
            )
            result["extractions"] = extractions

            # 6. 判断执行状态
            all_passed = all(a["passed"] for a in assertion_results)
            result["status"] = ExecutionStatus.SUCCESS if all_passed else ExecutionStatus.FAILED

        except Exception as e:
            logger.error(f"用例执行失败: case_id={case.id}, error={str(e)}")
            result["status"] = ExecutionStatus.FAILED
            result["error"] = str(e)

        finally:
            result["end_time"] = time.time()
            result["response_time"] = int((result["end_time"] - start_time) * 1000)

        return result

    def _build_request_data(
        self,
        case: Any,
        definition: Any,
        environment: Any,
        variables: Dict[str, Any],
        auth_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        构建请求数据

        Args:
            case: 用例对象
            definition: 接口定义对象
            environment: 环境对象
            variables: 变量字典
            auth_headers: 鉴权 Header（V2.0 自动鉴权）

        Returns:
            Dict: 请求数据
        """
        # 基础 URL
        base_url = environment.base_url
        full_url = urljoin(base_url, definition.path)

        # 解析并应用变量
        request_body = self._resolve_variables(
            case.request_data or {},
            variables
        )

        # 替换路径参数
        if request_body.get("path_params"):
            for key, value in request_body["path_params"].items():
                full_url = full_url.replace(f"{{{key}}}", str(value))

        # 添加查询参数
        if request_body.get("query_params"):
            from urllib.parse import urlencode
            query_string = urlencode(request_body["query_params"])
            full_url = f"{full_url}?{query_string}"

        # 构建请求头（优先级：用例 Header > 环境全局 Header > 鉴权 Header > 默认 Header）
        headers = {}
        
        # 1. 添加鉴权 Header（最高优先级）
        if auth_headers:
            headers.update(auth_headers)
        
        # 2. 添加环境全局 Header
        if hasattr(environment, 'headers') and environment.headers:
            headers.update(environment.headers)
        
        # 3. 添加用例 Header
        if request_body.get("headers"):
            headers.update(request_body.get("headers"))
        
        # 4. 添加默认 Content-Type（如果未设置）
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        return {
            "method": definition.method,
            "url": full_url,
            "headers": headers,
            "body": request_body.get("body")
        }

    async def _send_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送 HTTP 请求

        Args:
            request_data: 请求数据

        Returns:
            Dict: 响应数据
        """
        client = await self._get_http_client()

        response = await client.request(
            method=request_data["method"],
            url=request_data["url"],
            headers=request_data["headers"],
            json=request_data["body"]
        )

        # 解析响应
        response_body = None
        try:
            response_body = response.json()
        except:
            response_body = response.text

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response_body
        }

    def _check_assertions(
        self,
        assertion_rules: List[Dict[str, Any]],
        response_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        检查断言

        Args:
            assertion_rules: 断言规则列表
            response_data: 响应数据

        Returns:
            List: 断言结果列表
        """
        results = []

        for rule in assertion_rules:
            result = {
                "rule": rule,
                "passed": False,
                "expected": rule.get("value"),
                "actual": None,
                "message": ""
            }

            try:
                source = rule.get("source", AssertionSource.BODY)
                operator = rule.get("operator")
                field = rule.get("field")
                expected = rule.get("value")

                # 获取实际值
                actual = self._get_assertion_value(source, field, response_data)
                result["actual"] = actual

                # 执行断言
                result["passed"] = self._evaluate_assertion(
                    operator,
                    actual,
                    expected
                )

                if result["passed"]:
                    result["message"] = "断言通过"
                else:
                    result["message"] = f"断言失败: 期望 {expected}, 实际 {actual}"

            except Exception as e:
                result["passed"] = False
                result["message"] = f"断言检查异常: {str(e)}"

            results.append(result)

        return results

    def _get_assertion_value(
        self,
        source: str,
        field: str,
        response_data: Dict[str, Any]
    ) -> Any:
        """
        获取断言值

        Args:
            source: 断言来源
            field: 字段路径
            response_data: 响应数据

        Returns:
            Any: 实际值
        """
        if source == AssertionSource.STATUS:
            return response_data.get("status_code")
        elif source == AssertionSource.HEADER:
            return response_data.get("headers", {}).get(field)
        elif source == AssertionSource.RESPONSE_TIME:
            return response_data.get("response_time")
        elif source == AssertionSource.BODY:
            return self._get_json_path_value(response_data.get("body", {}), field)
        else:
            raise ValueError(f"不支持的断言来源: {source}")

    def _get_json_path_value(self, data: Any, path: str) -> Any:
        """
        根据 JSON Path 获取值

        Args:
            data: 数据对象
            path: JSON Path（如 $.data.user.id）

        Returns:
            Any: 获取的值
        """
        if not path or path == "$":
            return data

        # 移除 $. 前缀
        if path.startswith("$."):
            path = path[2:]

        keys = path.split(".")
        value = data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None

        return value

    def _evaluate_assertion(
        self,
        operator: str,
        actual: Any,
        expected: Any
    ) -> bool:
        """
        评估断言

        Args:
            operator: 操作符
            actual: 实际值
            expected: 期望值

        Returns:
            bool: 断言是否通过
        """
        if operator == AssertionOperator.EQUALS:
            return actual == expected
        elif operator == AssertionOperator.NOT_EQUALS:
            return actual != expected
        elif operator == AssertionOperator.CONTAINS:
            return str(expected) in str(actual)
        elif operator == AssertionOperator.NOT_CONTAINS:
            return str(expected) not in str(actual)
        elif operator == AssertionOperator.GREATER_THAN:
            return actual > expected
        elif operator == AssertionOperator.LESS_THAN:
            return actual < expected
        elif operator == AssertionOperator.GREATER_THAN_OR_EQUAL:
            return actual >= expected
        elif operator == AssertionOperator.LESS_THAN_OR_EQUAL:
            return actual <= expected
        elif operator == AssertionOperator.IN:
            return actual in expected
        elif operator == AssertionOperator.NOT_IN:
            return actual not in expected
        elif operator == AssertionOperator.IS_NULL:
            return actual is None
        elif operator == AssertionOperator.IS_NOT_NULL:
            return actual is not None
        elif operator == AssertionOperator.TYPE_IS:
            return type(actual).__name__ == expected
        elif operator == AssertionOperator.NOT_EMPTY:
            return actual is not None and actual != "" and actual != []
        else:
            raise ValueError(f"不支持的断言操作符: {operator}")

    def _extract_variables(
        self,
        extraction_rules: List[Dict[str, Any]],
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        提取变量

        Args:
            extraction_rules: 提取规则列表
            response_data: 响应数据

        Returns:
            Dict: 提取的变量字典
        """
        variables = {}

        for rule in extraction_rules:
            var_name = rule.get("variable_name")
            field = rule.get("field") or rule.get("json_path")

            if var_name and field:
                value = self._get_json_path_value(response_data.get("body", {}), field)
                variables[var_name] = value

        return variables

    def _resolve_variables(
        self,
        data: Any,
        variables: Dict[str, Any]
    ) -> Any:
        """
        解析变量（支持 {{variable_name}} 格式）

        Args:
            data: 数据对象
            variables: 变量字典

        Returns:
            Any: 解析后的数据
        """
        if isinstance(data, str):
            # 替换字符串中的变量
            import re
            pattern = r'\{\{(\w+)\}\}'
            matches = re.findall(pattern, data)

            for var_name in matches:
                if var_name in variables:
                    data = data.replace(f"{{{{{var_name}}}}}", str(variables[var_name]))

            return data
        elif isinstance(data, dict):
            return {k: self._resolve_variables(v, variables) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_variables(item, variables) for item in data]
        else:
            return data

    async def execute_batch(
        self,
        cases: List[Any],
        definitions: Dict[int, Any],
        environments: Dict[int, Any],
        variables: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 5,
        db: Optional[Any] = None,
        project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        批量执行用例

        Args:
            cases: 用例列表
            definitions: 接口定义字典 {definition_id: definition}
            environments: 环境字典 {environment_id: environment}
            variables: 变量字典
            max_concurrent: 最大并发数
            db: 数据库会话（用于鉴权）
            project_id: 项目 ID（用于鉴权）

        Returns:
            Dict: 批量执行结果
        """
        start_time = time.time()

        results = {
            "total": len(cases),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "cases": [],
            "start_time": start_time,
            "end_time": None,
            "total_time": None
        }

        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)

        async def execute_with_semaphore(case: Any):
            async with semaphore:
                definition = definitions.get(case.definition_id)
                environment = environments.get(case.environment_id)

                if not definition or not environment:
                    return {
                        "case_id": case.id,
                        "status": ExecutionStatus.SKIPPED,
                        "error": "缺少接口定义或环境"
                    }

                return await self.execute_case(
                    case=case,
                    definition=definition,
                    environment=environment,
                    variables=variables,
                    db=db,
                    project_id=project_id
                )

                return await self.execute_case(
                    case,
                    definition,
                    environment,
                    variables
                )

        # 并发执行
        tasks = [execute_with_semaphore(case) for case in cases]
        case_results = await asyncio.gather(*tasks)

        # 统计结果
        for case_result in case_results:
            results["cases"].append(case_result)

            if case_result["status"] == ExecutionStatus.SUCCESS:
                results["success"] += 1
            elif case_result["status"] == ExecutionStatus.FAILED:
                results["failed"] += 1
            elif case_result["status"] == ExecutionStatus.SKIPPED:
                results["skipped"] += 1

        results["end_time"] = time.time()
        results["total_time"] = int((results["end_time"] - start_time) * 1000)

        return results

    async def close(self):
        """关闭 HTTP 客户端"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None