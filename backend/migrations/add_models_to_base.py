"""
向 base.py 添加新的链路模型
"""

import re

def add_models_to_base():
    """向 base.py 添加新的链路模型"""
    base_file_path = r'D:\code\BugSeek\backend\app\db\base.py'
    
    with open(base_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已添加
    if 'class ApiInternalChain' in content:
        print("模型已存在，跳过添加")
        return
    
    # 新模型代码
    new_models = '''
# ==================== 链路管理相关模型 ====================

class ApiInternalChain(Base, TimestampMixin):
    """内部链路表"""
    __tablename__ = "api_internal_chains"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("api_endpoint_groups.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # 基本信息
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # 链路数据
    endpoint_ids = Column(JSON, nullable=False, default=list)
    execution_order = Column(JSON, nullable=False, default=list)
    
    # 链路元数据
    chain_type = Column(String(50), default="business")
    complexity_score = Column(Integer, default=1)
    estimated_duration = Column(Integer, nullable=True)
    
    # 生成标记
    auto_generated = Column(Boolean, default=True)
    analysis_version = Column(String(50), nullable=True)
    
    # 状态
    status = Column(String(20), default="active")
    
    # 统计信息
    endpoint_count = Column(Integer, default=0)
    dependency_count = Column(Integer, default=0)
    
    # 关联
    related_scenario_id = Column(Integer, ForeignKey("api_scenarios.id", ondelete="SET NULL"), nullable=True)
    
    # 关系定义
    group = relationship("ApiEndpointGroup", backref="internal_chains_list")
    project = relationship("Project", backref="internal_chains")
    related_scenario = relationship("ApiScenario", foreign_keys=[related_scenario_id])
    
    __table_args__ = (
        UniqueConstraint('group_id', 'name', name='uq_internal_chain'),
        Index('ix_api_internal_chains_group_id', 'group_id'),
        Index('ix_api_internal_chains_project_id', 'project_id'),
        Index('ix_api_internal_chains_status', 'status'),
        Index('ix_api_internal_chains_auto_generated', 'auto_generated'),
    )


class ApiChainScenario(Base, TimestampMixin):
    """链路与场景关联表"""
    __tablename__ = "api_chain_scenarios"

    id = Column(Integer, primary_key=True, index=True)
    chain_id = Column(Integer, nullable=False)
    chain_type = Column(String(20), nullable=False)  # internal | cross-module
    scenario_id = Column(Integer, ForeignKey("api_scenarios.id", ondelete="CASCADE"), nullable=False)
    
    # 关联信息
    is_primary = Column(Boolean, default=True)
    mapping_config = Column(JSON, nullable=True)
    
    # 关系定义
    scenario = relationship("ApiScenario", backref="chain_associations")
    
    __table_args__ = (
        UniqueConstraint('chain_id', 'chain_type', 'scenario_id', name='uq_chain_scenario'),
        Index('ix_api_chain_scenarios_chain_id', 'chain_id', 'chain_type'),
        Index('ix_api_chain_scenarios_scenario_id', 'scenario_id'),
    )
'''
    
    # 在文件末尾添加新模型
    with open(base_file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        f.write(new_models)
    
    print("链路模型添加成功")

if __name__ == "__main__":
    add_models_to_base()