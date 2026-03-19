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
import { useAppPreferences } from '../preferences/AppPreferencesProvider'
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

const KnowledgeGraph: React.FC = () => {
  const { t } = useAppPreferences()
  const { currentProject, currentVersion } = useProjectStore()
  const tm = (key: string, fallback: string, variables?: Record<string, string | number>) =>
    t(`knowledgeGraphPage.${key}`, fallback, variables)

  const filterOptions: Array<{ label: string; value: NodeFilter }> = [
    { label: tm('filters.api', 'APIs'), value: 'API' },
    { label: tm('filters.table', 'Tables'), value: 'TABLE' },
    { label: tm('filters.field', 'Fields'), value: 'FIELD' },
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
      message.error(error?.message || tm('messages.loadNodesFailed', 'Failed to load graph nodes'))
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
      message.error(error?.message || tm('messages.loadDetailsFailed', 'Failed to load graph details'))
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
      return tm('lane.selectNodeTitle', 'Select a node to inspect its graph context')
    }
    if (selectedNode.node_type === 'API') {
      return tm('lane.apiTitle', 'API -> TABLE + FIELD context')
    }
    if (selectedNode.node_type === 'TABLE') {
      return tm('lane.tableTitle', 'TABLE <- API + FIELD context')
    }
    return tm('lane.fieldTitle', 'FIELD <- API / TABLE context')
  }, [selectedNode])

  const laneDescription = useMemo(() => {
    if (!selectedNode) {
      return tm('lane.selectNodeDescription', 'Browse APIs, tables, and fields without entering UUIDs.')
    }
    if (selectedNode.node_type === 'API') {
      return tm('lane.apiDescription', 'This API currently connects to {primary} tables and {secondary} field nodes.', {
        primary: relations.primary.length,
        secondary: relations.secondary.length,
      })
    }
    if (selectedNode.node_type === 'TABLE') {
      return tm('lane.tableDescription', 'This table is currently referenced by {primary} APIs and exposes {secondary} field nodes.', {
        primary: relations.primary.length,
        secondary: relations.secondary.length,
      })
    }
    return tm('lane.fieldDescription', 'This field is attached to {primary} APIs and {secondary} tables.', {
      primary: relations.primary.length,
      secondary: relations.secondary.length,
    })
  }, [relations.primary.length, relations.secondary.length, selectedNode])

  const propertyEntries = useMemo(() => Object.entries(selectedDetail?.properties || {}), [selectedDetail])

  const primaryLabel = selectedNode?.node_type === 'API'
    ? tm('lane.primary.api', 'Written Tables')
    : selectedNode?.node_type === 'TABLE'
      ? tm('lane.primary.table', 'Upstream APIs')
      : tm('lane.primary.field', 'Related APIs')

  const secondaryLabel = selectedNode?.node_type === 'API'
    ? tm('lane.secondary.api', 'API Fields')
    : selectedNode?.node_type === 'TABLE'
      ? tm('lane.secondary.table', 'Table Fields')
      : tm('lane.secondary.field', 'Related Tables')

  const heroMetrics = useMemo(() => [
    { label: tm('metrics.nodeCount', 'Node count'), value: nodes.length },
    { label: tm('metrics.currentFilter', 'Current filter'), value: nodeType },
    { label: tm('metrics.currentFocus', 'Current focus'), value: selectedNode?.display_name || selectedNode?.name || '-' },
  ], [nodeType, nodes.length, selectedNode?.display_name, selectedNode?.name])

  if (!currentProject || !currentVersion) {
    return (
      <Result
        status="warning"
        title={tm('messages.selectProjectAndVersionTitle', 'Please select a project and version first')}
        subTitle={tm('messages.selectProjectAndVersionSubtitle', 'Knowledge graph browsing depends on the current project and version context.')}
      />
    )
  }

  return (
    <div className="governance-stack kg-page">
      <WorkspaceModuleHero
        eyebrow={tm('hero.eyebrow', 'Governance')}
        title={tm('hero.title', 'Knowledge Graph')}
        description={tm('hero.description', 'Browse the real relationships between API, table, and field nodes under {project} / {version} for dependency analysis, write-path tracing, and field context review.', {
          project: currentProject.name,
          version: currentVersion.version_number,
        })}
        metrics={heroMetrics}
        actions={
          <Space wrap>
            <Tag color="blue">{nodeType}</Tag>
            <Button icon={<ReloadOutlined />} onClick={() => void loadNodes(nodeType, searchKeyword)}>
              {tm('actions.refresh', 'Refresh')}
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
            placeholder={tm('placeholders.search', 'Search by name, display name, or source id')}
            allowClear
          />
          <Button type="primary" onClick={() => setSearchKeyword(searchInput.trim())}>
            {tm('actions.search', 'Search')}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => void loadNodes(nodeType, searchKeyword)}>
            {tm('actions.refresh', 'Refresh')}
          </Button>
        </div>
      </Card>

      <div className="kg-layout">
        <Card
          className="workspace-table-card kg-panel"
          bordered={false}
          title={`${nodeType} ${tm('cards.catalog', 'Catalog')}`}
          extra={<Text type="secondary">{tm('cards.itemsCount', '{count} items', { count: nodes.length })}</Text>}
        >
          <Spin spinning={loadingNodes}>
            <List
              className="kg-list"
              locale={{ emptyText: <Empty description={tm('empty.noGraphNodesFound', 'No graph nodes found')} /> }}
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
            <Empty description={tm('empty.selectNodeToInspectGraph', 'Select a node to inspect the graph')} />
          ) : (
            <Spin spinning={loadingRelations}>
              <div className="kg-lane kg-lane-grid">
                <div className="kg-lane-section">
                  <Text className="kg-lane-label">{tm('lane.selected', 'Selected')}</Text>
                  <div className="kg-focus-card">
                    <Tag color={typeColorMap[selectedNode.node_type] || 'default'}>{selectedNode.node_type}</Tag>
                    <Title level={4}>{selectedNode.display_name || selectedNode.name}</Title>
                    <Paragraph>{selectedNode.source_id || tm('lane.noSourceId', 'No source id')}</Paragraph>
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
                  )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={tm('empty.noItems', 'No {label}', { label: primaryLabel.toLowerCase() })} />}
                </div>

                <div className="kg-lane-section">
                  <Text className="kg-lane-label">{secondaryLabel}</Text>
                  {relations.secondary.length > 0 ? relations.secondary.map((item) => (
                    <button key={item.id} className="kg-mini-card" onClick={() => setSelectedNode(item)}>
                      <Tag color={typeColorMap[item.node_type] || 'default'}>{item.node_type}</Tag>
                      <strong>{item.display_name || item.name}</strong>
                      <span>{item.properties?.field_path || item.properties?.table || item.source_id || '-'}</span>
                    </button>
                  )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={tm('empty.noItems', 'No {label}', { label: secondaryLabel.toLowerCase() })} />}
                </div>
              </div>
            </Spin>
          )}
        </Card>

        <Card className="workspace-table-card kg-panel" bordered={false} title={tm('cards.nodeDetail', 'Node Detail')}>
          {!selectedNode ? (
            <Empty description={tm('empty.selectNodeToInspectMetadata', 'Select a node to inspect metadata')} />
          ) : (
            <Spin spinning={loadingDetail}>
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Descriptions column={1} size="small" labelStyle={{ width: 110 }}>
                  <Descriptions.Item label={tm('detail.type', 'Type')}>
                    <Tag color={typeColorMap[selectedNode.node_type] || 'default'}>{selectedNode.node_type}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label={tm('detail.name', 'Name')}>{selectedDetail?.name || '-'}</Descriptions.Item>
                  <Descriptions.Item label={tm('detail.display', 'Display')}>{selectedDetail?.display_name || '-'}</Descriptions.Item>
                  <Descriptions.Item label={tm('detail.sourceId', 'Source ID')}>{selectedDetail?.source_id || '-'}</Descriptions.Item>
                </Descriptions>

                <div>
                  <Text strong>{tm('detail.properties', 'Properties')}</Text>
                  {propertyEntries.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={tm('empty.noProperties', 'No properties')} />
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
