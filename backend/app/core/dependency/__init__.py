"""接口依赖分析模块"""
from .analyzer import DependencyAnalyzer
from .graph_builder import GraphBuilder
from .module_analyzer import ModuleAnalyzer
from .module_dependency_analyzer import ModuleDependencyAnalyzer
from .resource_lifecycle_analyzer import ResourceLifecycleAnalyzer
from .resource_context_analyzer import ResourceContextAnalyzer

__all__ = [
    'DependencyAnalyzer',
    'GraphBuilder',
    'ModuleAnalyzer',
    'ModuleDependencyAnalyzer',
    'ResourceLifecycleAnalyzer',
    'ResourceContextAnalyzer',
]

# 导入 ModuleAnalyzerV2，兼容旧代码
try:
    from .module_analyzer_v2 import ModuleAnalyzerV2, create_module_analyzer
    __all__.extend(['ModuleAnalyzerV2', 'create_module_analyzer'])
except ImportError:
    pass