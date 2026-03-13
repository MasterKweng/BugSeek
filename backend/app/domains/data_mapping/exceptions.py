"""
字段映射模块异常定义

遵循后端代码规范：
- 统一的异常处理
- 清晰的异常类型定义
"""


class FieldMappingException(Exception):
    """字段映射基础异常"""
    pass


class TaskCancelledException(FieldMappingException):
    """任务取消异常"""
    pass


class SchemaParseException(FieldMappingException):
    """数据库结构解析异常"""
    pass


class AIServiceException(FieldMappingException):
    """AI服务调用异常"""
    pass


class ConfigurationException(FieldMappingException):
    """配置异常"""
    pass