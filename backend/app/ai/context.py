"""上下文注入器"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.db.base import Project
import logging

logger = logging.getLogger(__name__)


class ContextInjector:
    """上下文注入器 - 自动注入项目技术栈信息"""
    
    async def inject(self, project_id: int) -> Dict[str, Any]:
        """
        注入项目上下文
        
        Args:
            project_id: 项目ID
            
        Returns:
            Dict: 项目上下文信息
        """
        if not project_id:
            return {}
        
        db = next(get_db())
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if project:
                context = {
                    "project_name": project.name or "",
                    "business_domain": project.business_domain or "",
                    "backend_language": project.backend_language or "",
                    "backend_framework": project.backend_framework or "",
                    "database": project.database or "",
                    "frontend_framework": project.frontend_framework or ""
                }
                
                # 构建 tech_stack 字符串
                tech_stack_parts = []
                if project.backend_language:
                    tech_stack_parts.append(project.backend_language)
                if project.backend_framework:
                    tech_stack_parts.append(project.backend_framework)
                if project.database:
                    tech_stack_parts.append(project.database)
                context["tech_stack"] = "/".join(tech_stack_parts) if tech_stack_parts else ""
                
                logger.info(f"注入项目上下文: project_id={project_id}, name={project.name}")
                return context
            else:
                logger.warning(f"项目不存在: project_id={project_id}")
                return {}
                
        except Exception as e:
            logger.error(f"注入项目上下文失败: {str(e)}")
            return {}
        finally:
            db.close()