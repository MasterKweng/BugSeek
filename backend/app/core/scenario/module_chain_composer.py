"""跨模块链路组合器"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import logging

from app.db.base import (
    ApiEndpoint, ApiEndpointGroup, ApiModuleDependency, ApiModuleChain, ApiScenario
)
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class ModuleChainComposer:
    """跨模块链路组合器"""

    def __init__(self, db: Session):
        """
        初始化跨模块链路组合器

        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()

    def compose_cross_module_scenarios(
        self,
        project_id: int,
        module_chain: List[int],
        chain_name: str,
        description: Optional[str] = None
    ) -> List[ApiScenario]:
        """
        组合跨模块的业务场景

        流程：
        1. 获取模块链路中每个模块的内部链路
        2. 识别模块间的数据传递规则
        3. 组合完整的执行顺序
        4. 生成场景配置

        示例：
        模块链：[用户模块, 订单模块, 支付模块]

        组合结果：
        [
          {step: 1, endpoint: 用户模块.创建用户, extract: {user_id: data.id}},
          {step: 2, endpoint: 用户模块.获取用户信息, depends_on: [1]},
          {step: 3, endpoint: 订单模块.创建订单,
           variables: {user_id: "{{step1.user_id}}"}, depends_on: [1, 2]},
          {step: 4, endpoint: 订单模块.查询订单, depends_on: [3]},
          {step: 5, endpoint: 支付模块.创建支付,
           variables: {order_id: "{{step3.order_id}}"}, depends_on: [3, 4]}
        ]

        Args:
            project_id: 项目ID
            module_chain: 模块链路（group_id列表）
            chain_name: 链路名称
            description: 链路描述

        Returns:
            生成的场景列表
        """
        logger.info(
            f"[{self.trace_id}] 开始组合跨模块场景: "
            f"project_id={project_id}, chain={module_chain}, name={chain_name}"
        )

        # 1. 获取所有模块信息
        groups = self.db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.id.in_(module_chain)
        ).all()

        group_map = {g.id: g for g in groups}

        # 2. 获取每个模块的内部链路
        module_chains_data = {}
        for group_id in module_chain:
            group = group_map.get(group_id)
            if group:
                # 从 ApiInternalChain 表查询内部链路
                internal_chains = self.db.query(ApiInternalChain).filter(
                    ApiInternalChain.group_id == group_id
                ).all()

                # 选择最长的链路作为主链路
                if internal_chains:
                    main_chain = max(internal_chains, key=lambda c: len(c.endpoint_ids or []))
                    module_chains_data[group_id] = {
                        "group": group,
                        "internal_chain": main_chain.endpoint_ids or [],
                        "internal_chain_id": main_chain.id
                    }

        # 3. 构建完整的执行顺序
        execution_order = self._build_execution_order(
            project_id=project_id,
            module_chain=module_chain,
            module_chains_data=module_chains_data,
            group_map=group_map
        )

        # 4. 收集所有涉及的接口
        all_endpoint_ids = []
        for step in execution_order:
            endpoint_id = step.get("endpoint_id")
            if endpoint_id:
                all_endpoint_ids.append(endpoint_id)

        # 5. 创建场景
        scenario = ApiScenario(
            project_id=project_id,
            name=chain_name,
            description=description or f"跨模块业务场景：{chain_name}",
            scenario_type="business_flow",
            category=self._infer_category(module_chain, group_map),
            endpoint_ids=all_endpoint_ids,
            execution_order=execution_order,
            endpoint_count=len(all_endpoint_ids),
            status="active",
            source_type="cross_module"  # 标记来源为跨模块组合
        )

        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)

        logger.info(
            f"[{self.trace_id}] 跨模块场景生成成功: "
            f"scenario_id={scenario.id}, endpoint_count={len(all_endpoint_ids)}"
        )

        return [scenario]

    def _build_execution_order(
        self,
        project_id: int,
        module_chain: List[int],
        module_chains_data: Dict[int, Dict],
        group_map: Dict[int, ApiEndpointGroup]
    ) -> List[Dict]:
        """
        构建完整的执行顺序

        Args:
            project_id: 项目ID
            module_chain: 模块链路
            module_chains_data: 模块链路数据
            group_map: 模块映射

        Returns:
            执行顺序列表
        """
        execution_order = []
        step_counter = 0

        # 记录每个步骤输出的变量
        step_outputs = {}

        for module_index, group_id in enumerate(module_chain):
            group = group_map.get(group_id)
            if not group:
                continue

            module_data = module_chains_data.get(group_id)
            if not module_data:
                logger.warning(f"[{self.trace_id}] 模块 {group_id} 没有内部链路，跳过")
                continue

            internal_chain = module_data.get("internal_chain", [])

            # 获取该模块的接口信息
            endpoints = self.db.query(ApiEndpoint).filter(
                ApiEndpoint.id.in_(internal_chain),
                ApiEndpoint.group_id == group_id
            ).all()

            endpoint_map = {ep.id: ep for ep in endpoints}

            # 执行模块内的每个接口
            for ep_id in internal_chain:
                endpoint = endpoint_map.get(ep_id)
                if not endpoint:
                    continue

                step_counter += 1

                step_config = {
                    "step": step_counter,
                    "module_id": group_id,
                    "module_name": group.name,
                    "endpoint_id": ep_id,
                    "name": f"{endpoint.method} {endpoint.path}",
                    "description": endpoint.summary or "",
                    "variables": {},
                    "extract": {},
                    "depends_on": []
                }

                # 处理变量传递
                if step_counter > 1:
                    # 查找该接口需要的输入字段
                    input_fields = self._extract_fields_from_schema(endpoint.request_schema)

                    # 从前面的步骤中查找匹配的字段
                    variables = {}
                    for field in input_fields:
                        # 简单的字段名匹配（实际应该使用更复杂的映射规则）
                        for prev_step, outputs in step_outputs.items():
                            if field in outputs:
                                variables[field] = f"{{{{step{prev_step}.{field}}}}}"
                                break

                    step_config["variables"] = variables

                # 提取输出字段
                output_fields = self._extract_fields_from_schema(endpoint.response_schema)
                if output_fields:
                    step_config["extract"] = {
                        field: f"data.{field}" for field in output_fields
                    }
                    step_outputs[step_counter] = output_fields

                # 添加依赖关系（依赖前一个步骤）
                if step_counter > 1:
                    step_config["depends_on"] = [step_counter - 1]

                execution_order.append(step_config)

            logger.info(
                f"[{self.trace_id}] 模块 {group.name} 执行顺序构建完成: "
                f"{len(internal_chain)} 个步骤"
            )

        return execution_order

    def _extract_fields_from_schema(self, schema: Optional[Dict]) -> List[str]:
        """
        从schema中提取字段名

        Args:
            schema: JSON Schema对象

        Returns:
            字段名列表
        """
        if not schema:
            return []

        fields = []

        def traverse(obj, prefix=''):
            if isinstance(obj, dict):
                if 'properties' in obj:
                    for key, value in obj['properties'].items():
                        fields.append(prefix + key)
                        traverse(value, prefix + key + '.')
            elif isinstance(obj, list) and obj:
                traverse(obj[0], prefix)

        traverse(schema)
        return fields

    def _infer_category(
        self,
        module_chain: List[int],
        group_map: Dict[int, ApiEndpointGroup]
    ) -> str:
        """
        推断场景分类

        Args:
            module_chain: 模块链路
            group_map: 模块映射

        Returns:
            场景分类
        """
        # 根据模块名称推断业务分类
        group_names = [group_map.get(gid, {}).name for gid in module_chain if gid in group_map]

        # 简单的关键词匹配
        if any('order' in name.lower() for name in group_names):
            return "订单流程"
        elif any('user' in name.lower() for name in group_names):
            return "用户流程"
        elif any('payment' in name.lower() for name in group_names):
            return "支付流程"
        elif any('product' in name.lower() or 'goods' in name.lower() for name in group_names):
            return "商品流程"
        else:
            return "业务流程"

    def save_module_chain(
        self,
        project_id: int,
        module_chain: List[int],
        chain_name: str,
        description: Optional[str] = None
    ) -> ApiModuleChain:
        """
        保存模块链路

        Args:
            project_id: 项目ID
            module_chain: 模块链路（group_id列表）
            chain_name: 链路名称
            description: 链路描述

        Returns:
            模块链路对象
        """
        logger.info(
            f"[{self.trace_id}] 保存模块链路: "
            f"project_id={project_id}, chain={module_chain}, name={chain_name}"
        )

        # 获取模块信息
        groups = self.db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.id.in_(module_chain)
        ).all()

        group_map = {g.id: g for g in groups}

        # 构建链路结构
        chain_structure = []
        for step, group_id in enumerate(module_chain, 1):
            group = group_map.get(group_id)
            if group:
                # 从 ApiInternalChain 表查询内部链路
                internal_chains = self.db.query(ApiInternalChain).filter(
                    ApiInternalChain.group_id == group_id
                ).all()
                
                chain_structure.append({
                    "step": step,
                    "group_id": group_id,
                    "group_name": group.name,
                    "internal_chain": [c.endpoint_ids for c in internal_chains],
                    "next_group_id": module_chain[step] if step < len(module_chain) else None
                })

        # 统计接口数量
        all_endpoint_ids = []
        for group_id in module_chain:
            # 从 ApiInternalChain 表查询
            internal_chains = self.db.query(ApiInternalChain).filter(
                ApiInternalChain.group_id == group_id
            ).all()
            
            for chain in internal_chains:
                all_endpoint_ids.extend(chain.endpoint_ids or [])

        # 创建模块链路
        module_chain_obj = ApiModuleChain(
            project_id=project_id,
            name=chain_name,
            description=description,
            group_ids=module_chain,
            chain_structure=chain_structure,
            endpoint_count=len(set(all_endpoint_ids)),
            group_count=len(module_chain),
            status="active"
        )

        self.db.add(module_chain_obj)
        # 5. 创建场景（如果需要）
        scenario = None
        if True:  # 默认为每个模块链路生成场景
            from app.core.scenario.generator import ScenarioGenerator
            
            generator = ScenarioGenerator(self.db)
            
            # 选择每个模块的最长内部链路
            selected_chain = []
            for group_id in module_chain:
                internal_chains = self.db.query(ApiInternalChain).filter(
                    ApiInternalChain.group_id == group_id
                ).all()
                
                if internal_chains:
                    # 选择最长的链路
                    longest_chain = max(internal_chains, key=lambda c: len(c.endpoint_ids))
                    selected_chain.extend(longest_chain.endpoint_ids)
            
            if selected_chain:
                scenario = generator.generate_from_chain(
                    project_id=project_id,
                    chain=selected_chain,
                    chain_name=f"{chain_name}_场景",
                    description=f"由模块链路 {chain_name} 自动生成的场景"
                )
                
                # 更新场景的来源信息
                scenario.source_type = "module_chain"
                scenario.source_module_chain_id = module_chain_obj.id
                self.db.commit()
        
        self.db.commit()
        self.db.refresh(module_chain_obj)

        logger.info(
            f"[{self.trace_id}] 模块链路保存成功: "
            f"chain_id={module_chain_obj.id}, scenario_id={scenario.id if scenario else None}"
        )

        return module_chain_obj

    def list_module_chains(
        self,
        project_id: int
    ) -> List[Dict[str, any]]:
        """
        获取跨模块业务链路列表

        Args:
            project_id: 项目ID

        Returns:
            [
                {
                    "id": 1,
                    "name": "用户下单支付流程",
                    "group_ids": [1, 3, 5],
                    "group_names": ["用户模块", "订单模块", "支付模块"],
                    "endpoint_count": 8
                }
            ]
        """
        chains = self.db.query(ApiModuleChain).filter(
            ApiModuleChain.project_id == project_id,
            ApiModuleChain.status == "active"
        ).order_by(ApiModuleChain.created_at.desc()).all()

        result = []

        for chain in chains:
            # 获取模块名称
            groups = self.db.query(ApiEndpointGroup).filter(
                ApiEndpointGroup.id.in_(chain.group_ids)
            ).all()

            group_names = [g.name for g in groups]

            result.append({
                "id": chain.id,
                "name": chain.name,
                "description": chain.description,
                "group_ids": chain.group_ids,
                "group_names": group_names,
                "endpoint_count": chain.endpoint_count,
                "group_count": chain.group_count,
                "created_at": chain.created_at.isoformat(),
                "updated_at": chain.updated_at.isoformat()
            })

        return result

    def get_module_chain(
        self,
        chain_id: int
    ) -> Optional[Dict[str, any]]:
        """
        获取模块链路详情

        Args:
            chain_id: 链路ID

        Returns:
            链路详情
        """
        chain = self.db.query(ApiModuleChain).filter(
            ApiModuleChain.id == chain_id
        ).first()

        if not chain:
            return None

        # 获取模块信息
        groups = self.db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.id.in_(chain.group_ids)
        ).all()

        group_map = {g.id: g for g in groups}

        return {
            "id": chain.id,
            "project_id": chain.project_id,
            "name": chain.name,
            "description": chain.description,
            "group_ids": chain.group_ids,
            "chain_structure": chain.chain_structure,
            "endpoint_count": chain.endpoint_count,
            "group_count": chain.group_count,
            "status": chain.status,
            "created_at": chain.created_at.isoformat(),
            "updated_at": chain.updated_at.isoformat()
        }