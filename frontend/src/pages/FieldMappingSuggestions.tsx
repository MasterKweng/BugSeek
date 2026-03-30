import React, { useEffect, useMemo, useState } from 'react'
import {
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
  QuestionCircleOutlined,
  ReloadOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import FieldMappingTaskObservability from '../components/FieldMappingTaskObservability'
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
  type FieldMappingSuggestionResponse,
  type FieldMappingWithDetails,
} from '../services/fieldMapping'

const { Paragraph, Text, Title } = Typography

type SuggestionStatusFilter = 'all' | 'pending' | 'confirmed' | 'rejected'
type MethodFilter = 'all' | 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
type FieldTypeFilter = 'all' | 'path' | 'query' | 'body'
type MappingFilter = 'all' | 'confirmed' | 'rejected' | 'proposed'
type DecisionSourceFilter = 'all' | 'rule' | 'ai' | 'fallback'
type RelationTypeFilter = 'all' | 'direct' | 'fk' | 'derived'
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

const getDecisionSourceColor = (value?: string | null) => {
  if (value === 'ai') return 'magenta'
  if (value === 'fallback') return 'orange'
  if (value === 'rule') return 'blue'
  return 'default'
}

const getRelationTypeColor = (value?: string | null) => {
  if (value === 'direct') return 'green'
  if (value === 'fk') return 'gold'
  if (value === 'derived') return 'purple'
  return 'default'
}

const formatPercent = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '-'
  }
  return `${(value * 100).toFixed(1)}%`
}

const renderTraceValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toString() : '-'
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

const renderKeyValueTags = (record: Record<string, unknown>) => {
  const entries = Object.entries(record || {})
  if (entries.length === 0) {
    return <Text type="secondary">-</Text>
  }

  return (
    <Space wrap>
      {entries.map(([key, value]) => (
        <Tag key={key}>{`${key}:${renderTraceValue(value)}`}</Tag>
      ))}
    </Space>
  )
}

