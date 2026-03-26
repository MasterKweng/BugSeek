-- 数据库迁移脚本：添加版本与接口的关联表
-- 执行时间: 请手动填写


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
