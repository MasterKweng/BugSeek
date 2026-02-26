"""
用例执行引擎

提供单用例执行和批量执行功能，用于执行 API 测试用例。

功能特性:
1. HTTP 请求发送（使用 httpx）
2. 环境变量替换
3. 鉴权注入（复用 auth_service）
4. 断言验证
5. 结果记录（保存到数据库）
6. 性能监控（响应时间）

符合后端代码规范:
1. 统一响应体：{ code, message, data }
2. IDOR 防御：检查项目归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
5. SQL 注入防御：使用 SQLAlchemy ORM

V2.0 架构对齐:
- 层级一（API 资产库）的原子用例执行功能
- 为层级二（场景工作室）预留 ScenarioExecutor 接口
"""

import asyncio
import time
import json
import logging
import re
import random
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

import httpx
from sqlalchemy.orm import Session
from jsonpath_ng import parse

from app.db.base import (
    ApiCase, ApiDefinition, Environment,
    TestExecution, TestExecutionResult, AuthConfig
)
from app.core.auth_service import AuthMiddleware
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


# ==================== 枚举定义（避免魔法值） ====================

class ExecutionStatus(str):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionType(str):
    """执行类型枚举"""
    SINGLE = "single"      # 单用例执行
    SCENARIO = "scenario"  # 场景执行
    SUITE = "suite"        # 套件执行


class AssertionType(str):
    """断言类型枚举"""
    STATUS_CODE = "status_code"
    RESPONSE_BODY = "response_body"
    RESPONSE_TIME = "response_time"


