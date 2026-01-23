"""
数据库迁移脚本：添加版本与接口的关联表
- 创建 version_endpoints 表
- 移除 api_endpoints 表的 version_id 字段
- 清空现有 API 数据

使用方法：
1. 确保数据库服务正在运行
2. 运行: python migrations/add_version_endpoint_table.py
"""

# SQL 迁移脚本
SQL_UPGRADE = """
-- 1. 清空现有 API 数据
DELETE FROM api_endpoints;

-- 2. 移除 api_endpoints 表的 version_id 字段
ALTER TABLE api_endpoints DROP COLUMN IF EXISTS version_id;

-- 3. 移除相关索引
DROP INDEX IF EXISTS ix_api_endpoints_version_id;

-- 4. 创建 version_endpoints 表
CREATE TABLE IF NOT EXISTS version_endpoints (
    id SERIAL PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    endpoint_id INTEGER NOT NULL REFERENCES api_endpoints(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. 创建索引
CREATE INDEX IF NOT EXISTS ix_version_endpoints_version_id ON version_endpoints(version_id);
CREATE INDEX IF NOT EXISTS ix_version_endpoints_endpoint_id ON version_endpoints(endpoint_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_version_endpoint ON version_endpoints(version_id, endpoint_id);
"""

SQL_DOWNGRADE = """
-- 1. 删除 version_endpoints 表
DROP TABLE IF EXISTS version_endpoints;

-- 2. 恢复 api_endpoints 表的 version_id 字段
ALTER TABLE api_endpoints ADD COLUMN IF NOT EXISTS version_id INTEGER REFERENCES versions(id);
CREATE INDEX IF NOT EXISTS ix_api_endpoints_version_id ON api_endpoints(version_id);
"""


def print_sql_upgrade():
    """打印升级 SQL"""
    print("=" * 60)
    print("数据库迁移 SQL - 升级")
    print("=" * 60)
    print(SQL_UPGRADE)
    print("=" * 60)
    print("\n请手动执行上述 SQL 语句来完成迁移。")
    print("\n或者使用 psql 命令行工具执行：")
    print("psql -h 172.23.113.132 -U bugseek -d bugseek -f migrations/add_version_endpoint_table.sql")


def print_sql_downgrade():
    """打印回滚 SQL"""
    print("=" * 60)
    print("数据库迁移 SQL - 回滚")
    print("=" * 60)
    print(SQL_DOWNGRADE)
    print("=" * 60)
    print("\n请手动执行上述 SQL 语句来回滚迁移。")


def save_sql_file():
    """保存 SQL 到文件"""
    with open("D:\\code\\BugSeek\\backend\\migrations\\add_version_endpoint_table.sql", "w", encoding="utf-8") as f:
        f.write("-- 数据库迁移脚本：添加版本与接口的关联表\n")
        f.write("-- 执行时间: 请手动填写\n\n")
        f.write(SQL_UPGRADE)
    print("✅ SQL 文件已保存到: migrations/add_version_endpoint_table.sql")


if __name__ == "__main__":
    import sys

    print("\n数据库迁移脚本生成器\n")

    if len(sys.argv) > 1:
        if sys.argv[1] == "downgrade":
            print_sql_downgrade()
        else:
            print_sql_upgrade()
    else:
        # 默认保存 SQL 文件
        save_sql_file()
        print_sql_upgrade()