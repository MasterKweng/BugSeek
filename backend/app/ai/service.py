"""AI 服务核心"""
from typing import Dict, Any, Optional
from app.ai.prompts import PromptManager
from app.ai.context import ContextInjector
from app.ai.adapters import ModelAdapterFactory
from app.ai.config import AI_CONFIG
import logging

logger = logging.getLogger(__name__)


class AIService:
    """AI 服务核心 - 统一管理所有 AI 调用"""
    
    def __init__(self):
        self.prompt_manager = PromptManager()
        self.context_injector = ContextInjector()
        self.model_adapter = None  # 延迟初始化
    
    def _get_adapter(self):
        """获取模型适配器（延迟初始化）"""
        if self.model_adapter is None:
            self.model_adapter = ModelAdapterFactory.create()
        return self.model_adapter
    
    async def execute(
        self,
        task_type: str,
        project_id: Optional[int],
        input_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行 AI 任务

        Args:
            task_type: 任务类型
            project_id: 项目ID（用于注入上下文）
            input_data: 输入数据
            options: 可选参数（如 temperature、max_tokens）

        Returns:
            Dict: 包含 result 和元数据
        """
        try:
            # 记录输入数据（不包含敏感信息）
            logger.info(f"AI 执行开始: task_type={task_type}, project_id={project_id}")
            logger.info(f"AI 输入数据: method={input_data.get('method')}, path={input_data.get('path')}, summary={input_data.get('summary')}")
            logger.debug(f"AI 输入数据: path={input_data.get('path')}, method={input_data.get('method')}, test_types={list(input_data.get('test_types_config', {}).keys())}")

            # 1. 获取 Prompt 模板
            template = self.prompt_manager.get_template(task_type)

            # 2. 注入项目上下文
            context = {}
            if project_id:
                context = await self.context_injector.inject(project_id)

            # 3. 构建 Prompt
            rendered = self.prompt_manager.render(template, context, input_data)

            # 记录渲染后的用户 Prompt（截取前500字符）
            logger.info(f"渲染后的用户 Prompt（前500字符）: {rendered['user'][:500]}")

            # 4. 调用模型
            adapter = self._get_adapter()
            logger.info(f"调用 AI 模型: model={type(adapter).__name__}")
            result = await adapter.complete(
                prompt=rendered["user"],
                system_prompt=rendered["system"]
            )

            # 5. 处理结果
            if result.get("error"):
                logger.error(f"AI 调用失败: {result['error']}")
                return {
                    "success": False,
                    "error": result["error"],
                    "task_type": task_type
                }

            logger.info(f"AI 调用成功: task_type={task_type}, project_id={project_id}, tokens_used={result.get('tokens_used', 0)}")

            return {
                "success": True,
                "result": result["result"],
                "metadata": {
                    "task_type": task_type,
                    "project_id": project_id,
                    "model": result.get("model"),
                    "tokens_used": result.get("tokens_used", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"AI 服务执行失败: task_type={task_type}, error={str(e)}")
            return {
                "success": False,
                "error": str(e),
                "task_type": task_type
            }
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        adapter = self._get_adapter()
        return await adapter.get_usage_stats()

    async def generate_base_case(
        self,
        method: str,
        path: str,
        summary: Optional[str],
        description: Optional[str],
        request_schema: Optional[Dict[str, Any]],
        response_schema: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        AI 生成基准用例

        Args:
            method: HTTP 方法
            path: 接口路径
            summary: 接口摘要
            description: 接口描述
            request_schema: 请求参数 Schema
            response_schema: 响应参数 Schema

        Returns:
            Dict: 生成的用例数据
        """
        try:
            # 构建输入数据
            input_data = {
                "method": method,
                "path": path,
                "summary": summary or "",
                "description": description or "",
                "request_schema": request_schema or {},
                "response_schema": response_schema or {}
            }

            # 异步执行 AI 任务
            result = await self.execute(
                task_type="api_case_generation",
                project_id=None,
                input_data=input_data
            )

            if result.get("success"):
                # 解析结果，移除 markdown 代码块标记
                result_str = result["result"]
                if isinstance(result_str, str):
                    # 移除 ```json 和 ``` 标记
                    result_str = result_str.strip()
                    if result_str.startswith('```json'):
                        result_str = result_str[7:]  # 移除 ```json
                    elif result_str.startswith('```'):
                        result_str = result_str[3:]  # 移除 ```
                    if result_str.endswith('```'):
                        result_str = result_str[:-3]  # 移除结尾的 ```
                    result_str = result_str.strip()
                
                # 记录原始返回内容（用于调试）
                logger.info(f"AI 返回的原始内容: {result_str[:500]}...")
                
                # 尝试解析为 JSON
                import json
                if isinstance(result_str, str):
                    try:
                        parsed_result = json.loads(result_str)
                        logger.info(f"JSON 解析成功")
                        return self._post_process_case(parsed_result, method=method, path=path)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 解析失败: {str(e)}")
                        logger.error(f"JSON 内容: {result_str}")
                        # 尝试修复常见的 JSON 格式问题
                        try:
                            # 尝试将单引号替换为双引号
                            fixed_str = result_str.replace("'", '"')
                            parsed_result = json.loads(fixed_str)
                            logger.info(f"JSON 修复后解析成功")
                            return self._post_process_case(parsed_result, method=method, path=path)
                        except Exception as e2:
                            logger.error(f"JSON 修复失败: {str(e2)}")
                            raise Exception(f"AI 返回的 JSON 格式错误: {str(e)}")
                return result_str
            else:
                raise Exception(result.get("error", "AI 生成失败"))

        except Exception as e:
            logger.error(f"AI 生成基准用例失败: {str(e)}")
            raise

    def _post_process_case(
        self,
        case_result: Any,
        method: str,
        path: str
    ) -> Any:
        """
        后处理 AI 生成的用例结果：
        - 识别 ID/外键字段，避免随机数，改为变量占位
        - 自动补充 required_variables / data_prep
        """
        if not isinstance(case_result, dict):
            return case_result

        def is_id_key(key: str) -> bool:
            if not key:
                return False
            if key == "id":
                return True
            if key.endswith("_id"):
                return True
            if key.endswith("Id") or key.endswith("ID"):
                return True
            return False

        def is_dynamic_or_numeric(val: Any) -> bool:
            if isinstance(val, (int, float)):
                return True
            if isinstance(val, str):
                lowered = val.lower()
                if "random_" in lowered or "uuid" in lowered or "timestamp" in lowered:
                    return True
                if val.isdigit():
                    return True
            return False

        def is_already_variable(val: Any) -> bool:
            if isinstance(val, str):
                return val.startswith("{{") and val.endswith("}}") and "random_" not in val.lower()
            return False

        required_vars = []
        raw_required = case_result.get("required_variables")
        if isinstance(raw_required, list):
            for item in raw_required:
                if isinstance(item, str):
                    required_vars.append(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("var_name") or item.get("variable")
                    if name:
                        required_vars.append(name)

        required_set = {v for v in required_vars if isinstance(v, str) and v}

        def normalize(obj: Any, parent_key: Optional[str] = None) -> Any:
            if isinstance(obj, dict):
                new_obj = {}
                for k, v in obj.items():
                    new_obj[k] = normalize(v, parent_key=k)
                return new_obj
            if isinstance(obj, list):
                return [normalize(item, parent_key=parent_key) for item in obj]

            if parent_key and is_id_key(parent_key):
                if not is_already_variable(obj) and is_dynamic_or_numeric(obj):
                    required_set.add(parent_key)
                    return "{{" + parent_key + "}}"
            return obj

        if "request_data" in case_result:
            case_result["request_data"] = normalize(case_result.get("request_data"))

        if required_set:
            case_result["required_variables"] = sorted(required_set)
            if not case_result.get("data_prep"):
                case_result["data_prep"] = [
                    f"{name}: 需从数据库查询或通过前置业务创建" for name in sorted(required_set)
                ]

        return case_result

    def generate_assertions(
        self,
        response_schema: Dict[str, Any],
        response_sample: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        AI 生成断言规则

        Args:
            response_schema: 响应参数 Schema
            response_sample: 参考响应数据

        Returns:
            Dict: 生成的断言规则
        """
        try:
            import asyncio

            # 构建输入数据
            input_data = {
                "method": "GET",  # 默认值，不使用
                "path": "/",      # 默认值，不使用
                "response_schema": response_schema,
                "response_sample": response_sample or {}
            }

            # 同步执行 AI 任务
            result = asyncio.run(self.execute(
                task_type="assertion_generation",
                project_id=None,
                input_data=input_data
            ))

            if result.get("success"):
                return result["result"]
            else:
                raise Exception(result.get("error", "AI 生成失败"))

        except Exception as e:
            logger.error(f"AI 生成断言失败: {str(e)}")
            raise
