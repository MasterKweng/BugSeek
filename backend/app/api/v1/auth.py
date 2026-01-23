from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import bcrypt
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr
import logging
from app.dependencies import get_db
from app.db.base import User
from app.api.v1.deps import get_current_user
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic 模型
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    nickname: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class UpdateProfile(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class ApiResponse(BaseModel):
    code: int = 0
    message: str
    data: Optional[dict] = None


# 工具函数
def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt 限制密码最多 72 字节
    truncated_password = plain_password[:72].encode('utf-8')
    return bcrypt.checkpw(truncated_password, hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    # bcrypt 限制密码最多 72 字节
    truncated_password = password[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(truncated_password, salt).decode('utf-8')


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


# API 接口
@router.post("/register", response_model=ApiResponse)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """用户注册"""
    logger.info(f"用户注册请求: username={user_data.username}, email={user_data.email}")

    # 检查用户名是否已存在
    if db.query(User).filter(User.username == user_data.username).first():
        logger.warning(f"注册失败: 用户名已存在 - {user_data.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 检查邮箱是否已存在
    if db.query(User).filter(User.email == user_data.email).first():
        logger.warning(f"注册失败: 邮箱已存在 - {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已存在"
        )

    # 创建用户
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        nickname=user_data.nickname
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"用户注册成功: user_id={user.id}, username={user.username}")
    return ApiResponse(
        message="注册成功",
        data={"user": UserResponse.model_validate(user).model_dump()}
    )


@router.post("/login", response_model=ApiResponse)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    logger.info(f"用户登录请求: username={user_data.username}")

    user = db.query(User).filter(User.username == user_data.username).first()

    if not user or not verify_password(user_data.password, user.password_hash):
        logger.warning(f"登录失败: 用户名或密码错误 - {user_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    access_token = create_access_token(data={"sub": user.username})

    logger.info(f"用户登录成功: user_id={user.id}, username={user.username}")
    return ApiResponse(
        message="登录成功",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": UserResponse.model_validate(user).model_dump()
        }
    )


@router.get("/me", response_model=ApiResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return ApiResponse(
        message="success",
        data=UserResponse.model_validate(current_user).model_dump()
    )


@router.post("/logout", response_model=ApiResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """用户登出"""
    logger.info(f"用户登出: user_id={current_user.id}, username={current_user.username}")
    return ApiResponse(message="登出成功")


@router.put("/password", response_model=ApiResponse)
async def change_password(
    password_data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    logger.info(f"用户修改密码: user_id={current_user.id}, username={current_user.username}")

    if not verify_password(password_data.old_password, current_user.password_hash):
        logger.warning(f"修改密码失败: 旧密码错误 - user_id={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )

    current_user.password_hash = get_password_hash(password_data.new_password)
    db.commit()

    logger.info(f"密码修改成功: user_id={current_user.id}")
    return ApiResponse(message="密码修改成功")


@router.put("/profile", response_model=ApiResponse)
async def update_profile(
    profile_data: UpdateProfile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户信息"""
    logger.info(f"用户更新信息: user_id={current_user.id}, username={current_user.username}")

    if profile_data.nickname is not None:
        current_user.nickname = profile_data.nickname
    if profile_data.avatar is not None:
        current_user.avatar = profile_data.avatar

    db.commit()
    db.refresh(current_user)

    logger.info(f"用户信息更新成功: user_id={current_user.id}")
    return ApiResponse(
        message="更新成功",
        data=UserResponse.model_validate(current_user).model_dump()
    )