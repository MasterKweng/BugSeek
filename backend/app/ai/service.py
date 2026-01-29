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
            logger.debug(f"AI 输入数据: path={input_data.get('path')}, method={input_data.get('method')}, test_types={list(input_data.get('test_types_config', {}).keys())}")

            # 1. 获取 Prompt 模板
            template = self.prompt_manager.get_template(task_type)

            # 2. 注入项目上下文
            context = {}
            if project_id:
                context = await self.context_injector.inject(project_id)

            # 3. 构建 Prompt
            rendered = self.prompt_manager.render(template, context, input_data)

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