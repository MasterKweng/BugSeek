"""测试类型管理接口"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel
import logging

from app.dependencies import get_db
from app.api.v1.deps import get_current_user
from app.db.base import TestType, User, Project
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Pydantic 模型 ==========

class TestTypeCreate(BaseModel):
    """创建测试类型请求"""
    name: str
    code: str
    description: Optional[str] = None


class TestTypeUpdate(BaseModel):
    """更新测试类型请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TestTypeResponse(BaseModel):
    """测试类型响应"""
    id: int
    project_id: int
    name: str
    code: str
    description: Optional[str]
    is_preset: bool
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            project_id=obj.project_id,
            name=obj.name,
            code=obj.code,
            description=obj.description,
            is_preset=obj.is_preset,
            is_active=obj.is_active,
            sort_order=obj.sort_order,
        )


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


# 预设测试类型
PRESET_TEST_TYPES = [
    {"code": "positive", "name": "正向测试", "description": "使用符合业务语义的正常参数测试"},
    {"code": "negative", "name": "逆向测试", "description": "缺失必填参数、错误类型参数测试"},
    {"code": "boundary", "name": "边界测试", "description": "边界值、空值测试"},
    {"code": "exception", "name": "异常测试", "description": "超长字符串、特殊字符测试"},
]


# ========== 核心接口 ==========

@router.get("/test-types", response_model=ApiResponse)
async def get_test_types(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试类型列表"""
    trace_id = get_trace_id()
    
    # 如果没有指定 project_id，使用用户当前项目
    if project_id is None:
        from app.context import get_current_project_id
        project_id = get_current_project_id(db, current_user)
    
    logger.info(f"[{trace_id}] 获取测试类型列表: project_id={project_id}")
    
    # 获取预设类型
    preset_types = []
    for preset in PRESET_TEST_TYPES:
        preset_types.append({
            "code": preset["code"],
            "name": preset["name"],
            "description": preset["description"],
            "is_preset": True
        })
    
    # 获取自定义类型
    custom_types = db.query(TestType).filter(
        TestType.project_id == project_id,
        TestType.is_active == True
    ).order_by(TestType.sort_order).all()
    
    custom_type_responses = [TestTypeResponse.from_orm(t).model_dump() for t in custom_types]
    
    return ApiResponse(
        message="success",
        data={
            "preset_types": preset_types,
            "custom_types": custom_type_responses
        }
    )


@router.post("/test-types", response_model=ApiResponse)
async def create_test_type(
    request: TestTypeCreate,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建自定义测试类型"""
    trace_id = get_trace_id()
    
    # 如果没有指定 project_id，使用用户当前项目
    if project_id is None:
        from app.context import get_current_project_id
        project_id = get_current_project_id(db, current_user)
    
    # 验证项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 检查是否与预设类型冲突
    for preset in PRESET_TEST_TYPES:
        if preset["code"] == request.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不能使用预设类型代码: {request.code}"
            )
    
    # 检查是否已存在
    existing = db.query(TestType).filter(
        TestType.project_id == project_id,
        TestType.code == request.code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该测试类型代码已存在"
        )
    
    # 创建测试类型
    test_type = TestType(
        project_id=project_id,
        name=request.name,
        code=request.code,
        description=request.description,
        is_preset=False,
        is_active=True,
        sort_order=0
    )
    
    db.add(test_type)
    db.commit()
    db.refresh(test_type)
    
    logger.info(f"[{trace_id}] 创建测试类型成功: code={request.code}, name={request.name}")
    
    return ApiResponse(
        message="创建成功",
        data=TestTypeResponse.from_orm(test_type).model_dump()
    )


@router.put("/test-types/{test_type_id}", response_model=ApiResponse)
async def update_test_type(
    test_type_id: int,
    request: TestTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新测试类型"""
    trace_id = get_trace_id()
    
    test_type = db.query(TestType).filter(TestType.id == test_type_id).first()
    
    if not test_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试类型不存在"
        )
    
    # 不允许修改预设类型
    if test_type.is_preset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改预设类型"
        )
    
    # 更新字段
    if request.name is not None:
        test_type.name = request.name
    if request.description is not None:
        test_type.description = request.description
    if request.is_active is not None:
        test_type.is_active = request.is_active
    
    db.commit()
    db.refresh(test_type)
    
    logger.info(f"[{trace_id}] 更新测试类型成功: id={test_type_id}")
    
    return ApiResponse(
        message="更新成功",
        data=TestTypeResponse.from_orm(test_type).model_dump()
    )


@router.delete("/test-types/{test_type_id}", response_model=ApiResponse)
async def delete_test_type(
    test_type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除测试类型"""
    trace_id = get_trace_id()
    
    test_type = db.query(TestType).filter(TestType.id == test_type_id).first()
    
    if not test_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试类型不存在"
        )
    
    # 不允许删除预设类型
    if test_type.is_preset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除预设类型"
        )
    
    db.delete(test_type)
    db.commit()
    
    logger.info(f"[{trace_id}] 删除测试类型成功: id={test_type_id}")
    
    return ApiResponse(message="删除成功")