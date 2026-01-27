"""根据 tags 为接口创建分组并关联"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine
from app.core.logging_config import setup_logging
import logging

setup_logging('INFO')
logger = logging.getLogger(__name__)


def organize_endpoints_by_tags():
    """根据 tags 为接口创建分组并关联"""
    try:
        with engine.connect() as conn:
            # 1. 获取所有有 tags 的接口
            result = conn.execute(text("""
                SELECT id, project_id, path, method, tags
                FROM api_endpoints
                WHERE tags IS NOT NULL
                AND json_array_length(tags) > 0
                AND group_id IS NULL
                AND project_id IS NOT NULL
            """))
            
            endpoints = result.fetchall()
            logger.info(f"找到 {len(endpoints)} 个未分组的接口")
            
            if not endpoints:
                logger.info("没有需要处理的接口")
                return
            
            # 2. 为每个 tag 创建分组（如果不存在）
            tag_to_group_id = {}
            
            for endpoint in endpoints:
                tags = endpoint.tags
                if not tags:
                    continue
                
                # 使用第一个 tag 作为分组依据
                tag = tags[0]
                project_id = endpoint.project_id
                
                # 检查分组是否已存在
                if tag not in tag_to_group_id:
                    group_result = conn.execute(text("""
                        SELECT id FROM api_endpoint_groups
                        WHERE project_id = :project_id AND name = :name
                    """), {"project_id": project_id, "name": tag})
                    
                    existing_group = group_result.fetchone()
                    
                    if existing_group:
                        tag_to_group_id[tag] = existing_group[0]
                        logger.info(f"分组 '{tag}' 已存在，ID: {existing_group[0]}")
                    else:
                        # 创建新分组
                        insert_result = conn.execute(text("""
                            INSERT INTO api_endpoint_groups (project_id, name, description, sort_order)
                            VALUES (:project_id, :name, :description, :sort_order)
                            RETURNING id
                        """), {
                            "project_id": project_id,
                            "name": tag,
                            "description": f"接口分组: {tag}",
                            "sort_order": 0
                        })
                        group_id = insert_result.fetchone()[0]
                        tag_to_group_id[tag] = group_id
                        logger.info(f"创建新分组 '{tag}'，ID: {group_id}")
                
                # 3. 关联接口到分组
                group_id = tag_to_group_id[tag]
                conn.execute(text("""
                    UPDATE api_endpoints
                    SET group_id = :group_id
                    WHERE id = :endpoint_id
                """), {"group_id": group_id, "endpoint_id": endpoint.id})
                
                logger.info(f"接口 {endpoint.method} {endpoint.path} -> 分组 '{tag}' (ID: {group_id})")
            
            conn.commit()
            
            # 4. 统计结果
            stats_result = conn.execute(text("""
                SELECT 
                    g.name as group_name,
                    COUNT(e.id) as endpoint_count
                FROM api_endpoint_groups g
                LEFT JOIN api_endpoints e ON g.id = e.group_id
                GROUP BY g.id, g.name
                ORDER BY endpoint_count DESC
            """))
            
            logger.info("\n=== 分组统计 ===")
            for row in stats_result:
                logger.info(f"  {row.group_name}: {row.endpoint_count} 个接口")
            
            logger.info("\n✅ 接口分组完成！")
            
    except Exception as e:
        logger.error(f"❌ 接口分组失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logger.info("开始根据 tags 组织接口...")
    organize_endpoints_by_tags()
