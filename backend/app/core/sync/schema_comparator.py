"""JSON Schema 对比算法（Diff 计算）
符合后端代码规范：
1. 使用类型注解
2. 清晰的日志记录
3. 幂等性保证
"""
from typing import Dict, List, Any, Optional, Set
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class DiffType(str, Enum):
    """变更类型枚举"""
    ADDED = "added"           # 新增
    REMOVED = "removed"       # 删除
    CHANGED = "changed"       # 修改
    UNCHANGED = "unchanged"   # 未变更


class DiffLocation(str, Enum):
    """变更位置枚举"""
    REQUEST = "request"       # 请求
    RESPONSE = "response"     # 响应


class SchemaDiff:
    """Schema 差异结果"""
    
    def __init__(self):
        self.added: List[Dict[str, Any]] = []      # 新增的字段
        self.removed: List[Dict[str, Any]] = []    # 删除的字段
        self.changed: List[Dict[str, Any]] = []    # 修改的字段
        self.unchanged: List[str] = []            # 未变更的字段
        self.diff_summary: Dict[str, int] = {}    # 差异摘要
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "summary": self.diff_summary
        }


class SchemaComparator:
    """JSON Schema 对比器"""
    
    def __init__(self):
        self.trace_id = None
    
    def compare(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any], trace_id: Optional[str] = None) -> SchemaDiff:
        """
        对比两个 JSON Schema
        
        Args:
            old_schema: 旧 Schema
            new_schema: 新 Schema
            trace_id: 追踪 ID
            
        Returns:
            SchemaDiff: 差异结果
        """
        self.trace_id = trace_id or "unknown"
        
        logger.info(f"[{self.trace_id}] 开始对比 Schema")
        
        result = SchemaDiff()
        
        # 提取所有字段
        old_fields = self._extract_all_fields(old_schema)
        new_fields = self._extract_all_fields(new_schema)
        
        old_field_names = set(old_fields.keys())
        new_field_names = set(new_fields.keys())
        
        # 1. 识别新增字段
        added_names = new_field_names - old_field_names
        for name in added_names:
            field_info = new_fields[name]
            result.added.append({
                "field": name,
                "type": field_info.get("type", "unknown"),
                "location": field_info.get("location", "unknown"),
                "description": field_info.get("description", "")
            })
            logger.debug(f"[{self.trace_id}] 新增字段: {name}")
        
        # 2. 识别删除字段
        removed_names = old_field_names - new_field_names
        for name in removed_names:
            field_info = old_fields[name]
            result.removed.append({
                "field": name,
                "type": field_info.get("type", "unknown"),
                "location": field_info.get("location", "unknown"),
                "description": field_info.get("description", "")
            })
            logger.debug(f"[{self.trace_id}] 删除字段: {name}")
        
        # 3. 识别修改字段
        common_names = old_field_names & new_field_names
        for name in common_names:
            old_field = old_fields[name]
            new_field = new_fields[name]
            
            # 对比字段类型
            if old_field.get("type") != new_field.get("type"):
                result.changed.append({
                    "field": name,
                    "location": new_field.get("location", "unknown"),
                    "old_type": old_field.get("type", "unknown"),
                    "new_type": new_field.get("type", "unknown"),
                    "change_type": "type"
                })
                logger.debug(f"[{self.trace_id}] 字段类型变更: {name} ({old_field.get('type')} -> {new_field.get('type')})")
            
            # 对比字段描述
            elif old_field.get("description") != new_field.get("description"):
                result.changed.append({
                    "field": name,
                    "location": new_field.get("location", "unknown"),
                    "old_description": old_field.get("description", ""),
                    "new_description": new_field.get("description", ""),
                    "change_type": "description"
                })
                logger.debug(f"[{self.trace_id}] 字段描述变更: {name}")
            
            # 对比嵌套结构
            elif old_field.get("schema") and new_field.get("schema"):
                nested_diff = self.compare(
                    old_field.get("schema", {}),
                    new_field.get("schema", {}),
                    self.trace_id
                )
                if nested_diff.has_changes():
                    result.changed.append({
                        "field": name,
                        "location": new_field.get("location", "unknown"),
                        "nested_diff": nested_diff.to_dict(),
                        "change_type": "nested"
                    })
                    logger.debug(f"[{self.trace_id}] 嵌套结构变更: {name}")
            
            else:
                result.unchanged.append(name)
        
        # 生成摘要
        result.diff_summary = {
            "added_count": len(result.added),
            "removed_count": len(result.removed),
            "changed_count": len(result.changed),
            "unchanged_count": len(result.unchanged),
            "total_changes": len(result.added) + len(result.removed) + len(result.changed)
        }
        
        logger.info(f"[{self.trace_id}] Schema 对比完成: {result.diff_summary}")
        
        return result
    
    def has_changes(self) -> bool:
        """是否有变更"""
        # 这个方法会在 SchemaDiff 类中实现
        pass
    
    def _extract_all_fields(self, schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        递归提取 Schema 中的所有字段
        
        Args:
            schema: JSON Schema 对象
            
        Returns:
            Dict: 字段名到字段信息的映射
        """
        fields = {}
        
        if not isinstance(schema, dict):
            return fields
        
        # 处理对象类型
        if schema.get("type") == "object" and "properties" in schema:
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            for field_name, field_schema in properties.items():
                fields[field_name] = {
                    "type": field_schema.get("type", "unknown"),
                    "required": field_name in required,
                    "description": field_schema.get("description", ""),
                    "location": "object"
                }
                
                # 递归提取嵌套对象的字段
                if field_schema.get("type") == "object" and "properties" in field_schema:
                    nested_fields = self._extract_all_fields(field_schema)
                    # 将嵌套字段添加到结果中（带路径）
                    for nested_name, nested_info in nested_fields.items():
                        nested_path = f"{field_name}.{nested_name}"
                        fields[nested_path] = {
                            "type": nested_info.get("type", "unknown"),
                            "required": nested_info.get("required", False),
                            "description": nested_info.get("description", ""),
                            "location": "object"
                        }
        
        return fields
    
    def compare_api_schemas(
        self, 
        old_request: Dict[str, Any], 
        old_response: Dict[str, Any],
        new_request: Dict[str, Any], 
        new_response: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        对比完整的 API Schema（请求 + 响应）
        
        Args:
            old_request: 旧请求 Schema
            old_response: 旧响应 Schema
            new_request: 新请求 Schema
            new_response: 新响应 Schema
            trace_id: 追踪 ID
            
        Returns:
            Dict: 完整的差异结果
        """
        self.trace_id = trace_id or "unknown"
        
        logger.info(f"[{self.trace_id}] 开始对比 API Schema")
        
        # 对比请求 Schema
        request_diff = self.compare(old_request, new_request, f"{self.trace_id}_request")
        
        # 对比响应 Schema
        response_diff = self.compare(old_response, new_response, f"{self.trace_id}_response")
        
        result = {
            "request_diff": request_diff.to_dict(),
            "response_diff": response_diff.to_dict(),
            "summary": {
                "request_changes": request_diff.diff_summary.get("total_changes", 0),
                "response_changes": response_diff.diff_summary.get("total_changes", 0),
                "total_changes": request_diff.diff_summary.get("total_changes", 0) + response_diff.diff_summary.get("total_changes", 0)
            },
            "has_changes": request_diff.has_changes() or response_diff.has_changes()
        }
        
        logger.info(f"[{self.trace_id}] API Schema 对比完成: {result['summary']}")
        
        return result


# 扩展 SchemaDiff 类
def has_changes(self) -> bool:
    """是否有变更"""
    return len(self.added) > 0 or len(self.removed) > 0 or len(self.changed) > 0

# 将方法绑定到类
SchemaDiff.has_changes = has_changes