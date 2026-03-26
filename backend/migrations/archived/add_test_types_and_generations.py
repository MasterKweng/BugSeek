"""添加测试类型和脚本生成记录表"""

from app.db.base import Base
from app.db.session import engine


def upgrade():
    """创建新表"""
    Base.metadata.create_all(bind=engine)
    print("表创建成功")


if __name__ == "__main__":
    upgrade()