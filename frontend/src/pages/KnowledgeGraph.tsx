import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Input,
  List,
  Result,
  Segmented,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  ApiOutlined,
  DatabaseOutlined,
  NodeIndexOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import WorkspaceModuleHero from '../components/WorkspaceModuleHero'
import { useProjectStore } from '../store/project'
import {
  GraphNode,
  getApisByField,
  getApisByTable,
  getFieldsByApi,
  getFieldsByTable,
  getNode,
  getNodes,
  getTablesByApi,
  getTablesByField,
} from '../services/knowledgeGraph'
import './KnowledgeGraph.css'

const { Paragraph, Text, Title } = Typography

type NodeFilter = 'API' | 'TABLE' | 'FIELD'

type RelationBuckets = {
  primary: GraphNode[]
  secondary: GraphNode[]
}

const filterOptions: Array<{ label: string; value: NodeFilter }> = [
  { label: 'APIs', value: 'API' },
  { label: 'Tables', value: 'TABLE' },
  { label: 'Fields', value: 'FIELD' },
]

const typeColorMap: Record<string, string> = {
  API: 'blue',
  TABLE: 'green',
  FIELD: 'gold',
}

const typeIconMap: Record<string, React.ReactNode> = {
  API: <ApiOutlined />,
  TABLE: <DatabaseOutlined />,
  FIELD: <NodeIndexOutlined />,
}

