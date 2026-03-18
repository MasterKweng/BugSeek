import React, { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Input,
  List,
  Progress,
  Result,
  Segmented,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CheckOutlined,
  CloseOutlined,
  ExperimentOutlined,
  ReloadOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import WorkspaceModuleHero from '../components/WorkspaceModuleHero'
import { useProjectStore } from '../store/project'
import { getDbSchemas } from '../services/dbSchema'
import {
  autoApplyFieldMappings,
  batchApplyFieldMappings,
  batchRejectSuggestions,
  createFieldMappingSuggestTask,
  deleteFieldMapping,
  getAsyncTask,
  getFieldMappingSuggestions,
  getFieldMappings,
  getLearningStats,
  listAsyncTasks,
  type AsyncTask,
  type FieldMappingSuggestion,
  type FieldMappingWithDetails,
} from '../services/fieldMapping'

const { Paragraph, Text, Title } = Typography

type SuggestionStatusFilter = 'all' | 'pending' | 'confirmed' | 'rejected'
type MethodFilter = 'all' | 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
type FieldTypeFilter = 'all' | 'path' | 'query' | 'body'
type MappingFilter = 'all' | 'confirmed' | 'rejected' | 'proposed'
type ViewMode = 'suggestions' | 'mappings'

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN')
}

const getMethodColor = (method?: string) => {
  const normalized = (method || '').toUpperCase()
  if (normalized === 'GET') return 'blue'
  if (normalized === 'POST') return 'green'
  if (normalized === 'PUT') return 'gold'
  if (normalized === 'DELETE') return 'red'
  if (normalized === 'PATCH') return 'purple'
  return 'default'
}

const getStatusColor = (status?: string) => {
  if (status === 'confirmed') return 'success'
  if (status === 'rejected') return 'error'
  if (status === 'failed') return 'error'
  if (status === 'partial_success') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'running') return 'processing'
  return 'default'
}

