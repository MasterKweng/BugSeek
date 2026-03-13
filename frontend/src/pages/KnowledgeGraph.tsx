import React, { useState } from 'react'
import { Card, Col, Input, Row, Button, Table, Typography, message, Space } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { getNode, getTablesByApi, getApisByTable, GraphNode } from '../services/knowledgeGraph'

const { Text } = Typography

const columns: ColumnsType<GraphNode> = [
  { title: 'Name', dataIndex: 'name', key: 'name', width: 200 },
  { title: 'Display Name', dataIndex: 'display_name', key: 'display_name', width: 220 },
  { title: 'Type', dataIndex: 'node_type', key: 'node_type', width: 120 },
  { title: 'Source Id', dataIndex: 'source_id', key: 'source_id' },
]

const KnowledgeGraph: React.FC = () => {
  const [nodeId, setNodeId] = useState('')
  const [apiNodeId, setApiNodeId] = useState('')
  const [tableNodeId, setTableNodeId] = useState('')
  const [node, setNode] = useState<GraphNode | null>(null)
  const [tables, setTables] = useState<GraphNode[]>([])
  const [apis, setApis] = useState<GraphNode[]>([])
  const [loadingNode, setLoadingNode] = useState(false)
  const [loadingTables, setLoadingTables] = useState(false)
  const [loadingApis, setLoadingApis] = useState(false)

  const handleLoadNode = async () => {
    if (!nodeId.trim()) {
      message.warning('Please input node id')
      return
    }
    setLoadingNode(true)
    try {
      const data = await getNode(nodeId.trim())
      setNode(data)
    } catch (err: any) {
      message.error(err?.message || 'Failed to load node')
    } finally {
      setLoadingNode(false)
    }
  }

  const handleLoadTables = async () => {
    if (!apiNodeId.trim()) {
      message.warning('Please input API node id')
      return
    }
    setLoadingTables(true)
    try {
      const data = await getTablesByApi(apiNodeId.trim())
      setTables(data.items || [])
    } catch (err: any) {
      message.error(err?.message || 'Failed to load tables')
    } finally {
      setLoadingTables(false)
    }
  }

  const handleLoadApis = async () => {
    if (!tableNodeId.trim()) {
      message.warning('Please input table node id')
      return
    }
    setLoadingApis(true)
    try {
      const data = await getApisByTable(tableNodeId.trim())
      setApis(data.items || [])
    } catch (err: any) {
      message.error(err?.message || 'Failed to load APIs')
    } finally {
      setLoadingApis(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card title="Knowledge Graph">
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                value={nodeId}
                onChange={(e) => setNodeId(e.target.value)}
                placeholder="Node id"
              />
              <Button type="primary" loading={loadingNode} onClick={handleLoadNode}>
                Load Node
              </Button>
            </Space.Compact>
          </Col>
          <Col span={24}>
            {node ? (
              <div>
                <Text strong>Node</Text>
                <pre style={{ marginTop: 8, background: '#0f172a', color: '#e2e8f0', padding: 12, borderRadius: 6 }}>
                  {JSON.stringify(node, null, 2)}
                </pre>
              </div>
            ) : (
              <Text type="secondary">No node loaded</Text>
            )}
          </Col>
        </Row>
      </Card>

      <Card title="API to Tables">
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                value={apiNodeId}
                onChange={(e) => setApiNodeId(e.target.value)}
                placeholder="API node id"
              />
              <Button type="primary" loading={loadingTables} onClick={handleLoadTables}>
                Fetch Tables
              </Button>
            </Space.Compact>
          </Col>
          <Col span={24}>
            <Table
              rowKey="id"
              columns={columns}
              dataSource={tables}
              loading={loadingTables}
              pagination={{ pageSize: 8 }}
              size="small"
            />
          </Col>
        </Row>
      </Card>

      <Card title="Table to APIs">
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                value={tableNodeId}
                onChange={(e) => setTableNodeId(e.target.value)}
                placeholder="Table node id"
              />
              <Button type="primary" loading={loadingApis} onClick={handleLoadApis}>
                Fetch APIs
              </Button>
            </Space.Compact>
          </Col>
          <Col span={24}>
            <Table
              rowKey="id"
              columns={columns}
              dataSource={apis}
              loading={loadingApis}
              pagination={{ pageSize: 8 }}
              size="small"
            />
          </Col>
        </Row>
      </Card>
    </div>
  )
}

export default KnowledgeGraph
