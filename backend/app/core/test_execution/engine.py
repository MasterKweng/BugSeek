"""统一测试执行引擎"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import httpx
from sqlalchemy.orm import Session

from app.db.base import ApiTestScript, ApiEndpoint, Environment, ScriptExecution
from app.core.trace import get_trace_id
from app.core.test_execution.request_builder import RequestBuilder
from app.core.test_execution.assertion_checker import AssertionChecker
from app.core.test_execution.result_collector import ResultCollector
from app.constants.script import ExecutionStatus

logger = logging.getLogger(__name__)


class TestExecutionEngine:
    """统一测试执行引擎"""

    def __init__(self, db: Session):
        """
        初始化执行引擎
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()

    async def execute_single(
        self,
        script: ApiTestScript,
        environment: Environment,
        variables: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None
    ) -> ScriptExecution:
        """
        执行单个测试脚本
        
        Args:
            script: 测试脚本
            environment: 环境配置
            variables: 自定义变量
            headers: 自定义请求头
            body: 自定义请求体
            
        Returns:
            执行记录
        """
        logger.info(f"[{self.trace_id}] 开始执行脚本: script_id={script.id}")
        
        started_at = datetime.utcnow()
        
        # 创建结果收集器
        result_collector = ResultCollector(execution_id=0)  # 临时ID，保存时更新
        
        try:
            # 1. 查询接口信息
            endpoint = self.db.query(ApiEndpoint).filter(
                ApiEndpoint.id == script.endpoint_id
            ).first()
            
            if not endpoint:
                raise ValueError(f"接口不存在: endpoint_id={script.endpoint_id}")
            
            # 2. 构建请求
            request_builder = RequestBuilder(
                script=script,
                endpoint=endpoint,
                environment=environment,
                variables=variables,
                headers=headers,
                body=body
            )
            
            request = request_builder.build_request()
            request_size = request_builder.get_request_size(request)
            
            result_collector.collect_request_info(request, request_size)
            
            # 3. 发送HTTP请求
            logger.info(f"[{self.trace_id}] 发送请求: {request['method']} {request['url']}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.request(
                    method=request['method'],
                    url=request['url'],
                    headers=request['headers'],
                    params=request['params'],
                    json=request['json'],
                )
                
                response_time_ms = int(response.elapsed.total_seconds() * 1000)
                
                # 4. 收集响应信息
                result_collector.collect_response_info(response, response_time_ms)
                
                # 5. 验证断言
                script_content = script.script_content or {}
                assertions = script_content.get('assertions', [])
                
                if assertions:
                    assertion_checker = AssertionChecker(assertions)
                    assertion_results = assertion_checker.check(
                        response_status_code=response.status_code,
                        response_body=result_collector.result['response']['body']
                    )
                    result_collector.collect_assertions(assertion_results)
                    
                    # 输出断言摘要
                    summary = assertion_checker.get_assertion_summary(assertion_results)
                    logger.info(
                        f"[{self.trace_id}] 断言结果: "
                        f"总数={summary['total']}, 通过={summary['passed']}, "
                        f"失败={summary['failed']}, 通过率={summary['pass_rate']:.2f}%"
                    )
            
            finished_at = datetime.utcnow()
            
            # 6. 保存执行记录
            execution_dict = result_collector.to_script_execution_dict(
                project_id=script.project_id,
                script_id=script.id,
                endpoint_id=endpoint.id,
                environment_id=environment.id,
                started_at=started_at,
                finished_at=finished_at
            )
            
            execution = ScriptExecution(**execution_dict)
            self.db.add(execution)
            self.db.commit()
            self.db.refresh(execution)
            
            logger.info(
                f"[{self.trace_id}] 执行完成: execution_id={execution.id}, "
                f"status={execution.status}, 耗时={execution.duration_ms}ms"
            )
            
            return execution
        
        except Exception as e:
            logger.error(f"[{self.trace_id}] 执行失败: {str(e)}", exc_info=True)
            
            # 保存失败记录
            finished_at = datetime.utcnow()
            
            result_collector.result['response'] = {
                'error': result_collector.get_error_message(e)
            }
            
            execution_dict = result_collector.to_script_execution_dict(
                project_id=script.project_id,
                script_id=script.id,
                endpoint_id=script.endpoint_id,
                environment_id=environment.id,
                started_at=started_at,
                finished_at=finished_at
            )
            
            execution = ScriptExecution(**execution_dict)
            self.db.add(execution)
            self.db.commit()
            self.db.refresh(execution)
            
            return execution

    async def execute_scenario(
        self,
        scenario_id: int,
        environment: Environment
    ):
        """
        执行场景（按依赖顺序执行）
        
        流程：
        1. 查询场景配置
        2. 按执行顺序依次执行接口
        3. 处理变量传递（从上一步的响应中提取变量，传递给下一步）
        4. 记录执行日志
        
        Args:
            scenario_id: 场景ID
            environment: 环境配置
            
        Returns:
            执行记录
        """
        from app.db.base import ApiScenario, ApiEndpoint
        
        logger.info(f"[{self.trace_id}] 开始执行场景: scenario_id={scenario_id}")
        
        started_at = datetime.utcnow()
        
        try:
            # 1. 查询场景配置
            scenario = self.db.query(ApiScenario).filter(
                ApiScenario.id == scenario_id
            ).first()
            
            if not scenario:
                raise ValueError(f"场景不存在: scenario_id={scenario_id}")
            
            # 2. 查询场景涉及的接口
            endpoints = self.db.query(ApiEndpoint).filter(
                ApiEndpoint.id.in_(scenario.endpoint_ids)
            ).all()
            
            endpoint_map = {ep.id: ep for ep in endpoints}
            
            # 3. 初始化变量存储
            scenario_variables = scenario.variables or {}
            
            # 4. 按执行顺序依次执行接口
            execution_results = []
            
            for step_config in scenario.execution_order:
                step = step_config.get('step')
                endpoint_id = step_config.get('endpoint_id')
                
                endpoint = endpoint_map.get(endpoint_id)
                if not endpoint:
                    logger.warning(f"[{self.trace_id}] 接口不存在: endpoint_id={endpoint_id}")
                    continue
                
                # 构建当前步骤的变量（合并场景变量和步骤变量）
                step_variables = {
                    **scenario_variables,
                    **step_config.get('variables', {})
                }
                
                # 查询接口的测试脚本
                script = self.db.query(ApiTestScript).filter(
                    ApiTestScript.endpoint_id == endpoint_id,
                    ApiTestScript.project_id == scenario.project_id
                ).first()
                
                if not script:
                    logger.warning(f"[{self.trace_id}] 接口无测试脚本: endpoint_id={endpoint_id}")
                    continue
                
                # 执行脚本
                logger.info(
                    f"[{self.trace_id}] 执行步骤 {step}: {endpoint.method} {endpoint.path}"
                )
                
                execution = await self.execute_single(
                    script=script,
                    environment=environment,
                    variables=step_variables
                )
                
                execution_results.append({
                    'step': step,
                    'endpoint_id': endpoint_id,
                    'execution_id': execution.id,
                    'status': execution.status,
                    'duration_ms': execution.duration_ms
                })
                
                # 5. 提取变量（从响应中提取，传递给下一步）
                extract_fields = step_config.get('extract', {})
                if extract_fields and execution.response_body:
                    for field_name, json_path in extract_fields.items():
                        extracted_value = self._extract_value_by_path(
                            execution.response_body,
                            json_path
                        )
                        if extracted_value is not None:
                            # 保存到场景变量，命名为 step{step}.{field_name}
                            scenario_variables[f"step{step}.{field_name}"] = extracted_value
                            logger.info(
                                f"[{self.trace_id}] 提取变量: step{step}.{field_name}={extracted_value}"
                            )
                
                # 如果执行失败且不允许继续，则中断
                if execution.status != 'success' and not scenario.continue_on_failure:
                    logger.error(
                        f"[{self.trace_id}] 步骤 {step} 执行失败，中断场景执行"
                    )
                    break
            
            finished_at = datetime.utcnow()
            
            # 6. 保存场景执行记录
            from app.db.base import TestExecution
            
            test_execution = TestExecution(
                project_id=scenario.project_id,
                execution_type="scenario",
                target_id=scenario.id,
                environment_id=environment.id,
                triggered_by="manual",
                status=self._calculate_scenario_status(execution_results),
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                total_steps=len(scenario.execution_order),
                passed_steps=len([r for r in execution_results if r['status'] == 'success']),
                failed_steps=len([r for r in execution_results if r['status'] != 'success'])
            )
            
            self.db.add(test_execution)
            self.db.commit()
            self.db.refresh(test_execution)
            
            logger.info(
                f"[{self.trace_id}] 场景执行完成: execution_id={test_execution.id}, "
                f"status={test_execution.status}, 耗时={test_execution.duration_ms}ms"
            )
            
            return test_execution
        
        except Exception as e:
            logger.error(f"[{self.trace_id}] 场景执行失败: {str(e)}", exc_info=True)
            raise

    def _extract_value_by_path(self, data: Dict[str, Any], path: str) -> Any:
        """
        从数据中按路径提取值
        
        Args:
            data: 数据字典
            path: 路径（如 "data.order_id" 或 "order_id"）
            
        Returns:
            提取的值
        """
        if not path:
            return None
        
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current

    def _calculate_scenario_status(self, execution_results: List[Dict]) -> str:
        """
        计算场景执行状态
        
        Args:
            execution_results: 执行结果列表
            
        Returns:
            状态（success | failed | partial）
        """
        if not execution_results:
            return "failed"
        
        failed_count = len([r for r in execution_results if r['status'] != 'success'])
        
        if failed_count == 0:
            return "success"
        elif failed_count == len(execution_results):
            return "failed"
        else:
            return "partial"

    async def execute_suite(
        self,
        suite_id: int,
        environment: Environment,
        execution_mode: str = "parallel"
    ):
        """
        执行测试套件
        
        Args:
            suite_id: 套件ID
            environment: 环境配置
            execution_mode: 执行模式（parallel | sequential）
            
        Returns:
            执行记录
        """
        logger.info(
            f"[{self.trace_id}] 开始执行套件: suite_id={suite_id}, mode={execution_mode}"
        )
        
        # TODO: 实现套件执行逻辑
        # 1. 查询套件配置
        # 2. 根据模式串行或并行执行
        # 3. 汇总执行结果
        
        raise NotImplementedError("套件执行功能待实现")