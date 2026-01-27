"""创建测试用户"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import bcrypt
from app.db.base import Base, User
from app.db.session import engine

def get_password_hash(password: str) -> str:
    truncated_password = password[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(truncated_password, salt).decode('utf-8')

# 创建表
Base.metadata.create_all(bind=engine)

from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# 检查是否已存在测试用户
existing_user = db.query(User).filter(User.username == "test").first()
if existing_user:
    print(f"测试用户已存在: {existing_user.username}")
else:
    # 创建测试用户
    test_user = User(
        username="test",
        email="test@example.com",
        password_hash=get_password_hash("test123"),
        nickname="测试用户",
        is_active=True
    )
    db.add(test_user)
    db.commit()
    print(f"测试用户创建成功: {test_user.username}")

db.close()