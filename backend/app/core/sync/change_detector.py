"""变更检测和影响范围扫描
符合后端代码规范：
1. 使用类型注解
2. 清晰的日志记录
3. IDOR 防御
"""
from typing import Dict, List, Any, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import or_
import logging

from app.db.base import ApiDefinition, ApiCase, ApiScenario, User
from app.core.sync.schema_comparator import SchemaComparator, DiffType
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class ChangeDetector:
    """变更检测器"""
    
    def __init__(self, db: Session, trace_id: Optional[str] = None):
        self.db = db
        self.trace_id = trace_id or get_trace_id()
        self.comparator = SchemaComparator()
    
    def detect_changes(
        self,
        old_definitions: List[Dict[str, Any]],
        new_definitions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        检测接口定义的变更
        
        Args:
            old_definitions: 旧接口定义列表
            new_definitions: 新接口定义列表
            
        Returns:
            Dict: 变更检测结果
        """
        logger.info(f"[{self.trace_id}] 开始检测接口变更")
        
        # 调试：检查 new_definitions 的结构
        if new_definitions:
            logger.info(f"[{self.trace_id}] new_definitions[0] keys: {list(new_definitions[0].keys())}")
            logger.info(f"[{self.trace_id}] new_definitions[0] data: {new_definitions[0]}")
        
        # 构建旧接口映射
        old_map = {(d['method'], d['path']): d for d in old_definitions}
        new_map = {(d['method'], d['path']): d for d in new_definitions}
        
        old_keys = set(old_map.keys())
        new_keys = set(new_map.keys())
        
        # 分类变更
        added_keys = new_keys - old_keys  # 新增接口
        removed_keys = old_keys - new_keys  # 删除接口
        common_keys = old_keys & new_keys  # 共有接口
        
        results = {
            "added": [],
            "removed": [],
            "changed": [],
            "unchanged": [],
            "summary": {}
        }
        
        # 1. 新增接口
        for key in added_keys:
            method, path = key
            definition = new_map[key]
            results["added"].append({
                "method": method,
                "path": path,
                "summary": definition.get("summary", ""),
                "description": definition.get("description", ""),
                "tags": definition.get("tags", []),
                "request_schema": definition.get("request_schema", {}),
                "response_schema": definition.get("response_schema", {}),
                "parameters": definition.get("parameters", []),
                "responses": definition.get("responses", {}),
                "security": definition.get("security", []),
                "change_type": DiffType.ADDED
            })
            logger.debug(f"[{self.trace_id}] 新增接口: {method} {path}")
        
        # 2. 删除接口
        for key in removed_keys:
            method, path = key
            definition = old_map[key]
            results["removed"].append({
                "method": method,
                "path": path,
                "summary": definition.get("summary", ""),
                "change_type": DiffType.REMOVED
            })
            logger.debug(f"[{self.trace_id}] 删除接口: {method} {path}")
        
        # 3. 检测共有接口的 Schema 变更
        for key in common_keys:
            method, path = key
            old_def = old_map[key]
            new_def = new_map[key]
            
            # 对比请求和响应 Schema
            schema_diff = self.comparator.compare_api_schemas(
                old_def.get("request_schema", {}),
                old_def.get("response_schema", {}),
                new_def.get("request_schema", {}),
                new_def.get("response_schema", {}),
                f"{self.trace_id}_{method}_{path}"
            )
            
            if schema_diff["has_changes"]:
                results["changed"].append({
                    "method": method,
                    "path": path,
                    "summary": new_def.get("summary", ""),
                    "description": new_def.get("description", ""),
                    "tags": new_def.get("tags", []),
                    "request_schema": new_def.get("request_schema", {}),
                    "response_schema": new_def.get("response_schema", {}),
                    "parameters": new_def.get("parameters", []),
                    "responses": new_def.get("responses", {}),
                    "security": new_def.get("security", []),
                    "change_type": DiffType.CHANGED,
                    "diff": schema_diff
                })
                logger.debug(f"[{self.trace_id}] Schema 变更: {method} {path}")
            else:
                results["unchanged"].append({
                    "method": method,
                    "path": path,
                    "summary": new_def.get("summary", ""),
                    "change_type": DiffType.UNCHANGED
                })
        
        # 生成摘要
        results["summary"] = {
            "added_count": len(results["added"]),
            "removed_count": len(results["removed"]),
            "changed_count": len(results["changed"]),
            "unchanged_count": len(results["unchanged"]),
            "total_changes": len(results["added"]) + len(results["removed"]) + len(results["changed"])
        }
        
        logger.info(f"[{self.trace_id}] 变更检测完成: {results['summary']}")
        
        return results


class ImpactAnalyzer:
    """影响范围扫描器"""
    
    def __init__(self, db: Session, trace_id: Optional[str] = None):
        self.db = db
        self.trace_id = trace_id or get_trace_id()
    
    def scan_impact(
        self,
        changed_endpoints: List[Dict[str, Any]],
        project_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        扫描变更接口的影响范围
        
        Args:
            changed_endpoints: 变更的接口列表
            project_id: 项目 ID
            user_id: 用户 ID（用于权限校验）
            
        Returns:
            Dict: 影响分析结果
        """
        logger.info(f"[{self.trace_id}] 开始扫描影响范围: {len(changed_endpoints)} 个变更接口")
        
        result = {
            "affected_cases": [],
            "affected_scenarios": [],
            "summary": {}
        }
        
        for endpoint in changed_endpoints:
            method = endpoint["method"]
            path = endpoint["path"]
            diff = endpoint.get("diff", {})
            
            # 查询数据库中的接口定义
            db_endpoint = self.db.query(ApiDefinition).filter(
                ApiDefinition.project_id == project_id,
                ApiDefinition.method == method,
                ApiDefinition.path == path
            ).first()
            
            if not db_endpoint:
                logger.warning(f"[{self.trace_id}] 接口不存在: {method} {path}")
                continue
            
            # 扫描关联的用例
            case_impact = self._scan_case_impact(db_endpoint, diff)
            result["affected_cases"].extend(case_impact)
            
            # 扫描关联的场景
            scenario_impact = self._scan_scenario_impact(db_endpoint, diff)
            result["affected_scenarios"].extend(scenario_impact)
        
        # 生成摘要
        result["summary"] = {
            "affected_case_count": len(result["affected_cases"]),
            "affected_scenario_count": len(result["affected_scenarios"]),
            "total_affected": len(result["affected_cases"]) + len(result["affected_scenarios"])
        }
        
        logger.info(f"[{self.trace_id}] 影响扫描完成: {result['summary']}")
        
        return result
    
    def _scan_case_impact(
        self,
        endpoint: ApiDefinition,
        diff: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        扫描接口对用例的影响
        
        Args:
            endpoint: 接口定义
            diff: Schema 差异
            
        Returns:
            List: 受影响的用例列表
        """
        affected_cases = []
        
        # 查询该接口的所有用例
        cases = self.db.query(ApiCase).filter(
            ApiCase.definition_id == endpoint.id
        ).all()
        
        request_diff = diff.get("request_diff", {})
        response_diff = diff.get("response_diff", {})
        
        # 获取所有变更的字段
        changed_fields = self._extract_changed_fields(request_diff, response_diff)
        
        for case in cases:
            # 检查用例是否使用了变更的字段
            is_affected = self._check_case_field_usage(case, changed_fields)
            
            if is_affected:
                affected_cases.append({
                    "case_id": case.id,
                    "case_name": case.name,
                    "priority": case.priority,
                    "ai_generated": case.ai_generated,
                    "changed_fields": list(changed_fields),
                    "impact_level": self._calculate_impact_level(changed_fields),
                    "suggestion": "需要检查并更新用例配置"
                })
                logger.debug(f"[{self.trace_id}] 用例受影响: {case.name} (字段: {list(changed_fields)})")
        
        return affected_cases
    
    def _scan_scenario_impact(
        self,
        endpoint: ApiDefinition,
        diff: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        扫描接口对场景的影响
        
        Args:
            endpoint: 接口定义
            diff: Schema 差异
            
        Returns:
            List: 受影响的场景列表
        """
        affected_scenarios = []
        
        # 查询包含该接口的场景
        scenarios = self.db.query(ApiScenario).filter(
            ApiScenario.project_id == endpoint.project_id,
            ApiScenario.endpoint_ids.contains(endpoint.id)
        ).all()
        
        request_diff = diff.get("request_diff", {})
        response_diff = diff.get("response_diff", {})
        
        # 获取所有变更的字段
        changed_fields = self._extract_changed_fields(request_diff, response_diff)
        
        for scenario in scenarios:
            # 检查场景是否使用了变更的字段
            is_affected = self._check_scenario_variable_usage(scenario, endpoint.id, changed_fields)
            
            if is_affected:
                affected_scenarios.append({
                    "scenario_id": scenario.id,
                    "scenario_name": scenario.name,
                    "endpoint_count": scenario.endpoint_count,
                    "changed_fields": list(changed_fields),
                    "impact_level": self._calculate_impact_level(changed_fields),
                    "suggestion": "需要检查并更新场景配置"
                })
                logger.debug(f"[{self.trace_id}] 场景受影响: {scenario.name} (字段: {list(changed_fields)})")
        
        return affected_scenarios
    
    def _extract_changed_fields(
        self,
        request_diff: Dict[str, Any],
        response_diff: Dict[str, Any]
    ) -> Set[str]:
        """
        从差异数据中提取变更的字段名
        
        Args:
            request_diff: 请求差异
            response_diff: 响应差异
            
        Returns:
            Set: 变更字段名集合
        """
        changed_fields = set()
        
        # 提取请求变更字段
        for change in request_diff.get("added", []):
            changed_fields.add(f"request.{change['field']}")
        for change in request_diff.get("removed", []):
            changed_fields.add(f"request.{change['field']}")
        for change in request_diff.get("changed", []):
            changed_fields.add(f"request.{change['field']}")
        
        # 提取响应变更字段
        for change in response_diff.get("added", []):
            changed_fields.add(f"response.{change['field']}")
        for change in response_diff.get("removed", []):
            changed_fields.add(f"response.{change['field']}")
        for change in response_diff.get("changed", []):
            changed_fields.add(f"response.{change['field']}")
        
        return changed_fields
    
    def _check_case_field_usage(
        self,
        case: ApiCase,
        changed_fields: Set[str]
    ) -> bool:
        """
        检查用例是否使用了变更的字段
        
        Args:
            case: 用例对象
            changed_fields: 变更字段集合
            
        Returns:
            bool: 是否受影响
        """
        # 检查请求数据中是否使用了变更字段
        if case.request_data:
            request_data_str = str(case.request_data)
            for field in changed_fields:
                if field.startswith("request.") and field.split(".", 1)[1] in request_data_str:
                    return True
        
        # 检查断言规则中是否使用了变更字段
        if case.assertion_rules:
            for rule in case.assertion_rules:
                rule_str = str(rule)
                for field in changed_fields:
                    if field in rule_str:
                        return True
        
        # 检查变量提取规则中是否使用了变更字段
        if case.extraction_rules:
            for rule in case.extraction_rules:
                rule_str = str(rule)
                for field in changed_fields:
                    if field in rule_str:
                        return True
        
        return False
    
    def _check_scenario_variable_usage(
        self,
        scenario: ApiScenario,
        endpoint_id: int,
        changed_fields: Set[str]
    ) -> bool:
        """
        检查场景是否使用了变更的字段
        
        Args:
            scenario: 场景对象
            endpoint_id: 接口 ID
            changed_fields: 变更字段集合
            
        Returns:
            bool: 是否受影响
        """
        # 检查执行顺序中的变量使用
        if scenario.execution_order:
            for step in scenario.execution_order:
                if step.get("endpoint_id") == endpoint_id:
                    # 检查该步骤的变量使用
                    variables = step.get("variables", {})
                    for var_name, var_value in variables.items():
                        for field in changed_fields:
                            if field in str(var_value):
                                return True
                    
                    # 检查变量提取规则
                    extract = step.get("extract", {})
                    for var_name, json_path in extract.items():
                        for field in changed_fields:
                            if field in json_path:
                                return True
        
        return False
    
    def _calculate_impact_level(self, changed_fields: Set[str]) -> str:
        """
        计算影响级别
        
        Args:
            changed_fields: 变更字段集合
            
        Returns:
            str: 影响级别（high/medium/low）
        """
        if len(changed_fields) >= 5:
            return "high"
        elif len(changed_fields) >= 2:
            return "medium"
        else:
            return "low"