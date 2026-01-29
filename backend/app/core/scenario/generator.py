"""场景生成器"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import logging

from app.db.base import ApiEndpoint, ApiScenario, ScenarioEndpoint
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class ScenarioGenerator:
    """场景生成器"""

    def __init__(self, db: Session):
        """
        初始化场景生成器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()

    def generate_from_chain(
        self,
        project_id: int,
        chain: List[int],
        chain_name: str,
        description: str = None
    ) -> ApiScenario:
        """
        从业务链路生成场景
        
        流程：
        1. 查询接口信息
        2. 构建执行顺序
        3. 创建场景
        
        Args:
            project_id: 项目ID
            chain: 业务链路（endpoint_id列表）
            chain_name: 场景名称
            description: 场景描述
            
        Returns:
            生成的场景
        """
        logger.info(f"[{self.trace_id}] 从链路生成场景: chain={chain}, name={chain_name}")
        
        # 1. 查询接口信息
        endpoints = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.id.in_(chain)
        ).all()

        endpoint_map = {ep.id: ep for ep in endpoints}
        
        if len(endpoint_map) != len(chain):
            logger.warning(f"[{self.trace_id}] 部分接口不存在: found={len(endpoint_map)}, expected={len(chain)}")
        
        # 2. 构建执行顺序
        execution_order = []

        for step, endpoint_id in enumerate(chain, 1):
            endpoint = endpoint_map.get(endpoint_id)
            if not endpoint:
                continue

            step_config = {
                "step": step,
                "endpoint_id": endpoint_id,
                "name": f"{endpoint.method} {endpoint.path}",
                "description": endpoint.summary or "",
                "variables": {},
                "extract": self._extract_output_fields(endpoint.response_schema),
                "depends_on": [chain[step - 2]] if step > 1 else []
            }

            execution_order.append(step_config)

        # 3. 创建场景
        scenario = ApiScenario(
            project_id=project_id,
            name=chain_name,
            description=description or f"自动生成的业务链路测试场景",
            scenario_type="business_flow",
            category=self._infer_category(chain),
            endpoint_ids=chain,
            execution_order=execution_order,
            endpoint_count=len(chain),
            status="active"
        )

        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)

        # 4. 创建场景-接口关联
        for step, endpoint_id in enumerate(chain, 1):
            scenario_endpoint = ScenarioEndpoint(
                scenario_id=scenario.id,
                endpoint_id=endpoint_id,
                step_order=step
            )
            self.db.add(scenario_endpoint)

        self.db.commit()

        logger.info(f"[{self.trace_id}] 场景生成成功: scenario_id={scenario.id}")

        return scenario

    def _extract_output_fields(self, schema: Dict) -> Dict[str, str]:
        """
        提取接口的输出字段（用于变量传递）
        
        Args:
            schema: JSON Schema对象
            
        Returns:
            {"字段名": "JSON路径"}
        """
        if not schema:
            return {}

        fields = {}

        def traverse(obj, prefix=''):
            if isinstance(obj, dict):
                if 'properties' in obj:
                    for key, value in obj['properties'].items():
                        fields[key] = prefix + key
                        traverse(value, prefix + key + '.')
            elif isinstance(obj, list) and obj:
                traverse(obj[0], prefix)

        traverse(schema)
        return fields

    def _infer_category(self, chain: List[int]) -> str:
        """
        推断场景分类
        
        Args:
            chain: 业务链路（endpoint_id列表）
            
        Returns:
            场景分类
        """
        # 根据接口路径推断业务分类
        endpoints = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.id.in_(chain)
        ).all()

        paths = [ep.path for ep in endpoints]

        # 简单的关键词匹配
        if any('order' in path.lower() for path in paths):
            return "订单流程"
        elif any('user' in path.lower() for path in paths):
            return "用户流程"
        elif any('payment' in path.lower() or 'pay' in path.lower() for path in paths):
            return "支付流程"
        elif any('product' in path.lower() or 'item' in path.lower() for path in paths):
            return "商品流程"
        elif any('cart' in path.lower() for path in paths):
            return "购物车流程"
        else:
            return "业务流程"