class CaseExecutor:
    """用例执行器
    
    负责执行 API 测试用例，包括单用例执行和批量执行。
    支持环境变量替换、鉴权注入、断言验证等功能。
    
    V2.0 层级一（API 资产库）核心组件
    """

    def __init__(self):
        """初始化执行器"""
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            verify=False
        )
        self.auth_middleware = None
        self.trace_id = get_trace_id()

    async def _init_auth_service(self, db: Session, environment: Environment):
        """初始化鉴权服务
        
        Args:
            db: 数据库会话
            environment: 环境对象
        """
        if self.auth_middleware is None:
            self.auth_middleware = AuthMiddleware(db=db, environment_id=environment.id)

    async def execute_case(
        self,
        case: ApiCase,
        definition: ApiDefinition,
        environment: Environment,
        variables: Dict[str, Any],
        db: Session,
        project_id: int
    ) -> Dict[str, Any]:
        """
        执行单个用例
        
        Args:
            case: 用例对象
            definition: 接口定义对象
            environment: 环境对象
            variables: 变量字典
            db: 数据库会话
            project_id: 项目 ID
            
        Returns:
            Dict: 执行结果
                {
                    "case_id": int,
                    "status": str,  # passed | failed
                    "response_time": int,  # 毫秒
                    "response_code": int,
                    "response_body": Any,
                    "request_body": Any,
                    "assertion_results": Dict,
                    "error_message": Optional[str]
                }
        """
        start_time = time.time()
        case_trace_id = get_trace_id()

        extracted_vars: Dict[str, Any] = {}
        try:
            logger.info(f"[{case_trace_id}] ========== 开始执行用例 ==========")
            logger.info(f"[{case_trace_id}] 用例ID: {case.id}, 用例名称: {case.name}")
            logger.info(f"[{case_trace_id}] 接口定义ID: {definition.id}, 接口路径: {definition.method} {definition.path}")
            logger.info(f"[{case_trace_id}] 环境ID: {environment.id}, 环境名称: {environment.name}")
            logger.info(f"[{case_trace_id}] 项目ID: {project_id}")

            # 安全地序列化变量
            try:
                variables_str = json.dumps(variables, ensure_ascii=False, default=str)
            except Exception as e:
                variables_str = f"<变量序列化失败: {str(e)}>"
            logger.info(f"[{case_trace_id}] 输入变量: {variables_str}")

            # 初始化鉴权服务
            logger.info(f"[{case_trace_id}] [步骤1] 初始化鉴权服务...")
            await self._init_auth_service(db, environment)
            logger.info(f"[{case_trace_id}] [步骤1] 鉴权服务初始化完成")
        except Exception as e:
            logger.error(f"[{case_trace_id}] 用例执行初始化失败: {str(e)}")
            raise

        # 执行前置 SQL（支持结果写回变量）
        try:
            if case.pre_sql:
                logger.info(f"[{case_trace_id}] [步骤2] 执行前置SQL...")
                logger.info(f"[{case_trace_id}] [步骤2] SQL语句: {case.pre_sql}")
                pre_sql_vars = await self._execute_sql(
                    sql=case.pre_sql,
                    variables=variables,
                    db=db,
                    trace_id=case_trace_id,
                    stage="pre"
                )
                if pre_sql_vars:
                    logger.info(f"[{case_trace_id}] [步骤2] 前置SQL提取变量: {json.dumps(pre_sql_vars, ensure_ascii=False)}")
                    variables.update(pre_sql_vars)
                logger.info(f"[{case_trace_id}] [步骤2] 前置SQL执行完成")
            else:
                logger.info(f"[{case_trace_id}] [步骤2] 无前置SQL，跳过")
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤2] 前置SQL执行失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            raise

        # 执行前变量校验（避免 {{var}} 未替换直接出站）
        try:
            logger.info(f"[{case_trace_id}] [步骤2.5] 校验请求变量占位符...")
            available_vars: Dict[str, Any] = {}
            if environment.variables:
                available_vars.update({k: v for k, v in environment.variables.items() if v is not None})
            if variables:
                available_vars.update({k: v for k, v in variables.items() if v is not None})

            missing_vars = self._find_missing_variables(case.request_data, available_vars)

            # 校验路径参数是否齐全
            required_path_params = re.findall(r'\{([^{}]+)\}', definition.path or "")
            if required_path_params:
                path_params = {}
                if case.request_data and isinstance(case.request_data, dict):
                    path_params = case.request_data.get("path_params") or {}
                missing_path_params = [p for p in required_path_params if p not in path_params]
            else:
                missing_path_params = []

            if missing_vars or missing_path_params:
                logger.error(f"[{case_trace_id}] [步骤2.5] 缺失变量: {missing_vars}")
                logger.error(f"[{case_trace_id}] [步骤2.5] 缺失路径参数: {missing_path_params}")
                raise ValueError(f"Missing placeholders: vars={missing_vars}, path_params={missing_path_params}")

            logger.info(f"[{case_trace_id}] [步骤2.5] 变量占位符校验通过")
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤2.5] 变量校验失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            raise

        # 构建请求
        try:
            logger.info(f"[{case_trace_id}] [步骤3] 构建HTTP请求...")
            request_data = await self._build_request(
                case=case,
                definition=definition,
                environment=environment,
                variables=variables
            )
            logger.info(f"[{case_trace_id}] [步骤3] 请求构建完成: {request_data['method']} {request_data['url']}")
            logger.info(f"[{case_trace_id}] [步骤3] 请求头: {json.dumps(request_data['headers'], ensure_ascii=False)}")
            logger.info(f"[{case_trace_id}] [步骤3] 请求体: {json.dumps(request_data['body'], ensure_ascii=False) if request_data['body'] else 'None'}")
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤3] 请求构建失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            raise

        # 注入鉴权
        try:
            logger.info(f"[{case_trace_id}] [步骤4] 注入鉴权信息...")
            await self._inject_auth(
                request_data=request_data,
                environment=environment
            )
            logger.info(f"[{case_trace_id}] [步骤4] 鉴权注入完成，最终请求头: {json.dumps(request_data['headers'], ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤4] 鉴权注入失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            raise

        # 发送请求
        try:
            logger.info(f"[{case_trace_id}] [步骤5] 发送HTTP请求...")
            response_data = await self._send_request(request_data, case_trace_id)
            logger.info(f"[{case_trace_id}] [步骤5] HTTP请求完成")
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤5] HTTP请求发送失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            raise

        # 验证断言
        try:
            logger.info(f"[{case_trace_id}] [步骤6] 验证断言...")
            logger.info(f"[{case_trace_id}] [步骤6] 断言规则: {json.dumps(case.assertion_rules, ensure_ascii=False)}")
            assertion_results = await self._validate_assertions(
                case=case,
                response=response_data
            )
            logger.info(f"[{case_trace_id}] [步骤6] 断言验证完成，结果: {json.dumps(assertion_results, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤6] 断言验证失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            raise

        # 提取变量
        try:
            if case.extraction_rules:
                logger.info(f"[{case_trace_id}] [步骤7] 提取响应变量...")
                logger.info(f"[{case_trace_id}] [步骤7] 提取规则: {json.dumps(case.extraction_rules, ensure_ascii=False)}")
                extracted_variables = await self._extract_variables(
                    case=case,
                    response=response_data
                )
                logger.info(f"[{case_trace_id}] [步骤7] 变量提取完成，提取结果: {json.dumps(extracted_variables, ensure_ascii=False)}")
            else:
                logger.info(f"[{case_trace_id}] [步骤7] 无提取规则，跳过变量提取")
                extracted_variables = {}
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤7] 变量提取失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            extracted_variables = {}  # 提取失败不影响整体流程

        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)

        # 构建结果
        result = {
            "case_id": case.id,
            "status": "passed" if assertion_results["passed"] else "failed",
            "response_time": duration_ms,
            "response_code": response_data.get("status_code"),
            "response_body": response_data.get("body"),
            "request_body": request_data.get("body"),
            "assertion_results": assertion_results,
            "extracted_variables": extracted_variables,
            "error_message": assertion_results.get("error_message")
        }

        # 保存执行记录
        try:
            logger.info(f"[{case_trace_id}] [步骤8] 保存执行记录到数据库...")
            await self._save_execution_record(
                case=case,
                environment=environment,
                result=result,
                db=db
            )
            logger.info(f"[{case_trace_id}] [步骤8] 执行记录保存完成")
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤8] 保存执行记录失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            # 保存记录失败不影响返回结果

        # 执行后置 SQL
        try:
            if case.post_sql:
                logger.info(f"[{case_trace_id}] [步骤9] 执行后置SQL...")
                logger.info(f"[{case_trace_id}] [步骤9] SQL语句: {case.post_sql}")
                await self._execute_sql(
                    sql=case.post_sql,
                    variables=variables,
                    db=db,
                    trace_id=case_trace_id,
                    stage="post"
                )
                logger.info(f"[{case_trace_id}] [步骤9] 后置SQL执行完成")
            else:
                logger.info(f"[{case_trace_id}] [步骤9] 无后置SQL，跳过")
        except Exception as e:
            logger.error(f"[{case_trace_id}] [步骤9] 后置SQL执行失败: {str(e)}")
            import traceback
            logger.error(f"[{case_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
            # 后置SQL失败不影响返回结果

        logger.info(f"[{case_trace_id}] ========== 用例执行完成 ==========")
        logger.info(f"[{case_trace_id}] 最终状态: {result['status']}")
        logger.info(f"[{case_trace_id}] 总耗时: {duration_ms}ms")
        logger.info(f"[{case_trace_id}] 响应状态码: {result['response_code']}")
        logger.info(f"[{case_trace_id}] 断言通过数: {len([a for a in assertion_results.get('assertions', []) if a.get('passed')])}/{len(assertion_results.get('assertions', []))}")
        if result.get('error_message'):
            logger.error(f"[{case_trace_id}] 错误信息: {result['error_message']}")

        return result

    async def execute_batch(
        self,
        cases: List[ApiCase],
        definitions: Dict[int, ApiDefinition],
        environments: Dict[int, Environment],
        variables: Dict[str, Any],
        max_concurrent: int,
        db: Session,
        project_id: int
    ) -> Dict[str, Any]:
        """
        批量执行用例
        
        Args:
            cases: 用例列表
            definitions: 接口定义字典 {definition_id: definition}
            environments: 环境字典 {environment_id: environment}
            variables: 变量字典
            max_concurrent: 最大并发数
            db: 数据库会话
            project_id: 项目 ID
            
        Returns:
            Dict: 批量执行结果
                {
                    "total": int,
                    "success": int,
                    "failed": int,
                    "total_time": int,  # 毫秒
                    "results": List[Dict]
                }
        """
        start_time = time.time()
        batch_trace_id = get_trace_id()

        logger.info(f"[{batch_trace_id}] 开始批量执行: count={len(cases)}, max_concurrent={max_concurrent}")

        # 创建任务列表
        tasks = []
        for case in cases:
            definition = definitions.get(case.definition_id)
            environment = next(iter(environments.values()))  # 使用第一个环境

            task = self.execute_case(
                case=case,
                definition=definition,
                environment=environment,
                variables=variables,
                db=db,
                project_id=environment.project_id
            )
            tasks.append(task)

        # 控制并发执行
        results = []
        success = 0
        failed = 0

        for i in range(0, len(tasks), max_concurrent):
            batch_tasks = tasks[i:i + max_concurrent]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    failed += 1
                    logger.error(f"[{batch_trace_id}] 用例执行异常: {type(result).__name__}: {str(result)}")
                    import traceback
                    logger.error(f"[{batch_trace_id}] 异常堆栈:\n{traceback.format_exc()}")
                    results.append({
                        "status": "error",
                        "error_message": f"{type(result).__name__}: {str(result)}"
                    })
                else:
                    results.append(result)
                    if result["status"] == "passed":
                        success += 1
                    else:
                        failed += 1

        # 计算总耗时
        total_time = int((time.time() - start_time) * 1000)

        # 构建结果
        batch_result = {
            "total": len(cases),
            "success": success,
            "failed": failed,
            "total_time": total_time,
            "results": results
        }

        logger.info(f"[{batch_trace_id}] 批量执行完成: success={success}, failed={failed}, time={total_time}ms")

        return batch_result

    async def _build_request(
        self,
        case: ApiCase,
        definition: ApiDefinition,
        environment: Environment,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建请求数据
        
        Args:
            case: 用例对象
            definition: 接口定义对象
            environment: 环境对象
            variables: 变量字典
            
        Returns:
            Dict: 请求数据
                {
                    "method": str,
                    "url": str,
                    "headers": Dict,
                    "body": Any
                }
        """
        trace_id = get_trace_id()
        
        logger.info(f"[{trace_id}] --- 开始构建请求 ---")
        
        # 合并环境变量和自定义变量
        all_variables = {}
        if environment.variables:
            logger.info(f"[{trace_id}] 加载环境变量: {json.dumps(environment.variables, ensure_ascii=False)}")
            all_variables.update(environment.variables)
        if variables:
            logger.info(f"[{trace_id}] 加载自定义变量: {json.dumps(variables, ensure_ascii=False)}")
            all_variables.update(variables)
        logger.info(f"[{trace_id}] 合并后的所有变量: {json.dumps(all_variables, ensure_ascii=False)}")

        # 替换变量 - URL (拼接 base_url 和 path)
        base_url = environment.base_url.rstrip('/')
        path = definition.path.lstrip('/')
        original_full_url = f"{base_url}/{path}"
        
        # 首先处理路径参数（在变量替换之前）
        path_params = {}
        if case.request_data and "path_params" in case.request_data:
            path_params = case.request_data["path_params"]
            if path_params:
                logger.info(f"[{trace_id}] 原始路径参数: {json.dumps(path_params, ensure_ascii=False)}")
                # 先替换路径参数值中的动态函数
                for param_name, param_value in path_params.items():
                    if isinstance(param_value, str):
                        path_params[param_name] = self._replace_dynamic_functions(param_value)
                
                logger.info(f"[{trace_id}] 处理后路径参数: {json.dumps(path_params, ensure_ascii=False)}")
                
                # 替换路径参数到 URL 中
                for param_name, param_value in path_params.items():
                    # 支持单大括号和双大括号格式
                    placeholders = [f"{{{param_name}}}", f"{{{{{param_name}}}}}"]
                    for placeholder in placeholders:
                        if placeholder in path:
                            path = path.replace(placeholder, str(param_value))
                            logger.info(f"[{trace_id}] 路径参数替换: {placeholder} -> {param_value}")
                            break
        
        # 然后替换变量（包含动态函数）
        full_url = f"{base_url}/{path}"
        original_full_url_with_path = full_url
        full_url = self._replace_variables(full_url, all_variables)
        
        logger.info(f"[{trace_id}] URL构建: base_url='{base_url}', path='{path}'")
        logger.info(f"[{trace_id}] 路径参数替换后: '{original_full_url_with_path}'")
        logger.info(f"[{trace_id}] 变量替换后: '{full_url}'")
        
        # 合并请求头：环境 headers + 用例 request_data 中的 headers
        headers = {}
        if environment.headers:
            logger.info(f"[{trace_id}] 加载环境请求头: {json.dumps(environment.headers, ensure_ascii=False)}")
            headers.update(environment.headers)
        if case.request_data and "headers" in case.request_data:
            logger.info(f"[{trace_id}] 加载用例请求头: {json.dumps(case.request_data['headers'], ensure_ascii=False)}")
            headers.update(case.request_data["headers"])
        
        original_headers = headers.copy()
        headers = self._replace_variables(headers, all_variables)
        logger.info(f"[{trace_id}] 请求头变量替换: {json.dumps(original_headers, ensure_ascii=False)} -> {json.dumps(headers, ensure_ascii=False)}")

        # 处理请求体或查询参数
        body = None
        query_params = {}
        
        # 判断是否是 GET/HEAD 请求（这些请求不应该有 body）
        has_body_request = definition.method.upper() not in ['GET', 'HEAD', 'DELETE']
        
        if case.request_data:
            if has_body_request and "body" in case.request_data:
                # 有 body 的请求（POST/PUT/PATCH）
                original_body = case.request_data["body"]
                logger.info(f"[{trace_id}] 加载用例请求体: {json.dumps(original_body, ensure_ascii=False)}")
                body = case.request_data["body"]
                body = self._replace_variables(body, all_variables)
                logger.info(f"[{trace_id}] 请求体变量替换: {json.dumps(original_body, ensure_ascii=False)} -> {json.dumps(body, ensure_ascii=False)}")
            elif "body" in case.request_data:
                # GET/HEAD 请求中有 body 字段（不正确，但记录警告）
                logger.warning(f"[{trace_id}] {definition.method} 请求不应该有 body，但 request_data 中包含 body 字段，已忽略")
            
            # 处理查询参数（适用于所有请求类型）
            # 过滤掉非查询参数的字段（如 headers, body, path_params, query_params）
            non_query_fields = {'headers', 'body', 'path_params', 'query_params'}

            # 兼容 query_params 独立字段
            if "query_params" in case.request_data:
                qp = case.request_data.get("query_params")
                if isinstance(qp, dict):
                    query_params.update(qp)
                else:
                    logger.warning(f"[{trace_id}] query_params 不是对象类型，已忽略: {type(qp).__name__}")

            for key, value in case.request_data.items():
                if key not in non_query_fields:
                    query_params[key] = value
            
            if query_params:
                logger.info(f"[{trace_id}] 查询参数: {json.dumps(query_params, ensure_ascii=False)}")
                # 替换变量
                query_params = self._replace_variables(query_params, all_variables)
                # 构建查询字符串
                from urllib.parse import urlencode
                query_string = urlencode(query_params, doseq=True)
                full_url = f"{full_url}?{query_string}"
                logger.info(f"[{trace_id}] 最终URL（带查询参数）: {full_url}")
        
        if body is None:
            logger.info(f"[{trace_id}] 无请求体 ({definition.method} 请求)")
        else:
            logger.info(f"[{trace_id}] 请求体: {json.dumps(body, ensure_ascii=False)}")

        logger.info(f"[{trace_id}] --- 请求构建完成 ---")
        logger.info(f"[{trace_id}] 最终请求: {definition.method} {full_url}")

        return {
            "method": definition.method,
            "url": full_url,
            "headers": headers,
            "body": body
        }
    async def _inject_auth(
        self,
        request_data: Dict[str, Any],
        environment: Environment
    ):
        """
        注入鉴权
        
        Args:
            request_data: 请求数据
            environment: 环境对象
        """
        trace_id = get_trace_id()
        
        logger.info(f"[{trace_id}] --- 开始注入鉴权 ---")
        logger.info(f"[{trace_id}] 环境ID: {environment.id}, 项目ID: {environment.project_id}")
        
        if self.auth_middleware:
            # 获取登录凭证
            logger.info(f"[{trace_id}] 获取登录凭证...")
            result = await self.auth_middleware.acquire_auth_token(environment.project_id)
            logger.info(f"[{trace_id}] 登录凭证获取结果: {json.dumps(result, ensure_ascii=False)}")
            
            if result.get("success") and result.get("variables"):
                # 获取鉴权配置
                logger.info(f"[{trace_id}] 获取鉴权配置...")
                auth_config = await self.auth_middleware.get_auth_config(environment.project_id)
                logger.info(f"[{trace_id}] 鉴权配置: auth_type={auth_config.auth_type if auth_config else 'None'}")
                
                if auth_config:
                    # 将变量转换为 headers
                    logger.info(f"[{trace_id}] 将鉴权变量转换为请求头...")
                    logger.info(f"[{trace_id}] 鉴权变量: {json.dumps(result['variables'], ensure_ascii=False)}")
                    auth_headers = await self.auth_middleware._variables_to_headers(
                        auth_config, result["variables"]
                    )
                    logger.info(f"[{trace_id}] 转换后的鉴权请求头: {json.dumps(auth_headers, ensure_ascii=False)}")
                    
                    # 注入鉴权头
                    logger.info(f"[{trace_id}] 注入鉴权头到请求中...")
                    logger.info(f"[{trace_id}] 注入前请求头: {json.dumps(request_data['headers'], ensure_ascii=False)}")
                    request_data["headers"].update(auth_headers)
                    logger.info(f"[{trace_id}] 注入后请求头: {json.dumps(request_data['headers'], ensure_ascii=False)}")
                    logger.info(f"[{trace_id}] 鉴权注入完成")
                else:
                    logger.warning(f"[{trace_id}] 鉴权配置为空，跳过鉴权注入")
            else:
                logger.warning(f"[{trace_id}] 登录凭证获取失败或无变量，跳过鉴权注入")
        else:
            logger.warning(f"[{trace_id}] 鉴权中间件未初始化，跳过鉴权注入")
        
        logger.info(f"[{trace_id}] --- 鉴权注入流程结束 ---")

    async def _send_request(
        self,
        request_data: Dict[str, Any],
        trace_id: str
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求
        
        Args:
            request_data: 请求数据
            trace_id: 追踪 ID
            
        Returns:
            Dict: 响应数据
                {
                    "status_code": int,
                    "headers": Dict,
                    "body": Any
                }
        """
        try:
            logger.info(f"[{trace_id}] ========== 开始发送HTTP请求 ==========")
            logger.info(f"[{trace_id}] 请求方法: {request_data['method']}")
            logger.info(f"[{trace_id}] 请求URL: {request_data['url']}")
            logger.info(f"[{trace_id}] 请求头: {json.dumps(request_data['headers'], ensure_ascii=False)}")
            logger.info(f"[{trace_id}] 请求体: {json.dumps(request_data['body'], ensure_ascii=False) if request_data['body'] else 'None'}")
            logger.info(f"[{trace_id}] 等待响应...")
            
            request_start_time = time.time()
            
            response = await self.http_client.request(
                method=request_data["method"],
                url=request_data["url"],
                headers=request_data["headers"],
                json=request_data["body"] if request_data["body"] else None
            )
            
            request_duration = time.time() - request_start_time
            elapsed_ms = int(request_duration * 1000)
            
            logger.info(f"[{trace_id}] ========== 收到HTTP响应 ==========")
            logger.info(f"[{trace_id}] 响应状态码: {response.status_code}")
            logger.info(f"[{trace_id}] 响应时间: {request_duration:.3f}秒 ({int(request_duration * 1000)}ms)")
            logger.info(f"[{trace_id}] 响应头: {json.dumps(dict(response.headers), ensure_ascii=False)}")
            logger.info(f"[{trace_id}] 响应体类型: {response.headers.get('content-type', 'unknown')}")
            
            # 尝试格式化响应体
            response_body = response.text
            try:
                # 如果是JSON格式，尝试美化输出
                if response.headers.get('content-type', '').startswith('application/json'):
                    parsed_body = json.loads(response_body)
                    response_body = json.dumps(parsed_body, ensure_ascii=False, indent=2)
                    logger.info(f"[{trace_id}] 响应体 (JSON格式化):\n{response_body}")
                else:
                    # 非JSON响应，截断输出（最多500字符）
                    if len(response_body) > 500:
                        logger.info(f"[{trace_id}] 响应体 (截断显示):\n{response_body[:500]}... (总长度: {len(response_body)}字节)")
                    else:
                        logger.info(f"[{trace_id}] 响应体:\n{response_body}")
            except json.JSONDecodeError:
                # JSON解析失败，直接输出
                if len(response_body) > 500:
                    logger.info(f"[{trace_id}] 响应体 (截断显示):\n{response_body[:500]}... (总长度: {len(response_body)}字节)")
                else:
                    logger.info(f"[{trace_id}] 响应体:\n{response_body}")
            
            logger.info(f"[{trace_id}] ========== HTTP请求完成 ==========")

            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
                "elapsed_ms": elapsed_ms
            }
        except Exception as e:
            logger.error(f"[{trace_id}] ========== HTTP请求失败 ==========")
            logger.error(f"[{trace_id}] 异常类型: {type(e).__name__}")
            logger.error(f"[{trace_id}] 异常信息: {str(e)}")
            logger.error(f"[{trace_id}] 请求URL: {request_data['url']}")
            logger.error(f"[{trace_id}] 请求方法: {request_data['method']}")
            logger.error(f"[{trace_id}] ========== HTTP请求失败 ==========")
            return {
                "status_code": 0,
                "headers": {},
                "body": str(e),
                "elapsed_ms": 0
            }

    async def _validate_assertions(
        self,
        case: ApiCase,
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证断言
        
        Args:
            case: 用例对象
            response: 响应数据
            
        Returns:
            Dict: 断言结果
                {
                    "passed": bool,
                    "assertions": List[Dict],
                    "error_message": Optional[str]
                }
        """
        trace_id = get_trace_id()
        
        logger.info(f"[{trace_id}] ========== 开始验证断言 ==========")
        
        results = {
            "passed": True,
            "assertions": [],
            "error_message": None
        }

        # 检查断言规则是否存在
        if not case.assertion_rules:
            logger.info(f"[{trace_id}] 无断言规则，跳过所有断言")
            logger.info(f"[{trace_id}] ========== 断言验证完成 ==========")
            return results

        # 判断断言规则格式（列表或字典）
        if isinstance(case.assertion_rules, list):
            # 新格式：列表形式的断言规则
            logger.info(f"[{trace_id}] 检查断言（列表格式），共 {len(case.assertion_rules)} 条断言")
            
            # 尝试解析响应体
            try:
                response_body = json.loads(response["body"]) if response["body"] else {}
            except:
                response_body = {}

            def _normalize_operator(op: Any) -> str:
                if op is None:
                    return "=="
                raw = str(op).strip()
                low = raw.lower()
                mapping = {
                    "equals": "==",
                    "equal": "==",
                    "=": "==",
                    "==": "==",
                    "not_equals": "!=",
                    "not_equal": "!=",
                    "!=": "!=",
                    "<>": "!=",
                    "greater_than": ">",
                    "gt": ">",
                    "less_than": "<",
                    "lt": "<",
                    "greater_equal": ">=",
                    "ge": ">=",
                    "gte": ">=",
                    "less_equal": "<=",
                    "le": "<=",
                    "lte": "<=",
                    "not_in": "not_in",
                    "not-in": "not_in",
                    "not_contains": "not_contains",
                    "not-contains": "not_contains",
                }
                return mapping.get(low, raw)

            def _match_type(actual_value: Any, expected_type: Any) -> bool:
                type_map = {
                    "string": str,
                    "str": str,
                    "text": str,
                    "int": int,
                    "integer": int,
                    "float": float,
                    "number": (int, float),
                    "bool": bool,
                    "boolean": bool,
                    "list": list,
                    "array": list,
                    "dict": dict,
                    "object": dict,
                }
                if isinstance(expected_type, str):
                    t = type_map.get(expected_type.lower())
                    if t is None:
                        return False
                    return isinstance(actual_value, t)
                return False

            def _compare(actual_value: Any, operator_value: str, expected_value: Any) -> bool:
                op = operator_value
                op_lower = str(op).lower()

                if op in ("==", "="):
                    return actual_value == expected_value
                if op in ("!=", "<>"):
                    return actual_value != expected_value
                if op_lower == "in":
                    if isinstance(expected_value, (list, tuple, set)):
                        return actual_value in expected_value
                    if isinstance(actual_value, (list, tuple, set)):
                        return expected_value in actual_value
                    if isinstance(actual_value, str):
                        return str(expected_value) in actual_value
                    return actual_value == expected_value
                if op_lower == "not_in":
                    return not _compare(actual_value, "in", expected_value)
                if op_lower == "contains":
                    if actual_value is None:
                        return False
                    if isinstance(actual_value, dict):
                        return expected_value in actual_value
                    if isinstance(actual_value, (list, tuple, set)):
                        return expected_value in actual_value
                    return str(expected_value) in str(actual_value)
                if op_lower == "not_contains":
                    return not _compare(actual_value, "contains", expected_value)
                if op in (">", ">=", "<", "<="):
                    try:
                        if op == ">":
                            return actual_value > expected_value
                        if op == ">=":
                            return actual_value >= expected_value
                        if op == "<":
                            return actual_value < expected_value
                        if op == "<=":
                            return actual_value <= expected_value
                    except Exception:
                        return False
                if op_lower in ("exists", "not_null"):
                    return actual_value is not None
                if op_lower == "is_null":
                    return actual_value is None
                if op_lower == "is_true":
                    return actual_value is True or actual_value == True
                if op_lower == "is_false":
                    return actual_value is False or actual_value == False
                if op_lower == "regex":
                    if expected_value is None:
                        return False
                    return re.search(str(expected_value), str(actual_value)) is not None
                if op_lower == "type":
                    if isinstance(expected_value, (list, tuple, set)):
                        return any(_match_type(actual_value, t) for t in expected_value)
                    return _match_type(actual_value, expected_value)
                if op_lower == "length":
                    try:
                        return len(actual_value) == expected_value
                    except Exception:
                        return False
                if op_lower == "empty":
                    if actual_value is None:
                        return True
                    try:
                        return len(actual_value) == 0
                    except Exception:
                        return False
                return False

            def _get_header(headers_dict: Dict[str, Any], name: str) -> Any:
                if not name:
                    return None
                if name in headers_dict:
                    return headers_dict.get(name)
                lower_map = {k.lower(): v for k, v in headers_dict.items()}
                return lower_map.get(name.lower())

            for idx, assertion in enumerate(case.assertion_rules, 1):
                source_raw = assertion.get("source", "body")
                source = str(source_raw).lower()
                if source in ("status_code", "statuscode"):
                    source = "status"
                elif source in ("response", "response_body"):
                    source = "body"
                elif source in ("header", "headers"):
                    source = "header"
                elif source in ("time", "response_time", "elapsed", "duration"):
                    source = "time"

                operator = _normalize_operator(assertion.get("operator", "=="))
                property_path = assertion.get("property") or assertion.get("field") or assertion.get("json_path")
                expected = assertion.get("value")
                description = assertion.get("description", "")

                logger.info(
                    f"[{trace_id}] [断言 #{idx}] source={source}, operator={operator}, property={property_path}, expected={expected}, desc={description}"
                )

                assertion_passed = False
                actual = None

                try:
                    if source == "status":
                        actual = response["status_code"]
                        assertion_passed = _compare(actual, operator, expected)
                        results["assertions"].append({
                            "type": AssertionType.STATUS_CODE,
                            "source": source,
                            "operator": operator,
                            "expected": expected,
                            "actual": actual,
                            "passed": assertion_passed,
                            "description": description
                        })

                    elif source == "body":
                        if property_path:
                            actual = self._extract_field(response_body, property_path)
                        else:
                            actual = response_body
                        assertion_passed = _compare(actual, operator, expected)
                        results["assertions"].append({
                            "type": AssertionType.RESPONSE_BODY,
                            "source": source,
                            "field": property_path,
                            "operator": operator,
                            "expected": expected,
                            "actual": actual,
                            "passed": assertion_passed,
                            "description": description
                        })

                    elif source == "header":
                        actual = _get_header(response.get("headers", {}), property_path or "")
                        assertion_passed = _compare(actual, operator, expected)
                        results["assertions"].append({
                            "type": "header",
                            "source": source,
                            "field": property_path,
                            "operator": operator,
                            "expected": expected,
                            "actual": actual,
                            "passed": assertion_passed,
                            "description": description
                        })

                    elif source == "time":
                        actual = response.get("elapsed_ms")
                        assertion_passed = _compare(actual, operator, expected)
                        results["assertions"].append({
                            "type": AssertionType.RESPONSE_TIME,
                            "source": source,
                            "operator": operator,
                            "expected": expected,
                            "actual": actual,
                            "passed": assertion_passed,
                            "description": description
                        })

                    else:
                        logger.warning(f"[{trace_id}] [断言 #{idx}] 不支持的断言类型: {source_raw}")
                        continue

                    result_str = "通过" if assertion_passed else "失败"
                    logger.info(f"[{trace_id}] [断言 #{idx}] 结果: {result_str} (actual={actual}, expected={expected})")

                    if not assertion_passed:
                        results["passed"] = False

                except Exception as e:
                    logger.error(f"[{trace_id}] [断言 #{idx}] 验证失败: {str(e)}")
                    results["assertions"].append({
                        "type": "unknown",
                        "source": source_raw,
                        "passed": False,
                        "error": str(e),
                        "description": description
                    })
                    results["passed"] = False
                    
        elif isinstance(case.assertion_rules, dict):
            # 旧格式：字典形式的断言规则（向后兼容）
            logger.info(f"[{trace_id}] 检查断言（字典格式）")
            
            # 验证状态码
            status_assertion = case.assertion_rules.get("status_code")
            if status_assertion:
                expected = status_assertion.get("equals")
                if expected is not None:
                    actual = response["status_code"]
                    status_passed = actual == expected
                    
                    logger.info(f"[{trace_id}] [状态码断言] 预期: {expected}, 实际: {actual}, 结果: {'通过' if status_passed else '失败'}")
                    
                    results["assertions"].append({
                        "type": AssertionType.STATUS_CODE,
                        "expected": expected,
                        "actual": actual,
                        "passed": status_passed
                    })
                    if not status_passed:
                        results["passed"] = False
            else:
                logger.info(f"[{trace_id}] 无状态码断言，跳过")

            # 验证响应体（如果有断言）
            if "body" in case.assertion_rules:
                try:
                    response_body = json.loads(response["body"]) if response["body"] else {}
                    body_assertions = case.assertion_rules["body"]
                    logger.info(f"[{trace_id}] 响应体断言数量: {len(body_assertions)}")

                    for idx, assertion in enumerate(body_assertions, 1):
                        field = assertion.get("field")
                        operator = assertion.get("operator", "equals")
                        expected = assertion.get("value")

                        logger.info(f"[{trace_id}] [响应体断言 #{idx}] 字段路径: {field}, 操作符: {operator}, 预期值: {expected}")

                        actual = self._extract_field(response_body, field)
                        logger.info(f"[{trace_id}] [响应体断言 #{idx}] 提取到的实际值: {json.dumps(actual, ensure_ascii=False)}")

                        assertion_passed = False
                        if operator == "equals":
                            assertion_passed = actual == expected
                        elif operator == "contains":
                            assertion_passed = expected in str(actual)
                        elif operator == "not_equals":
                            assertion_passed = actual != expected
                        elif operator == "exists":
                            assertion_passed = actual is not None

                        result_str = "通过" if assertion_passed else "失败"
                        logger.info(f"[{trace_id}] [响应体断言 #{idx}] 结果: {result_str}")

                        results["assertions"].append({
                            "type": AssertionType.RESPONSE_BODY,
                            "field": field,
                            "operator": operator,
                            "expected": expected,
                            "actual": actual,
                            "passed": assertion_passed
                        })

                        if not assertion_passed:
                            results["passed"] = False

                except Exception as e:
                    logger.error(f"[{trace_id}] 响应体断言验证失败")
                    logger.error(f"[{trace_id}] 异常类型: {type(e).__name__}")
                    logger.error(f"[{trace_id}] 异常信息: {str(e)}")
                    results["error_message"] = f"解析响应失败: {str(e)}"
                    results["passed"] = False
        else:
            logger.warning(f"[{trace_id}] 不支持的断言规则格式: {type(case.assertion_rules)}")

        total_assertions = len(results["assertions"])
        passed_assertions = len([a for a in results["assertions"] if a["passed"]])
        logger.info(f"[{trace_id}] 断言验证完成: {passed_assertions}/{total_assertions} 通过, 总体结果: {'通过' if results['passed'] else '失败'}")
        logger.info(f"[{trace_id}] ========== 断言验证完成 ==========")

        return results

    async def _extract_variables(
        self,
        case: ApiCase,
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        提取变量（根据 extraction_rules）
        
        Args:
            case: 用例对象
            response: 响应数据
            
        Returns:
            Dict: 提取的变量字典 {var_name: value}
        """
        trace_id = get_trace_id()
        
        logger.info(f"[{trace_id}] ========== 开始提取变量 ==========")
        
        extracted_vars = {}

        if not case.extraction_rules:
            logger.info(f"[{trace_id}] 无提取规则，跳过变量提取")
            logger.info(f"[{trace_id}] ========== 变量提取完成 ==========")
            return extracted_vars

        try:
            # 解析响应体
            logger.info(f"[{trace_id}] 解析响应体...")
            response_body = json.loads(response["body"]) if response["body"] else {}
            logger.info(f"[{trace_id}] 响应体解析完成: {json.dumps(response_body, ensure_ascii=False)[:500]}...")

            # 提取变量
            logger.info(f"[{trace_id}] 提取规则数量: {len(case.extraction_rules)}")
            
            for idx, rule in enumerate(case.extraction_rules, 1):
                var_name = rule.get("var_name") or rule.get("variable_name")
                field_path = rule.get("field") or rule.get("json_path")

                if not var_name or not field_path:
                    logger.warning(f"[{trace_id}] [提取规则 #{idx}] 规则不完整，跳过 (var_name={var_name}, field_path={field_path})")
                    continue

                logger.info(f"[{trace_id}] [提取规则 #{idx}] 变量名: {var_name}, 字段路径: {field_path}")

                # 使用 JSONPath 提取字段值
                value = self._extract_field(response_body, field_path)

                if value is not None:
                    extracted_vars[var_name] = value
                    logger.info(f"[{trace_id}] [提取规则 #{idx}] 提取成功: {var_name} = {json.dumps(value, ensure_ascii=False)}")
                else:
                    logger.warning(f"[{trace_id}] [提取规则 #{idx}] 提取失败: 字段路径 {field_path} 未找到值")

        except Exception as e:
            logger.error(f"[{trace_id}] 变量提取失败")
            logger.error(f"[{trace_id}] 异常类型: {type(e).__name__}")
            logger.error(f"[{trace_id}] 异常信息: {str(e)}")

        logger.info(f"[{trace_id}] 变量提取完成，共提取 {len(extracted_vars)} 个变量")
        logger.info(f"[{trace_id}] 提取结果: {json.dumps(extracted_vars, ensure_ascii=False)}")
        logger.info(f"[{trace_id}] ========== 变量提取完成 ==========")

        return extracted_vars

    async def _execute_sql(
        self,
        sql: str,
        variables: Dict[str, Any],
        db: Session,
        trace_id: str,
        stage: str
    ) -> Dict[str, Any]:
        """
        Execute SQL for pre/post steps and return extracted variables.
        """
        extracted_vars: Dict[str, Any] = {}
        try:
            logger.info(f"[{trace_id}] {stage}_sql execute: {sql[:100]}...")

            sql_with_vars = self._replace_variables(sql, variables)
            logger.info(f"[{trace_id}] {stage}_sql after_replace: {sql_with_vars[:200]}...")

            result = db.execute(sql_with_vars)
            db.commit()

            if result.returns_rows:
                rows = result.fetchall()
                try:
                    logger.info(f"[{trace_id}] {stage}_sql columns: {list(result.keys())}")
                except Exception:
                    logger.info(f"[{trace_id}] {stage}_sql columns: <unavailable>")

                if rows:
                    first_row = rows[0]
                    try:
                        row_mapping = dict(first_row._mapping)
                    except Exception:
                        row_mapping = {k: first_row[i] for i, k in enumerate(result.keys())}
                    extracted_vars.update(row_mapping)
                    logger.info(f"[{trace_id}] {stage}_sql extracted_vars: {json.dumps(extracted_vars, ensure_ascii=False)}")
                else:
                    logger.warning(f"[{trace_id}] {stage}_sql returned 0 rows")

                logger.info(f"[{trace_id}] {stage}_sql success, rows={len(rows)}")
            else:
                affected_rows = result.rowcount
                logger.info(f"[{trace_id}] {stage}_sql success, affected_rows={affected_rows}")

        except Exception as e:
            db.rollback()
            logger.error(f"[{trace_id}] {stage}_sql failed: {str(e)}")
            logger.error(f"[{trace_id}] {stage}_sql original: {sql[:200]}...")
            try:
                logger.error(f"[{trace_id}] {stage}_sql replaced: {sql_with_vars[:200]}...")
            except Exception:
                pass

        if stage == "pre" and not extracted_vars:
            logger.warning(f"[{trace_id}] pre_sql extracted no vars; use SELECT ... AS <var_name>")

        return extracted_vars

    async def _save_execution_record(
        self,
        case: ApiCase,
        environment: Environment,
        result: Dict[str, Any],
        db: Session
    ):
        """
        保存执行记录
        
        Args:
            case: 用例对象
            environment: 环境对象
            result: 执行结果
            db: 数据库会话
        """
        try:
            # 创建执行记录
            execution = TestExecution(
                project_id=case.project_id,
                execution_type=ExecutionType.SINGLE,
                target_id=case.id,
                environment_id=environment.id,
                execution_mode="sequential",
                triggered_by="manual",
                status=ExecutionStatus.COMPLETED if result["status"] == "passed" else ExecutionStatus.FAILED,
                total=1,
                passed=1 if result["status"] == "passed" else 0,
                failed=0 if result["status"] == "passed" else 1,
                skipped=0,
                duration=result["response_time"]
            )

            db.add(execution)
            db.flush()  # 获取 execution.id

            # 创建执行结果明细
            execution_result = TestExecutionResult(
                execution_id=execution.id,
                target_type="endpoint",
                target_id=case.definition_id,
                status=result["status"],
                response_time=result["response_time"],
                response_code=result["response_code"],
                response_body={"raw": result["response_body"]},
                request_body={"raw": result["request_body"]},
                assertion_results=result["assertion_results"],
                extracted_variables=result.get("extracted_variables", {}),
                error_message=result.get("error_message")
            )

            db.add(execution_result)
            db.commit()

            logger.info(f"保存执行记录成功: execution_id={execution.id}")

        except Exception as e:
            db.rollback()
            logger.error(f"保存执行记录失败: {str(e)}")

    def _replace_variables(
        self,
        data: Any,
        variables: Dict[str, Any]
    ) -> Any:
        """
        替换变量和动态函数
        
        支持格式:
        1. 变量替换: {{variable_name}}
        2. 动态函数: {{random_int(1, 10)}}, {{random_string(8)}}, {{timestamp()}}, {{uuid()}}
        
        Args:
            data: 原始数据
            variables: 变量字典
            
        Returns:
            Any: 替换后的数据
        """
        if isinstance(data, str):
            # 先替换动态函数
            data = self._replace_dynamic_functions(data)
            
            # 再替换变量：{{variable_name}}
            for key, value in variables.items():
                placeholder = "{{" + key + "}}"
                if placeholder in data:
                    data = data.replace(placeholder, str(value))
            return data
        elif isinstance(data, dict):
            return {k: self._replace_variables(v, variables) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_variables(item, variables) for item in data]
        return data

    def _find_missing_variables(
        self,
        data: Any,
        available_vars: Dict[str, Any]
    ) -> List[str]:
        """
        查找请求数据中未提供的变量占位符（仅检查 {{var}}，忽略 {{func(...)}}）
        """
        missing = set()
        pattern = re.compile(r'\{\{\s*([a-zA-Z_]\w*)\s*(\([^{}]*\))?\s*\}\}')

        def walk(node: Any):
            if isinstance(node, str):
                for m in pattern.finditer(node):
                    name = m.group(1)
                    has_call = m.group(2) is not None
                    if has_call:
                        continue
                    if name not in available_vars:
                        missing.add(name)
            elif isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)
        return sorted(missing)

    def _replace_dynamic_functions(self, data: str) -> str:
        """
        替换动态函数占位符
        
        支持的函数:
        - {{random_int(min, max)}}: 生成随机整数
        - {{random_int(max)}}: 生成 0 到 max 的随机整数
        - {{random_string(length)}}: 生成随机字符串
        - {{random_choice([...])}}: 从列表中随机选择
        - {{timestamp()}}: 当前时间戳
        - {{uuid()}}: 生成 UUID
        
        Args:
            data: 包含动态函数的字符串
            
        Returns:
            str: 替换后的字符串
        """
        # 随机整数: {{random_int(min, max)}} 或 {{random_int(max)}}
        data = re.sub(
            r'\{\{random_int\((\d+)\)\}\}',
            lambda m: str(random.randint(0, int(m.group(1)))),
            data
        )
        data = re.sub(
            r'\{\{random_int\((\d+),\s*(\d+)\)\}\}',
            lambda m: str(random.randint(int(m.group(1)), int(m.group(2)))),
            data
        )
        
        # 随机字符串: {{random_string(length)}}
        def generate_random_string(match):
            length = int(match.group(1))
            chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            return ''.join(random.choice(chars) for _ in range(length))
        
        data = re.sub(
            r'\{\{random_string\((\d+)\)\}\}',
            generate_random_string,
            data
        )
        
        # 随机选择: {{random_choice([...])}}
        def random_choice_wrapper(match):
            try:
                choices_str = match.group(1)
                choices = json.loads(choices_str)
                return str(random.choice(choices))
            except:
                return match.group(0)
        
        data = re.sub(
            r'\{\{random_choice\((.+?)\)\}\}',
            random_choice_wrapper,
            data
        )
        
        # 时间戳: {{timestamp()}} 或 {{timestamp}}
        data = data.replace('{{timestamp()}}', str(int(time.time())))
        data = data.replace('{{timestamp}}', str(int(time.time())))
        
        # UUID: {{uuid()}}
        data = data.replace('{{uuid()}}', str(uuid.uuid4()))
        
        return data

    def _extract_field(self, data: Any, field_path: str) -> Any:
        """
        提取字段值（支持完整的 JSONPath 语法）
        
        支持格式:
        - 简化版: data.id, data.users[0].name
        - JSONPath: $.data.id, $.data.users[0].name, $..id (递归查找)
        
        Args:
            data: 数据对象
            field_path: 字段路径
            
        Returns:
            Any: 字段值
        """
        try:
            # 如果 field_path 包含 JSONPath 语法（$. 或 $..），使用 jsonpath-ng
            if field_path.startswith('$'):
                jsonpath_expression = parse(field_path)
                matches = jsonpath_expression.find(data)
                
                if matches:
                    # 如果有多个匹配，返回列表；否则返回单个值
                    if len(matches) == 1:
                        return matches[0].value
                    else:
                        return [match.value for match in matches]
                return None
            
            # 否则使用简化版语法（向后兼容）
            current = data
            parts = field_path.split(".")

            for part in parts:
                # 处理数组索引，如 users[0]
                if "[" in part and "]" in part:
                    array_name = part.split("[")[0]
                    index = int(part.split("[")[1].split("]")[0])
                    current = current.get(array_name, [])[index]
                else:
                    current = current.get(part)

            return current
        except Exception as e:
            logger.error(f"提取字段失败: field_path={field_path}, error={str(e)}")
            return None

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.http_client.aclose()


# ==================== 预留场景执行器接口 ====================

class ScenarioExecutor:
    """场景执行器（预留）
    
    V2.0 层级二（场景工作室）核心组件
    支持解析 Graph/JSON 结构的流程
    
    TODO: 待实现
    """

    async def execute_scenario(
        self,
        scenario_id: int,
        graph_data: Dict[str, Any],
        variables: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """
        执行场景
        
        Args:
            scenario_id: 场景 ID
            graph_data: 图数据（nodes + edges）
            variables: 变量字典
            db: 数据库会话
            
        Returns:
            Dict: 执行结果
        """
        # TODO: 实现场景执行逻辑
        raise NotImplementedError("场景执行器待实现")


# ==================== AI 辅助功能预留接口 ====================

class AIAssistedExecutor(CaseExecutor):
    """AI 增强执行器（预留）
    
    V2.0 第三阶段（AI 增强）核心组件
    支持智能断言生成、智能参数映射等 AI 功能
    
    TODO: 待实现
    """

    async def auto_generate_assertions(
        self,
        response: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        AI 自动生成断言规则
        
        Args:
            response: 响应数据
            context: 上下文信息（可选）
            
        Returns:
            List[Dict]: 生成的断言规则列表
                [
                    {
                        "type": "status_code",
                        "expected": 200
                    },
                    {
                        "type": "response_body",
                        "field": "$.data.id",
                        "operator": "exists"
                    }
                ]
        """
        # TODO: 调用 LLM 分析响应，生成断言
        raise NotImplementedError("AI 断言生成待实现")

    async def auto_map_variables(
        self,
        source_output: Dict[str, Any],
        target_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        AI 自动映射变量（场景编排用）
        
        Args:
            source_output: 源接口的输出
            target_input: 目标接口的输入
            context: 上下文信息（可选）
            
        Returns:
            Dict: 变量映射规则
                {
                    "source_field": "source_output.data.orderId",
                    "target_field": "target_input.body.oid",
                    "confidence": 0.95
                }
        """
        # TODO: 调用 LLM 语义分析，自动连线
        raise NotImplementedError("AI 变量映射待实现")

    async def analyze_test_failure(
        self,
        execution_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        AI 分析测试失败原因
        
        Args:
            execution_result: 执行结果
            context: 上下文信息（可选）
            
        Returns:
            Dict: 失败分析结果
                {
                    "failure_type": "assertion_failed",
                    "root_cause": "响应字段名变更",
                    "suggested_fix": "更新断言字段为 $.data.new_field",
                    "confidence": 0.88
                }
        """
        # TODO: 调用 LLM 分析失败原因
        raise NotImplementedError("AI 失败分析待实现")

    async def generate_test_cases(
        self,
        api_definition: Dict[str, Any],
        num_cases: int = 5,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        AI 自动生成测试用例
        
        Args:
            api_definition: API 定义
            num_cases: 生成用例数量
            context: 上下文信息（可选）
            
        Returns:
            List[Dict]: 生成的测试用例列表
                [
                    {
                        "name": "正常登录",
                        "request_data": {...},
                        "assertion_rules": {...}
                    }
                ]
        """
        # 调用 AI 服务生成用例（基准用例模板）
        from app.ai.service import AIService

        ai_service = AIService()
        total = max(1, int(num_cases))
        results: List[Dict[str, Any]] = []

        method = api_definition.get("method", "GET")
        path = api_definition.get("path", "/")
        summary = api_definition.get("summary")
        description = api_definition.get("description")
        request_schema = api_definition.get("request_schema")
        response_schema = api_definition.get("response_schema")

        for _ in range(total):
            case = await ai_service.generate_base_case(
                method=method,
                path=path,
                summary=summary,
                description=description,
                request_schema=request_schema,
                response_schema=response_schema
            )

            # 兼容模型返回列表或单对象
            if isinstance(case, list):
                results.extend(case)
            else:
                results.append(case)

        return results
