import React from 'react'
import { Alert, Drawer, Space, Table } from 'antd'

import type { ScenarioRevisionGraph } from '../../types/scenario'

interface ScenarioGraphDrawerProps {
  open: boolean
  graph: ScenarioRevisionGraph | null
  onClose: () => void
}

const ScenarioGraphDrawer: React.FC<ScenarioGraphDrawerProps> = ({ open, graph, onClose }) => (
  <Drawer title="场景依赖图" open={open} onClose={onClose} width={680}>
    {graph ? (
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Table
          rowKey="node_key"
          dataSource={graph.nodes}
          pagination={false}
          columns={[
            { title: '节点标识', dataIndex: 'node_key', key: 'node_key' },
            { title: '节点名称', dataIndex: 'node_name', key: 'node_name' },
            { title: '节点类型', dataIndex: 'node_type', key: 'node_type' },
          ]}
        />
        <Table
          rowKey={(item) => `${item.source_node_key}-${item.target_node_key}-${item.edge_type}`}
          dataSource={graph.edges}
          pagination={false}
          columns={[
            { title: '起点节点', dataIndex: 'source_node_key', key: 'source_node_key' },
            { title: '终点节点', dataIndex: 'target_node_key', key: 'target_node_key' },
            { title: '边类型', dataIndex: 'edge_type', key: 'edge_type' },
          ]}
        />
      </Space>
    ) : (
      <Alert type="info" showIcon message="当前没有可展示的依赖图，请先加载某个版本快照。" />
    )}
  </Drawer>
)

export default ScenarioGraphDrawer
