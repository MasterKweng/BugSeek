"""AI 服务网关 - 统一接口"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.ai.service import AIService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class AIRequest(BaseModel):
    """统一的 AI 请求模型"""
    task_type: str  # 任务类型
    project_id: Optional[int] = None  # 项目ID（用于注入上下文）
    input_data: Dict[str, Any]  # 输入数据
    options: Optional[Dict[str, Any]] = None  # 可选参数


class AIResponse(BaseModel):
    """统一的 AI 响应模型"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/ai/complete", response_model=AIResponse)
async def ai_complete(request: AIRequest):
    """
    统一的 AI 完成接口
    
    所有模块通过此接口调用 AI 能力
    
    **任务类型示例**：
    - api_test_generation: 接口测试脚本生成
    - code_review: 代码审查
    - unit_test_generation: 单元测试生成
    - tia_analysis: TIA 影响分析
    - root_cause_analysis: 根因分析
    """
    service = AIService()
    
    try:
        result = await service.execute(
            task_type=request.task_type,
            project_id=request.project_id,
            input_data=request.input_data,
            options=request.options
        )
        
        return AIResponse(**result)
        
    except Exception as e:
        logger.error(f"AI 网关处理失败: {str(e)}")
        return AIResponse(
            success=False,
            error=f"AI 服务异常: {str(e)}"
        )


@router.get("/ai/usage-stats")
async def get_usage_stats():
    """获取 AI 使用统计"""
    service = AIService()
    try:
        stats = await service.get_usage_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取使用统计失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/ai/health")
async def health_check():
    """健康检查"""
    try:
        from app.ai.config import AI_CONFIG
        
        return {
            "status": "healthy",
            "default_provider": AI_CONFIG["default_provider"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))