const FieldMappingSuggestions: React.FC = () => {
  const defaultSuggestionPageSize = 20
  const suggestionPageSizeOptions = ['20', '50', '100']
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
  const [suggestionPage, setSuggestionPage] = useState(1)
  const [suggestionPageSize, setSuggestionPageSize] = useState(defaultSuggestionPageSize)
  const [suggestionTotal, setSuggestionTotal] = useState(0)
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
  const [useSqlLineage, setUseSqlLineage] = useState(true)
  const [useCodeLineage, setUseCodeLineage] = useState(true)
  const [useRuntimeVerification, setUseRuntimeVerification] = useState(true)
  const [evidenceMode, setEvidenceMode] = useState<'balanced' | 'conservative' | 'aggressive'>('balanced')
  const [rebuildLineageBeforeRun, setRebuildLineageBeforeRun] = useState(false)
  const [highPriorityEnabled, setHighPriorityEnabled] = useState(true)
  const [mediumPriorityEnabled, setMediumPriorityEnabled] = useState(true)
  const [lowPriorityEnabled, setLowPriorityEnabled] = useState(false)

  const [searchKeyword, setSearchKeyword] = useState('')
  const [pathFilter, setPathFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<SuggestionStatusFilter>('all')
  const [methodFilter, setMethodFilter] = useState<MethodFilter>('all')
  const [fieldTypeFilter, setFieldTypeFilter] = useState<FieldTypeFilter>('all')
  const [mappingFilter, setMappingFilter] = useState<MappingFilter>('all')
  const [decisionSourceFilter, setDecisionSourceFilter] = useState<DecisionSourceFilter>('all')
  const [relationTypeFilter, setRelationTypeFilter] = useState<RelationTypeFilter>('all')

  const contextParams = useMemo(() => ({
    project_id: currentProject?.id,
    version_id: currentVersion?.id,
  }), [currentProject?.id, currentVersion?.id])

  const selectedSuggestions = useMemo(
    () => suggestions.filter((item) => item.id && selectedRowKeys.includes(item.id)),
    [selectedRowKeys, suggestions],
  )

  const visibleSuggestions = useMemo(
    () => suggestions.filter((item) => {
      const source = item.decision_source || item.decision_artifact?.decision_source || 'rule'
      const relationType = item.relation_type || item.decision_artifact?.relation_type || 'direct'
      if (decisionSourceFilter !== 'all' && source !== decisionSourceFilter) {
        return false
      }
      if (relationTypeFilter !== 'all' && relationType !== relationTypeFilter) {
        return false
      }
      return true
    }),
    [decisionSourceFilter, relationTypeFilter, suggestions],
  )


  const suggestionMetrics = useMemo(() => {
    const highConfidence = suggestions.filter((item) => (
      (item.confidence ?? item.candidates?.[0]?.confidence ?? item.candidates?.[0]?.score) || 0
    ) >= 0.85).length

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
        page: suggestionPage,
        size: suggestionPageSize,
      })
      const data: FieldMappingSuggestionResponse | undefined = response.data
      setSuggestions(data?.items || [])
      setSelectedRowKeys([])
      setSuggestionTotal(data?.total || 0)
      setSuggestionPage(data?.page || suggestionPage)
      setSuggestionPageSize(data?.size || suggestionPageSize)
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
        setSuggestionTotal(0)
        setSuggestionPage(1)
        setSuggestionPageSize(defaultSuggestionPageSize)
        return
      }

      setTaskId(latestTask.id)
      await loadTask(latestTask.id)
    } catch {
      setTask(null)
      setTaskId(null)
      setSuggestions([])
      setSuggestionTotal(0)
      setSuggestionPage(1)
      setSuggestionPageSize(defaultSuggestionPageSize)
    }
  }

  useEffect(() => {
    void loadSchemaCount()
    void loadMappings()
    void loadStats()
    void loadLatestTask()
  }, [currentProject?.id, currentVersion?.id])

  useEffect(() => {
    const projectDefaults = currentProject?.asset_config?.field_mapping_defaults
    const versionOverrides = currentVersion?.mapping_config?.field_mapping_overrides
    const runtimeBinding = currentVersion?.mapping_config?.runtime_binding

    setUseAi(versionOverrides?.allow_ai ?? projectDefaults?.use_ai ?? true)
    setUseSqlLineage(versionOverrides?.use_sql_lineage ?? projectDefaults?.use_sql_lineage ?? true)
    setUseCodeLineage(versionOverrides?.use_code_lineage ?? projectDefaults?.use_code_lineage ?? true)
    setUseRuntimeVerification(
      versionOverrides?.use_runtime_verification ?? projectDefaults?.use_runtime_verification ?? true,
    )
    setEvidenceMode(projectDefaults?.evidence_mode ?? 'balanced')
    setRebuildLineageBeforeRun(Boolean(runtimeBinding?.auto_build_sql_lineage))
  }, [currentProject?.asset_config, currentVersion?.mapping_config])

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
    setSuggestionPage(1)
  }, [fieldTypeFilter, methodFilter, pathFilter, searchKeyword, statusFilter])

  useEffect(() => {
    if (taskId && task && (task.status === 'completed' || task.status === 'partial_success')) {
      void loadSuggestions(taskId)
    }
  }, [fieldTypeFilter, methodFilter, pathFilter, searchKeyword, statusFilter, suggestionPage, suggestionPageSize, task?.status, taskId])

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
          use_sql_lineage: useSqlLineage,
          use_code_lineage: useCodeLineage,
          use_runtime_verification: useRuntimeVerification,
          evidence_mode: evidenceMode,
          rebuild_lineage_before_run: rebuildLineageBeforeRun,
          selected_execution_ids: currentVersion?.mapping_config?.runtime_binding?.selected_execution_ids || [],
          workspace_root: currentProject?.asset_config?.repository?.workspace_root,
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
      setSuggestionTotal(0)
      setSuggestionPage(1)
      setSuggestionPageSize(defaultSuggestionPageSize)
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
          relation_type: candidate.relation_type || item.relation_type || item.decision_artifact?.relation_type || 'direct',
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
      title: '候选映射',
      key: 'candidate',
      render: (_, record) => {
        const candidate = record.top_candidate || record.candidates?.[0]
        if (!candidate) {
          return <Text type="secondary">暂无候选</Text>
        }

        return (
          <Space direction="vertical" size={2}>
            <Text strong>{candidate.db_table}.{candidate.db_column}</Text>
            <Text type="secondary">{candidate.reasons?.join(' / ') || '暂无说明'}</Text>
          </Space>
        )
      },
    },
    {
      title: '置信度',
      key: 'confidence',
      width: 180,
      render: (_, record) => {
        const confidence = (
          record.confidence
          ?? record.top_candidate?.confidence
          ?? record.candidates?.[0]?.confidence
          ?? record.candidates?.[0]?.score
        ) || 0
        return <Progress percent={Number((confidence * 100).toFixed(1))} size="small" />
      },
    },
    {
      title: '决策',
      key: 'decision',
      width: 180,
      render: (_, record) => {
        const decisionSource = record.decision_source || record.decision_artifact?.decision_source || 'rule'
        const relationType = record.relation_type || record.decision_artifact?.relation_type || 'direct'
        return (
          <Space wrap>
            <Tag color={getDecisionSourceColor(decisionSource)}>{decisionSource}</Tag>
            <Tag color={getRelationTypeColor(relationType)}>{relationType}</Tag>
          </Space>
        )
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
                    <Space align="center" style={{ marginBottom: 4 }}>
                      <Title level={5} style={{ marginBottom: 0 }}>生成配置</Title>
                      <Link to="/version-center/field-mapping/help">
                        <Space size={4}>
                          <QuestionCircleOutlined />
                          <Text>功能说明</Text>
                        </Space>
                      </Link>
                    </Space>
                    <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      当前版本已导入 {schemaCount} 份数据库结构。任务会调用后端异步建议流程并写入可审阅的建议记录。
                    </Paragraph>
                  </div>
                  <div className="governance-switch-list">
                    <span><Text>Path 参数</Text><Switch checked={includePaths} onChange={setIncludePaths} /></span>
                    <span><Text>Query 参数</Text><Switch checked={includeQuery} onChange={setIncludeQuery} /></span>
                    <span><Text>Body 参数</Text><Switch checked={includeBody} onChange={setIncludeBody} /></span>
                    <span><Text>启用 AI</Text><Switch checked={useAi} onChange={setUseAi} /></span>
                    <span><Text>SQL Lineage</Text><Switch checked={useSqlLineage} onChange={setUseSqlLineage} /></span>
                    <span><Text>Code Lineage</Text><Switch checked={useCodeLineage} onChange={setUseCodeLineage} /></span>
                    <span><Text>Runtime Verification</Text><Switch checked={useRuntimeVerification} onChange={setUseRuntimeVerification} /></span>
                    <span><Text>运行前重建 Lineage</Text><Switch checked={rebuildLineageBeforeRun} onChange={setRebuildLineageBeforeRun} /></span>
                    <span><Text>高优先级</Text><Switch checked={highPriorityEnabled} onChange={setHighPriorityEnabled} disabled={!useAi} /></span>
                    <span><Text>中优先级</Text><Switch checked={mediumPriorityEnabled} onChange={setMediumPriorityEnabled} disabled={!useAi} /></span>
                    <span><Text>低优先级</Text><Switch checked={lowPriorityEnabled} onChange={setLowPriorityEnabled} disabled={!useAi} /></span>
                  </div>
                  <Space wrap>
                    <Text type="secondary">证据模式</Text>
                    <Select value={evidenceMode} onChange={(value) => setEvidenceMode(value as typeof evidenceMode)} style={{ width: 180 }}>
                      <Select.Option value="balanced">balanced</Select.Option>
                      <Select.Option value="conservative">conservative</Select.Option>
                      <Select.Option value="aggressive">aggressive</Select.Option>
                    </Select>
                    <Text type="secondary">
                      版本绑定 Schema: {currentVersion?.mapping_config?.schema_binding?.selected_schema_id || '-'}
                    </Text>
                    <Text type="secondary">
                      绑定 Execution: {(currentVersion?.mapping_config?.runtime_binding?.selected_execution_ids || []).length}
                    </Text>
                  </Space>
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
                  <FieldMappingTaskObservability task={task} />
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
                  <Select.Option value="pending">待审核</Select.Option>
                  <Select.Option value="confirmed">已确认</Select.Option>
                  <Select.Option value="rejected">已拒绝</Select.Option>
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
                <Select value={decisionSourceFilter} onChange={(value) => setDecisionSourceFilter(value as DecisionSourceFilter)} style={{ width: 140 }}>
                  <Select.Option value="all">全部来源</Select.Option>
                  <Select.Option value="rule">规则</Select.Option>
                  <Select.Option value="ai">AI</Select.Option>
                  <Select.Option value="fallback">降级</Select.Option>
                </Select>
                <Select value={relationTypeFilter} onChange={(value) => setRelationTypeFilter(value as RelationTypeFilter)} style={{ width: 140 }}>
                  <Select.Option value="all">全部关系</Select.Option>
                  <Select.Option value="direct">direct</Select.Option>
                  <Select.Option value="fk">fk</Select.Option>
                  <Select.Option value="derived">derived</Select.Option>
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
                  dataSource={visibleSuggestions}
                  scroll={{ y: 'calc(100vh - 520px)' }}
                  pagination={{
                    current: suggestionPage,
                    pageSize: suggestionPageSize,
                    total: suggestionTotal,
                    showSizeChanger: true,
                    pageSizeOptions: suggestionPageSizeOptions,
                    hideOnSinglePage: false,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page, pageSize) => {
                      setSuggestionPage(page)
                      setSuggestionPageSize(pageSize)
                    },
                  }}
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
                    { label: '已确认', value: 'confirmed' },
                    { label: '已拒绝', value: 'rejected' },
                    { label: '待审核', value: 'proposed' },
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
              <Descriptions.Item label="决策来源">
                <Tag color={getDecisionSourceColor(selectedSuggestion.decision_source || selectedSuggestion.decision_artifact?.decision_source)}>
                  {selectedSuggestion.decision_source || selectedSuggestion.decision_artifact?.decision_source || 'rule'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="关系类型">
                <Tag color={getRelationTypeColor(selectedSuggestion.relation_type || selectedSuggestion.decision_artifact?.relation_type)}>
                  {selectedSuggestion.relation_type || selectedSuggestion.decision_artifact?.relation_type || 'direct'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="最终置信度">
                {formatPercent(selectedSuggestion.confidence ?? selectedSuggestion.decision_artifact?.confidence)}
              </Descriptions.Item>
            </Descriptions>

            {selectedSuggestion.decision_artifact ? (
              <Card className="governance-note-card" bordered={false}>
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  <Title level={5} style={{ marginBottom: 0 }}>决策产物</Title>
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="最高候选">
                      {selectedSuggestion.decision_artifact.top_candidate
                        ? `${selectedSuggestion.decision_artifact.top_candidate.db_table}.${selectedSuggestion.decision_artifact.top_candidate.db_column}`
                        : '-'}
                    </Descriptions.Item>
                    <Descriptions.Item label="来源">{selectedSuggestion.decision_artifact.decision_source || '-'}</Descriptions.Item>
                    <Descriptions.Item label="关系">{selectedSuggestion.decision_artifact.relation_type || '-'}</Descriptions.Item>
                    <Descriptions.Item label="置信度">{formatPercent(selectedSuggestion.decision_artifact.confidence)}</Descriptions.Item>
                  </Descriptions>
                </Space>
              </Card>
            ) : null}

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
                              {candidate.ai_selected ? 'AI 选中' : '规则选中'}
                            </Tag>
                          </Space>
                          <Text type="secondary">score: {(candidate.score * 100).toFixed(1)}%（排序分）</Text>
                          {typeof candidate.confidence === 'number' ? <Text type="secondary">confidence: {formatPercent(candidate.confidence)}（最终置信度）</Text> : null}
                          {candidate.relation_type ? <Text type="secondary">relation: {candidate.relation_type}</Text> : null}
                          {candidate.negative_evidence?.length ? <Text type="secondary">negative: {candidate.negative_evidence.join(' / ')}</Text> : null}
                          {candidate.reject_reasons?.length ? <Text type="secondary">reject: {candidate.reject_reasons.join(' / ')}</Text> : null}
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
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="来源">
                      {renderTraceValue(selectedSuggestion.decision_trace.decision_source)}
                    </Descriptions.Item>
                    <Descriptions.Item label="最高候选">
                      {renderTraceValue(selectedSuggestion.decision_trace.top_candidate_key || selectedSuggestion.decision_trace.top_final_candidate)}
                    </Descriptions.Item>
                    <Descriptions.Item label="关系">
                      {renderTraceValue(selectedSuggestion.decision_trace.relation_type)}
                    </Descriptions.Item>
                    <Descriptions.Item label="置信度">
                      {typeof selectedSuggestion.decision_trace.confidence === 'number'
                        ? formatPercent(selectedSuggestion.decision_trace.confidence)
                        : renderTraceValue(selectedSuggestion.decision_trace.confidence)}
                    </Descriptions.Item>
                    <Descriptions.Item label="降级原因">
                      {renderTraceValue(selectedSuggestion.decision_trace.fallback_reason)}
                    </Descriptions.Item>
                    <Descriptions.Item label="运行时先验">
                      {renderKeyValueTags((selectedSuggestion.decision_trace.runtime_table_prior || {}) as Record<string, unknown>)}
                    </Descriptions.Item>
                    <Descriptions.Item label="负向证据">
                      {selectedSuggestion.candidates?.[0]?.negative_evidence?.length
                        ? selectedSuggestion.candidates[0].negative_evidence.join(' / ')
                        : '-'}
                    </Descriptions.Item>
                    <Descriptions.Item label="拒绝原因">
                      {selectedSuggestion.candidates?.[0]?.reject_reasons?.length
                        ? selectedSuggestion.candidates[0].reject_reasons.join(' / ')
                        : '-'}
                    </Descriptions.Item>
                  </Descriptions>
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
