from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.db.base import User
from jose import JWTError, jwt
from app.config import settings
import logging
import threading
from functools import lru_cache

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# 用户缓存（简单内存缓存，生产环境建议使用Redis）
_user_cache = {}
_user_cache_lock = threading.Lock()


def clear_user_cache():
    """清除用户缓存"""
    with _user_cache_lock:
        _user_cache.clear()
    logger.info("用户缓存已清除")


@lru_cache(maxsize=128)
def _get_user_by_username_cached(username: str, db_session_id: int) -> User | None:
    """
    缓存的用户查询函数
    注意：包含session_id确保缓存不会跨session共享
    """
    from app.dependencies import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        return user
    finally:
        db.close()


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    获取当前登录用户
    优化：添加缓存机制，减少数据库查询
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 如果OAuth2PasswordBearer没有提取到token，尝试手动提取
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            raise credentials_exception

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"JWT解码失败: {str(e)}")
        raise credentials_exception

    # 使用内存缓存减少数据库查询
    with _user_cache_lock:
        if username in _user_cache:
            logger.debug(f"从缓存获取用户: {username}")
            cached_user = _user_cache[username]
            # 将缓存对象合并到当前会话以避免 DetachedInstanceError
            return db.merge(cached_user)

    # 缓存未命中，从数据库查询
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        logger.warning(f"用户不存在: {username}")
        raise credentials_exception

    # 更新缓存（使用 expunge 断开会话连接）
    db.expunge(user)
    with _user_cache_lock:
        _user_cache[username] = user

    return db.merge(user)