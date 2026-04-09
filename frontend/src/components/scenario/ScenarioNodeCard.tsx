import React from 'react'
import { Button, Card, Space, Tag, Typography } from 'antd'
import { DeleteOutlined, EditOutlined } from '@ant-design/icons'

import type { ScenarioNode } from '../../types/scenario'

interface ScenarioNodeCardProps {
  node: ScenarioNode
  referenceLabel: string
  onEdit: (node: ScenarioNode) => void
  onDelete: (nodeKey: string) => void
}

const nodeTypeLabelMap: Record<string, string> = {
  api_call: 'API 调用',
  condition: '条件判断',
  wait: '等待/轮询',
  script: '脚本处理',
}

const ScenarioNodeCard: React.FC<ScenarioNodeCardProps> = ({ node, referenceLabel, onEdit, onDelete }) => (
  <Card size="small" className="node-card">
    <div className="node-header">
      <Space wrap>
        <Tag color="blue">#{node.step_order}</Tag>
        <strong>{node.node_name || node.node_key}</strong>
        <Tag>{node.node_key}</Tag>
        <Tag>{nodeTypeLabelMap[node.node_type] || node.node_type}</Tag>
        <Tag color={node.is_enabled ? 'success' : 'default'}>{node.is_enabled ? '已启用' : '已停用'}</Tag>
      </Space>
      <Space>
        <Button type="link" size="small" icon={<EditOutlined />} onClick={() => onEdit(node)}>编辑</Button>
        <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => onDelete(node.node_key)}>删除</Button>
      </Space>
    </div>
    <div className="node-details">
      <div>引用：{referenceLabel}</div>
      {node.depends_on.length > 0 ? <div>依赖：{node.depends_on.join(', ')}</div> : null}
      {node.extra_config && Object.keys(node.extra_config).length > 0 ? (
        <div>
          配置：<Typography.Text type="secondary">{JSON.stringify(node.extra_config)}</Typography.Text>
        </div>
      ) : null}
    </div>
  </Card>
)

export default ScenarioNodeCard