const KnowledgeGraph: React.FC = () => {
  const { currentProject, currentVersion } = useProjectStore()
  const [nodeType, setNodeType] = useState<NodeFilter>('API')
  const [searchInput, setSearchInput] = useState('')
  const [searchKeyword, setSearchKeyword] = useState('')
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<GraphNode | null>(null)
  const [relations, setRelations] = useState<RelationBuckets>({ primary: [], secondary: [] })
  const [loadingNodes, setLoadingNodes] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [loadingRelations, setLoadingRelations] = useState(false)

  const loadNodes = useCallback(async (nextType: NodeFilter = nodeType, nextSearch: string = searchKeyword) => {
    setLoadingNodes(true)
    try {
      const data = await getNodes({
        node_type: nextType,
        search: nextSearch || undefined,
        limit: 120,
      })
      const items = data.items || []
      setNodes(items)

      if (items.length === 0) {
        setSelectedNode(null)
        setSelectedDetail(null)
        setRelations({ primary: [], secondary: [] })
        return
      }

      setSelectedNode((prev) => {
        const matched = prev ? items.find((item) => item.id === prev.id) : null
        return matched || items[0]
      })
    } catch (error: any) {
      message.error(error?.message || 'Failed to load graph nodes')
    } finally {
      setLoadingNodes(false)
    }
  }, [nodeType, searchKeyword])

  const loadNodeContext = useCallback(async (node: GraphNode | null) => {
    if (!node) {
      setSelectedDetail(null)
      setRelations({ primary: [], secondary: [] })
      return
    }

    setLoadingDetail(true)
    setLoadingRelations(true)
    try {
      const detailPromise = getNode(node.id)
      let relationPromise: Promise<RelationBuckets>

      if (node.node_type === 'API') {
        relationPromise = Promise.all([getTablesByApi(node.id), getFieldsByApi(node.id)]).then(([primary, secondary]) => ({
          primary: primary.items || [],
          secondary: secondary.items || [],
        }))
      } else if (node.node_type === 'TABLE') {
        relationPromise = Promise.all([getApisByTable(node.id), getFieldsByTable(node.id)]).then(([primary, secondary]) => ({
          primary: primary.items || [],
          secondary: secondary.items || [],
        }))
      } else {
        relationPromise = Promise.all([getApisByField(node.id), getTablesByField(node.id)]).then(([primary, secondary]) => ({
          primary: primary.items || [],
          secondary: secondary.items || [],
        }))
      }

      const [detail, relationData] = await Promise.all([detailPromise, relationPromise])
      setSelectedDetail(detail)
      setRelations(relationData)
    } catch (error: any) {
      message.error(error?.message || 'Failed to load graph details')
    } finally {
      setLoadingDetail(false)
      setLoadingRelations(false)
    }
  }, [])

  useEffect(() => {
    void loadNodes(nodeType, searchKeyword)
  }, [loadNodes, nodeType, searchKeyword])

  useEffect(() => {
    void loadNodeContext(selectedNode)
  }, [loadNodeContext, selectedNode])

  const laneTitle = useMemo(() => {
    if (!selectedNode) {
      return 'Select a node to inspect its graph context'
    }
    if (selectedNode.node_type === 'API') {
      return 'API -> TABLE + FIELD context'
    }
    if (selectedNode.node_type === 'TABLE') {
      return 'TABLE <- API + FIELD context'
    }
    return 'FIELD <- API / TABLE context'
  }, [selectedNode])

  const laneDescription = useMemo(() => {
    if (!selectedNode) {
      return 'Browse APIs, tables, and fields without entering UUIDs.'
    }
    if (selectedNode.node_type === 'API') {
      return `This API currently connects to ${relations.primary.length} tables and ${relations.secondary.length} field nodes.`
    }
    if (selectedNode.node_type === 'TABLE') {
      return `This table is currently referenced by ${relations.primary.length} APIs and exposes ${relations.secondary.length} field nodes.`
    }
    return `This field is attached to ${relations.primary.length} APIs and ${relations.secondary.length} tables.`
  }, [relations.primary.length, relations.secondary.length, selectedNode])

  const propertyEntries = useMemo(() => Object.entries(selectedDetail?.properties || {}), [selectedDetail])

  const primaryLabel = selectedNode?.node_type === 'API'
    ? 'Written Tables'
    : selectedNode?.node_type === 'TABLE'
      ? 'Upstream APIs'
      : 'Related APIs'

  const secondaryLabel = selectedNode?.node_type === 'API'
    ? 'API Fields'
    : selectedNode?.node_type === 'TABLE'
      ? 'Table Fields'
      : 'Related Tables'

  const heroMetrics = useMemo(() => [
    { label: '节点总数', value: nodes.length },
    { label: '当前筛选', value: nodeType },
    { label: '当前焦点', value: selectedNode?.display_name || selectedNode?.name || '-' },
  ], [nodeType, nodes.length, selectedNode?.display_name, selectedNode?.name])

  if (!currentProject || !currentVersion) {
    return (
      <Result
        status="warning"
        title="请先选择项目和版本"
        subTitle="知识图谱浏览依赖项目和版本上下文。"
      />
    )
  }

  return (
    <div className="governance-stack kg-page">
      <WorkspaceModuleHero
        eyebrow="Governance"
        title="知识图谱"
        description={`浏览 ${currentProject.name} / ${currentVersion.version_number} 下 API、表和字段节点的真实关联关系，用于排查依赖、回溯写路径和审阅字段上下文。`}
        metrics={heroMetrics}
        actions={
          <Space wrap>
            <Tag color="blue">{nodeType}</Tag>
            <Button icon={<ReloadOutlined />} onClick={() => void loadNodes(nodeType, searchKeyword)}>
              Refresh
            </Button>
          </Space>
        }
      />

      <Card className="workspace-table-card" bordered={false}>
        <div className="kg-toolbar">
          <Segmented
            options={filterOptions}
            value={nodeType}
            onChange={(value) => setNodeType(value as NodeFilter)}
          />
          <Input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            onPressEnter={() => setSearchKeyword(searchInput.trim())}
            prefix={<SearchOutlined />}
            placeholder="Search by name, display name, or source id"
            allowClear
          />
          <Button type="primary" onClick={() => setSearchKeyword(searchInput.trim())}>
            Search
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => void loadNodes(nodeType, searchKeyword)}>
            Refresh
          </Button>
        </div>
      </Card>

      <div className="kg-layout">
        <Card
          className="workspace-table-card kg-panel"
          bordered={false}
          title={`${nodeType} Catalog`}
          extra={<Text type="secondary">{nodes.length} items</Text>}
        >
          <Spin spinning={loadingNodes}>
            <List
              className="kg-list"
              locale={{ emptyText: <Empty description="No graph nodes found" /> }}
              dataSource={nodes}
              renderItem={(item) => {
                const active = selectedNode?.id === item.id
                return (
                  <List.Item className={`kg-list-item ${active ? 'is-active' : ''}`} onClick={() => setSelectedNode(item)}>
                    <div className="kg-list-item-main">
                      <div className="kg-list-item-title">
                        <span className="kg-list-item-icon">{typeIconMap[item.node_type] || <NodeIndexOutlined />}</span>
                        <span>{item.display_name || item.name}</span>
                      </div>
                      <Text type="secondary">{item.name}</Text>
                    </div>
                    <Tag color={typeColorMap[item.node_type] || 'default'}>{item.node_type}</Tag>
                  </List.Item>
                )
              }}
            />
          </Spin>
        </Card>

        <Card
          className="workspace-table-card kg-panel kg-lane-card"
          bordered={false}
          title={laneTitle}
          extra={<Text type="secondary">{laneDescription}</Text>}
        >
          {!selectedNode ? (
            <Empty description="Select a node to inspect the graph" />
          ) : (
            <Spin spinning={loadingRelations}>
              <div className="kg-lane kg-lane-grid">
                <div className="kg-lane-section">
                  <Text className="kg-lane-label">Selected</Text>
                  <div className="kg-focus-card">
                    <Tag color={typeColorMap[selectedNode.node_type] || 'default'}>{selectedNode.node_type}</Tag>
                    <Title level={4}>{selectedNode.display_name || selectedNode.name}</Title>
                    <Paragraph>{selectedNode.source_id || 'No source id'}</Paragraph>
                  </div>
                </div>

                <div className="kg-lane-section">
                  <Text className="kg-lane-label">{primaryLabel}</Text>
                  {relations.primary.length > 0 ? relations.primary.map((item) => (
                    <button key={item.id} className="kg-mini-card" onClick={() => setSelectedNode(item)}>
                      <Tag color={typeColorMap[item.node_type] || 'default'}>{item.node_type}</Tag>
                      <strong>{item.display_name || item.name}</strong>
                      <span>{item.properties?.method ? `${item.properties.method} ${item.properties.path || ''}` : item.source_id || '-'}</span>
                    </button>
                  )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`No ${primaryLabel.toLowerCase()}`} />}
                </div>

                <div className="kg-lane-section">
                  <Text className="kg-lane-label">{secondaryLabel}</Text>
                  {relations.secondary.length > 0 ? relations.secondary.map((item) => (
                    <button key={item.id} className="kg-mini-card" onClick={() => setSelectedNode(item)}>
                      <Tag color={typeColorMap[item.node_type] || 'default'}>{item.node_type}</Tag>
                      <strong>{item.display_name || item.name}</strong>
                      <span>{item.properties?.field_path || item.properties?.table || item.source_id || '-'}</span>
                    </button>
                  )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`No ${secondaryLabel.toLowerCase()}`} />}
                </div>
              </div>
            </Spin>
          )}
        </Card>

        <Card className="workspace-table-card kg-panel" bordered={false} title="Node Detail">
          {!selectedNode ? (
            <Empty description="Select a node to inspect metadata" />
          ) : (
            <Spin spinning={loadingDetail}>
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Descriptions column={1} size="small" labelStyle={{ width: 110 }}>
                  <Descriptions.Item label="Type">
                    <Tag color={typeColorMap[selectedNode.node_type] || 'default'}>{selectedNode.node_type}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Name">{selectedDetail?.name || '-'}</Descriptions.Item>
                  <Descriptions.Item label="Display">{selectedDetail?.display_name || '-'}</Descriptions.Item>
                  <Descriptions.Item label="Source ID">{selectedDetail?.source_id || '-'}</Descriptions.Item>
                </Descriptions>

                <div>
                  <Text strong>Properties</Text>
                  {propertyEntries.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No properties" />
                  ) : (
                    <List
                      size="small"
                      dataSource={propertyEntries}
                      renderItem={([key, value]) => (
                        <List.Item>
                          <div style={{ width: '100%' }}>
                            <Text strong>{key}</Text>
                            <Paragraph className="kg-property-value" copyable={{ text: JSON.stringify(value) }}>
                              {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                            </Paragraph>
                          </div>
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              </Space>
            </Spin>
          )}
        </Card>
      </div>
    </div>
  )
}

export default KnowledgeGraph