const FieldMappingSuggestions: React.FC = () => {
  const { currentProject, currentVersion } = useProjectStore()
  const [viewMode, setViewMode] = useState<ViewMode>('suggestions')
  const [loading, setLoading] = useState(false)
  const [mappingsLoading, setMappingsLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [selectedSuggestion, setSelectedSuggestion] = useState<FieldMappingSuggestion | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [task, setTask] = useState<AsyncTask | null>(null)
  const [taskId, setTaskId] = useState<number | null>(null)
  const [schemaCount, setSchemaCount] = useState(0)
  const [suggestions, setSuggestions] = useState<FieldMappingSuggestion[]>([])
  const [mappings, setMappings] = useState<FieldMappingWithDetails[]>([])
  const [stats, setStats] = useState<{
    total_mappings: number
    confirmed_mappings: number
    proposed_mappings: number
    rejected_mappings: number
    avg_confidence: number
    ai_mappings: number
    manual_mappings: number
  } | null>(null)

  const [includePaths, setIncludePaths] = useState(true)
  const [includeQuery, setIncludeQuery] = useState(true)
  const [includeBody, setIncludeBody] = useState(true)
  const [useAi, setUseAi] = useState(true)
  const [highPriorityEnabled, setHighPriorityEnabled] = useState(true)
  const [mediumPriorityEnabled, setMediumPriorityEnabled] = useState(true)
  const [lowPriorityEnabled, setLowPriorityEnabled] = useState(false)

  const [searchKeyword, setSearchKeyword] = useState('')
  const [pathFilter, setPathFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<SuggestionStatusFilter>('all')
  const [methodFilter, setMethodFilter] = useState<MethodFilter>('all')
  const [fieldTypeFilter, setFieldTypeFilter] = useState<FieldTypeFilter>('all')
  const [mappingFilter, setMappingFilter] = useState<MappingFilter>('all')

  const contextParams = useMemo(() => ({
    project_id: currentProject?.id,
    version_id: currentVersion?.id,
  }), [currentProject?.id, currentVersion?.id])

  const selectedSuggestions = useMemo(
    () => suggestions.filter((item) => item.id && selectedRowKeys.includes(item.id)),
    [selectedRowKeys, suggestions],
  )

  const suggestionMetrics = useMemo(() => {
    const highConfidence = suggestions.filter((item) => (item.candidates?.[0]?.score || 0) >= 0.85).length

    return [
      { label: '建议数', value: suggestions.length },
      { label: '高置信', value: highConfidence },
      { label: '任务状态', value: task?.status || '-' },
    ]
  }, [suggestions, task?.status])

  const mappingMetrics = useMemo(() => [
    { label: '已生效', value: stats?.confirmed_mappings ?? mappings.filter((item) => item.status === 'confirmed').length },
    { label: '待处理', value: stats?.proposed_mappings ?? mappings.filter((item) => item.status === 'proposed').length },
    { label: 'AI 来源', value: stats?.ai_mappings ?? mappings.filter((item) => item.source === 'ai').length },
  ], [mappings, stats])

  const filteredMappings = useMemo(() => {
    if (mappingFilter === 'all') {
      return mappings
    }

    return mappings.filter((item) => item.status === mappingFilter)
  }, [mappingFilter, mappings])

  const loadStats = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      setStats(null)
      return
    }

    try {
      const response = await getLearningStats(contextParams)
      setStats(response.data || null)
    } catch {
      setStats(null)
    }
  }

  const loadMappings = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      setMappings([])
      return
    }

    setMappingsLoading(true)
    try {
      const response = await getFieldMappings(contextParams)
      setMappings(response.data?.items || [])
    } catch (error: any) {
      message.error(error.message || '获取字段映射失败')
    } finally {
      setMappingsLoading(false)
    }
  }

  const loadSchemaCount = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      setSchemaCount(0)
      return
    }

    try {
      const response = await getDbSchemas(contextParams)
      setSchemaCount(response.data?.items?.length || 0)
    } catch {
      setSchemaCount(0)
    }
  }

  const loadSuggestions = async (nextTaskId: number) => {
    setLoading(true)
    try {
      const response = await getFieldMappingSuggestions(nextTaskId, {
        search: searchKeyword || undefined,
        status_filter: statusFilter !== 'all' ? statusFilter : undefined,
        method_filter: methodFilter !== 'all' ? methodFilter : undefined,
        field_type_filter: fieldTypeFilter !== 'all' ? fieldTypeFilter : undefined,
        definition_path_filter: pathFilter || undefined,
        page: 1,
        size: 200,
      })
      setSuggestions(response.data?.items || [])
    } catch (error: any) {
      message.error(error.message || '获取建议结果失败')
    } finally {
      setLoading(false)
    }
  }

  const loadTask = async (nextTaskId: number) => {
    try {
      const response = await getAsyncTask(nextTaskId)
      const nextTask = response.data || null
      setTask(nextTask)

      if (nextTask?.status === 'completed' || nextTask?.status === 'partial_success') {
        await loadSuggestions(nextTaskId)
      }
    } catch (error: any) {
      message.error(error.message || '获取任务状态失败')
    }
  }

  const loadLatestTask = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      setTask(null)
      setTaskId(null)
      setSuggestions([])
      return
    }

    try {
      const response = await listAsyncTasks({
        project_id: currentProject.id,
        version_id: currentVersion.id,
        task_type: 'field_mapping_suggest',
        limit: 1,
        offset: 0,
      })
      const latestTask = response.data?.items?.[0]

      if (!latestTask?.id) {
        setTask(null)
        setTaskId(null)
        setSuggestions([])
        return
      }

      setTaskId(latestTask.id)
      await loadTask(latestTask.id)
    } catch {
      setTask(null)
      setTaskId(null)
      setSuggestions([])
    }
  }

  useEffect(() => {
    void loadSchemaCount()
    void loadMappings()
    void loadStats()
    void loadLatestTask()
  }, [currentProject?.id, currentVersion?.id])

  useEffect(() => {
    if (!taskId || !task || (task.status !== 'pending' && task.status !== 'running')) {
      return
    }

    const timer = window.setInterval(() => {
      void loadTask(taskId)
    }, 3000)

    return () => window.clearInterval(timer)
  }, [task, taskId])

  useEffect(() => {
    if (taskId && task && (task.status === 'completed' || task.status === 'partial_success')) {
      void loadSuggestions(taskId)
    }
  }, [fieldTypeFilter, methodFilter, pathFilter, searchKeyword, statusFilter, task?.status, taskId])

  const handleCreateTask = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本')
      return
    }

    if (schemaCount === 0) {
      message.warning('当前版本还没有数据库结构，无法生成字段映射建议')
      return
    }

    setLoading(true)
    try {
      const response = await createFieldMappingSuggestTask(
        {
          include_paths: includePaths,
          include_query: includeQuery,
          include_body: includeBody,
          use_ai: useAi,
          high_priority_enabled: highPriorityEnabled,
          medium_priority_enabled: mediumPriorityEnabled,
          low_priority_enabled: lowPriorityEnabled,
        },
        contextParams,
      )

      const nextTaskId = response.data?.task_id
      if (!nextTaskId) {
        throw new Error(response.message || '任务创建失败')
      }

      setTaskId(nextTaskId)
      setSelectedRowKeys([])
      setSuggestions([])
      message.success('字段映射任务已创建')
      await loadTask(nextTaskId)
    } catch (error: any) {
      message.error(error.message || '创建字段映射任务失败')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmSuggestions = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      return
    }

    const items = selectedSuggestions
      .filter((item) => item.id && item.candidates?.length)
      .map((item) => {
        const candidate = item.candidates[0]
        return {
          suggestion_id: item.id!,
          definition_id: item.definition_id,
          api_field_path: item.api_field_path,
          db_table: candidate.db_table,
          db_column: candidate.db_column,
          relation_type: 'write',
          source: candidate.ai_selected ? 'ai' : 'manual',
        }
      })

    if (items.length === 0) {
      message.warning('所选建议没有可应用的候选字段')
      return
    }

    setLoading(true)
    try {
      await batchApplyFieldMappings({ items, mode: 'confirm' }, contextParams)
      message.success('已应用所选建议')
      setSelectedRowKeys([])
      if (taskId) {
        await loadSuggestions(taskId)
      }
      await loadMappings()
      await loadStats()
    } catch (error: any) {
      message.error(error.message || '应用建议失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRejectSuggestions = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      return
    }

    const suggestionIds = selectedSuggestions
      .map((item) => item.id)
      .filter((id): id is number => typeof id === 'number')

    if (suggestionIds.length === 0) {
      message.warning('所选建议没有可拒绝的记录')
      return
    }

    setLoading(true)
    try {
      await batchRejectSuggestions({ suggestion_ids: suggestionIds }, contextParams)
      message.success('所选建议已拒绝')
      setSelectedRowKeys([])
      if (taskId) {
        await loadSuggestions(taskId)
      }
      await loadStats()
    } catch (error: any) {
      message.error(error.message || '拒绝建议失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAutoApply = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      return
    }

    setMappingsLoading(true)
    try {
      const response = await autoApplyFieldMappings({ min_confidence: 0.85 }, contextParams)
      message.success(`已自动应用 ${response.data?.updated_count ?? 0} 条高置信映射`)
      await loadMappings()
      await loadStats()
    } catch (error: any) {
      message.error(error.message || '自动应用失败')
    } finally {
      setMappingsLoading(false)
    }
  }

  const handleDeleteMapping = async (mappingId: number) => {
    if (!currentProject?.id || !currentVersion?.id) {
      return
    }

    setMappingsLoading(true)
    try {
      await deleteFieldMapping(mappingId, contextParams)
      message.success('映射已删除')
      await loadMappings()
      await loadStats()
    } catch (error: any) {
      message.error(error.message || '删除映射失败')
    } finally {
      setMappingsLoading(false)
    }
  }

  const suggestionColumns: ColumnsType<FieldMappingSuggestion> = [
    {
      title: 'API',
      key: 'api',
      width: 280,
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Space wrap>
            <Tag color={getMethodColor(record.definition_method)}>{record.definition_method}</Tag>
            <Text strong>{record.definition_path}</Text>
          </Space>
          <Text type="secondary">{record.api_field_path}</Text>
        </Space>
      ),
    },
    {
      title: '推荐字段',
      key: 'candidate',
      render: (_, record) => {
        const candidate = record.candidates?.[0]
        if (!candidate) {
          return <Text type="secondary">无候选字段</Text>
        }

        return (
          <Space direction="vertical" size={2}>
            <Text strong>{candidate.db_table}.{candidate.db_column}</Text>
            <Text type="secondary">{candidate.reasons?.join(' / ') || '无额外说明'}</Text>
          </Space>
        )
      },
    },
    {
      title: '置信度',
      key: 'confidence',
      width: 180,
      render: (_, record) => {
        const score = record.candidates?.[0]?.score || 0
        return <Progress percent={Number((score * 100).toFixed(1))} size="small" />
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string | undefined) => <Tag color={getStatusColor(value || 'pending')}>{value || 'pending'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 110,
      render: (_, record) => (
        <Button
          type="link"
          onClick={() => {
            setSelectedSuggestion(record)
            setDetailOpen(true)
          }}
        >
          查看
        </Button>
      ),
    },
  ]

  const mappingColumns: ColumnsType<FieldMappingWithDetails> = [
    {
      title: 'API',
      key: 'api',
      width: 280,
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Space wrap>
            <Tag color={getMethodColor(record.definition_method)}>{record.definition_method || '-'}</Tag>
            <Text strong>{record.definition_path || '-'}</Text>
          </Space>
          <Text type="secondary">{record.api_field_path}</Text>
        </Space>
      ),
    },
    {
      title: '已生效映射',
      key: 'mapping',
      render: (_, record) => <Text strong>{record.db_table}.{record.db_column}</Text>,
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 160,
      render: (value: number | null | undefined) => (
        <Progress percent={Number(((value || 0) * 100).toFixed(1))} size="small" />
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (value: string | null | undefined) => <Tag color={value === 'ai' ? 'green' : 'blue'}>{value || 'manual'}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string | undefined) => <Tag color={getStatusColor(value || 'confirmed')}>{value || 'confirmed'}</Tag>,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Button danger type="link" onClick={() => void handleDeleteMapping(record.id)}>
          删除
        </Button>
      ),
    },
  ]

  if (!currentProject || !currentVersion) {
    return (
      <Result
        status="warning"
        title="请先选择项目和版本"
        subTitle="字段映射治理依赖项目和版本上下文。"
      />
    )
  }

  return (
    <div className="governance-stack">
      <WorkspaceModuleHero
        eyebrow="Governance"
        title="字段映射治理"
        description={`管理 ${currentProject.name} / ${currentVersion.version_number} 的字段映射建议和已生效映射，只使用真实的异步建议任务、批量应用和批量拒绝能力。`}
        metrics={viewMode === 'suggestions' ? suggestionMetrics : mappingMetrics}
        actions={
          <Space wrap>
            <Segmented
              value={viewMode}
              onChange={(value) => setViewMode(value as ViewMode)}
              options={[
                { label: '建议工作台', value: 'suggestions' },
                { label: '已生效映射', value: 'mappings' },
              ]}
            />
            <Button onClick={() => {
              void loadMappings()
              void loadStats()
              void loadLatestTask()
            }}>
              刷新
            </Button>
          </Space>
        }
      />

      {viewMode === 'suggestions' ? (
        <>
          <Card className="workspace-table-card" bordered={false}>
            <div className="governance-filter-grid">
              <div className="governance-note-card">
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <div>
                    <Title level={5} style={{ marginBottom: 4 }}>生成配置</Title>
                    <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      当前版本已导入 {schemaCount} 份数据库结构。任务会调用后端异步建议流程并写入可审阅的建议记录。
                    </Paragraph>
                  </div>
                  <div className="governance-switch-list">
                    <span><Text>Path 参数</Text><Switch checked={includePaths} onChange={setIncludePaths} /></span>
                    <span><Text>Query 参数</Text><Switch checked={includeQuery} onChange={setIncludeQuery} /></span>
                    <span><Text>Body 参数</Text><Switch checked={includeBody} onChange={setIncludeBody} /></span>
                    <span><Text>启用 AI</Text><Switch checked={useAi} onChange={setUseAi} /></span>
                    <span><Text>高优先级</Text><Switch checked={highPriorityEnabled} onChange={setHighPriorityEnabled} disabled={!useAi} /></span>
                    <span><Text>中优先级</Text><Switch checked={mediumPriorityEnabled} onChange={setMediumPriorityEnabled} disabled={!useAi} /></span>
                    <span><Text>低优先级</Text><Switch checked={lowPriorityEnabled} onChange={setLowPriorityEnabled} disabled={!useAi} /></span>
                  </div>
                  <Button type="primary" icon={<RocketOutlined />} loading={loading && (!task || task.status !== 'completed')} onClick={() => void handleCreateTask()}>
                    生成新任务
                  </Button>
                </Space>
              </div>

              <div className="governance-note-card">
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <div>
                    <Title level={5} style={{ marginBottom: 4 }}>当前任务</Title>
                    <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      这里只展示当前项目版本下最近一次字段映射任务的真实状态与结果。
                    </Paragraph>
                  </div>
                  {task ? (
                    <>
                      <Descriptions size="small" column={1}>
                        <Descriptions.Item label="任务 ID">#{task.id}</Descriptions.Item>
                        <Descriptions.Item label="状态">
                          <Tag color={getStatusColor(task.status)}>{task.status}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="进度">{task.progress}%</Descriptions.Item>
                        <Descriptions.Item label="创建时间">{formatDateTime(task.created_at)}</Descriptions.Item>
                      </Descriptions>
                      <Progress
                        percent={task.progress}
                        status={task.status === 'failed' ? 'exception' : task.status === 'completed' ? 'success' : 'active'}
                      />
                      {task.progress_message ? <Text type="secondary">{task.progress_message}</Text> : null}
                      {task.error_message ? <Alert type="error" showIcon message={task.error_message} /> : null}
                    </>
                  ) : (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有字段映射任务" />
                  )}
                </Space>
              </div>
            </div>
          </Card>

          <Card className="workspace-table-card" bordered={false}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div className="governance-toolbar">
                <Input.Search
                  allowClear
                  placeholder="搜索 API 字段、表名或列名"
                  onSearch={(value) => setSearchKeyword(value.trim())}
                  style={{ maxWidth: 280 }}
                />
                <Input
                  allowClear
                  placeholder="按 API 路径过滤"
                  onChange={(event) => setPathFilter(event.target.value.trim())}
                  style={{ maxWidth: 260 }}
                />
                <Select value={statusFilter} onChange={(value) => setStatusFilter(value as SuggestionStatusFilter)} style={{ width: 140 }}>
                  <Select.Option value="all">全部状态</Select.Option>
                  <Select.Option value="pending">Pending</Select.Option>
                  <Select.Option value="confirmed">Confirmed</Select.Option>
                  <Select.Option value="rejected">Rejected</Select.Option>
                </Select>
                <Select value={methodFilter} onChange={(value) => setMethodFilter(value as MethodFilter)} style={{ width: 120 }}>
                  <Select.Option value="all">全部方法</Select.Option>
                  <Select.Option value="GET">GET</Select.Option>
                  <Select.Option value="POST">POST</Select.Option>
                  <Select.Option value="PUT">PUT</Select.Option>
                  <Select.Option value="DELETE">DELETE</Select.Option>
                  <Select.Option value="PATCH">PATCH</Select.Option>
                </Select>
                <Select value={fieldTypeFilter} onChange={(value) => setFieldTypeFilter(value as FieldTypeFilter)} style={{ width: 120 }}>
                  <Select.Option value="all">全部位置</Select.Option>
                  <Select.Option value="path">path</Select.Option>
                  <Select.Option value="query">query</Select.Option>
                  <Select.Option value="body">body</Select.Option>
                </Select>
              </div>

              <Space wrap>
                <Button
                  type="primary"
                  icon={<CheckOutlined />}
                  disabled={selectedSuggestions.length === 0}
                  onClick={() => void handleConfirmSuggestions()}
                >
                  批量确认
                </Button>
                <Button
                  danger
                  icon={<CloseOutlined />}
                  disabled={selectedSuggestions.length === 0}
                  onClick={() => void handleRejectSuggestions()}
                >
                  批量拒绝
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  disabled={!taskId}
                  onClick={() => taskId && void loadSuggestions(taskId)}
                >
                  刷新结果
                </Button>
              </Space>

              <Spin spinning={loading}>
                <Table
                  rowKey={(record) => record.id || `${record.definition_id}-${record.api_field_path}`}
                  rowSelection={{
                    selectedRowKeys,
                    onChange: setSelectedRowKeys,
                    getCheckboxProps: (record) => ({
                      disabled: !record.id || !record.candidates?.length || record.status === 'confirmed',
                    }),
                  }}
                  columns={suggestionColumns}
                  dataSource={suggestions}
                  scroll={{ y: 'calc(100vh - 520px)' }}
                  pagination={{ pageSize: 10, hideOnSinglePage: true }}
                  locale={{ emptyText: <Empty description="当前任务还没有可审阅的建议结果" /> }}
                />
              </Spin>
            </Space>
          </Card>
        </>
      ) : (
        <>
          <Card className="workspace-table-card" bordered={false}>
            <div className="governance-filter-grid">
              <div className="governance-note-card">
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Title level={5} style={{ marginBottom: 0 }}>映射质量概览</Title>
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="总映射">{stats?.total_mappings ?? mappings.length}</Descriptions.Item>
                    <Descriptions.Item label="已确认">{stats?.confirmed_mappings ?? 0}</Descriptions.Item>
                    <Descriptions.Item label="AI 来源">{stats?.ai_mappings ?? 0}</Descriptions.Item>
                    <Descriptions.Item label="平均置信度">
                      {stats?.avg_confidence ? `${(stats.avg_confidence * 100).toFixed(1)}%` : '-'}
                    </Descriptions.Item>
                  </Descriptions>
                </Space>
              </div>

              <div className="governance-note-card">
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <div>
                    <Title level={5} style={{ marginBottom: 4 }}>自动应用</Title>
                    <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      使用后端现有的高置信自动应用能力，将高于或等于 0.85 的建议映射直接落库。
                    </Paragraph>
                  </div>
                  <Button icon={<ExperimentOutlined />} onClick={() => void handleAutoApply()} loading={mappingsLoading}>
                    自动应用高置信映射
                  </Button>
                </Space>
              </div>
            </div>
          </Card>

          <Card className="workspace-table-card" bordered={false}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div className="governance-toolbar">
                <Segmented
                  value={mappingFilter}
                  onChange={(value) => setMappingFilter(value as MappingFilter)}
                  options={[
                    { label: '全部', value: 'all' },
                    { label: 'Confirmed', value: 'confirmed' },
                    { label: 'Rejected', value: 'rejected' },
                    { label: 'Proposed', value: 'proposed' },
                  ]}
                />
              </div>

              <Table
                rowKey="id"
                loading={mappingsLoading}
                columns={mappingColumns}
                dataSource={filteredMappings}
                scroll={{ y: 'calc(100vh - 520px)' }}
                pagination={{ pageSize: 10, hideOnSinglePage: true }}
                locale={{ emptyText: <Empty description="当前版本还没有字段映射" /> }}
              />
            </Space>
          </Card>
        </>
      )}

      <Drawer
        title="建议详情"
        open={detailOpen}
        width={760}
        onClose={() => setDetailOpen(false)}
      >
        {selectedSuggestion ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="API">
                <Space wrap>
                  <Tag color={getMethodColor(selectedSuggestion.definition_method)}>
                    {selectedSuggestion.definition_method}
                  </Tag>
                  <Text strong>{selectedSuggestion.definition_path}</Text>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="字段路径">{selectedSuggestion.api_field_path}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={getStatusColor(selectedSuggestion.status || 'pending')}>
                  {selectedSuggestion.status || 'pending'}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            <Card className="governance-note-card" bordered={false}>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Title level={5} style={{ marginBottom: 0 }}>候选字段</Title>
                {selectedSuggestion.candidates?.length ? (
                  <List
                    dataSource={selectedSuggestion.candidates}
                    renderItem={(candidate) => (
                      <List.Item>
                        <Space direction="vertical" size={2}>
                          <Space wrap>
                            <Text strong>{candidate.db_table}.{candidate.db_column}</Text>
                            <Tag color={candidate.ai_selected ? 'green' : 'blue'}>
                              {candidate.ai_selected ? 'AI selected' : 'Rule selected'}
                            </Tag>
                          </Space>
                          <Text type="secondary">score: {(candidate.score * 100).toFixed(1)}%</Text>
                          <Text type="secondary">{candidate.reasons?.join(' / ') || '无额外说明'}</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有候选字段" />
                )}
              </Space>
            </Card>

            {selectedSuggestion.decision_trace ? (
              <Card className="governance-note-card" bordered={false}>
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  <Text type="secondary">决策轨迹</Text>
                  <pre className="governance-json-block">
                    {JSON.stringify(selectedSuggestion.decision_trace, null, 2)}
                  </pre>
                </Space>
              </Card>
            ) : null}
          </Space>
        ) : null}
      </Drawer>
    </div>
  )
}

export default FieldMappingSuggestions
