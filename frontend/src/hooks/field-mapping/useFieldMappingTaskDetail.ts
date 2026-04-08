import { useEffect, useMemo, useState } from 'react'
import { message, Modal } from 'antd'
import { useProjectStore } from '../../store/project'
import {
  cancelAsyncTask,
  getAsyncTask,
  replayTaskSuggestions,
  resetTask,
  resumeTask,
  retryStage,
  type AsyncTask,
} from '../../services/fieldMappingTask'
import {
  batchApplyFieldMappings,
  batchRejectSuggestions,
  getFieldMappingSuggestions,
  type FieldMappingSuggestion,
  type FieldMappingSuggestionResponse,
} from '../../services/fieldMappingSuggestion'

type SuggestionStatusFilter = 'all' | 'pending' | 'confirmed' | 'rejected'
type MethodFilter = 'all' | 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
type FieldTypeFilter = 'all' | 'path' | 'query' | 'body'
type DecisionSourceFilter = 'all' | 'rule' | 'ai' | 'fallback'
type RelationTypeFilter = 'all' | 'direct' | 'fk' | 'derived'

interface CountItem {
  key: string
  count: number
}

export interface TaskEvidenceContribution {
  totalSuggestions: number
  analyzedSuggestions: number
  decisionSources: CountItem[]
  recallSources: CountItem[]
  positiveFeatures: CountItem[]
  negativeEvidence: CountItem[]
  effectiveSignals: {
    sql: number
    code: number
    runtime: number
    cross: number
    vector: number
    history: number
    lexical: number
  }
}

const isPositiveFeatureValue = (value: unknown): boolean => {
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'number') {
    return value > 0
  }
  return false
}

const toSortedCounts = (counter: Map<string, number>, limit = 8): CountItem[] => (
  Array.from(counter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([key, count]) => ({ key, count }))
)

export const useFieldMappingTaskDetail = (parsedTaskId: number) => {
  const defaultSuggestionPageSize = 20
  const { currentProject, currentVersion } = useProjectStore()

  const [loading, setLoading] = useState(false)
  const [task, setTask] = useState<AsyncTask | null>(null)
  const [suggestions, setSuggestions] = useState<FieldMappingSuggestion[]>([])
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [selectedSuggestion, setSelectedSuggestion] = useState<FieldMappingSuggestion | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false)
  const [stageDetailOpen, setStageDetailOpen] = useState(false)
  const [consistencyDrawerOpen, setConsistencyDrawerOpen] = useState(false)
  const [selectedStageNum, setSelectedStageNum] = useState<number | null>(null)
  const [actionLoading, setActionLoading] = useState<'cancel' | 'resume' | 'reset' | null>(null)
  const [retryingStageNum, setRetryingStageNum] = useState<number | null>(null)
  const [replayLoading, setReplayLoading] = useState(false)
  const [suggestionPage, setSuggestionPage] = useState(1)
  const [suggestionPageSize, setSuggestionPageSize] = useState(defaultSuggestionPageSize)
  const [suggestionTotal, setSuggestionTotal] = useState(0)
  const [evidenceSuggestions, setEvidenceSuggestions] = useState<FieldMappingSuggestion[]>([])
  const [evidenceLoading, setEvidenceLoading] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [pathFilter, setPathFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<SuggestionStatusFilter>('all')
  const [methodFilter, setMethodFilter] = useState<MethodFilter>('all')
  const [fieldTypeFilter, setFieldTypeFilter] = useState<FieldTypeFilter>('all')
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

  const metrics = useMemo(() => {
    const highConfidence = suggestions.filter((item) => (
      (item.confidence ?? item.candidates?.[0]?.confidence ?? item.candidates?.[0]?.score) || 0
    ) >= 0.85).length

    return [
      { label: '任务 ID', value: parsedTaskId || '-' },
      { label: '建议数', value: suggestionTotal || suggestions.length },
      { label: '高置信', value: highConfidence },
      { label: '任务状态', value: task?.status || '-' },
    ]
  }, [parsedTaskId, suggestionTotal, suggestions, task?.status])

  const evidenceContribution = useMemo<TaskEvidenceContribution | null>(() => {
    const base = evidenceSuggestions.length ? evidenceSuggestions : suggestions
    if (!base.length) {
      return null
    }

    const decisionSources = new Map<string, number>()
    const recallSources = new Map<string, number>()
    const positiveFeatures = new Map<string, number>()
    const negativeEvidence = new Map<string, number>()

    let sql = 0
    let code = 0
    let runtime = 0
    let cross = 0
    let vector = 0
    let history = 0
    let lexical = 0

    base.forEach((suggestion) => {
      const decisionSource = suggestion.decision_source || suggestion.decision_artifact?.decision_source || suggestion.source || 'unknown'
      decisionSources.set(decisionSource, (decisionSources.get(decisionSource) || 0) + 1)

      const topCandidate = suggestion.candidates?.[0]
      ;(topCandidate?.recall_sources || []).forEach((source) => {
        recallSources.set(source, (recallSources.get(source) || 0) + 1)
      })

      Object.entries(topCandidate?.features || {}).forEach(([featureKey, featureValue]) => {
        if (!isPositiveFeatureValue(featureValue)) {
          return
        }

        positiveFeatures.set(featureKey, (positiveFeatures.get(featureKey) || 0) + 1)

        if (featureKey === 'f_sql_lineage_exact' || featureKey === 'f_sql_transform_strength') sql += 1
        if (featureKey === 'f_code_assignment_hit' || featureKey === 'f_code_trace_strength') code += 1
        if (featureKey === 'f_runtime_field_hit') runtime += 1
        if (featureKey === 'f_cross_lineage_agreement') cross += 1
        if (featureKey === 'f_vector_similarity') vector += 1
        if (featureKey === 'f_history_prior') history += 1
        if (
          featureKey === 'f_name_similarity'
          || featureKey === 'f_name_exact'
          || featureKey === 'f_exact_rule_boost'
          || featureKey === 'f_acronym_match'
        ) lexical += 1
      })

      ;[
        ...(topCandidate?.negative_evidence || []),
        ...(topCandidate?.reject_reasons || []),
      ].forEach((item) => {
        negativeEvidence.set(item, (negativeEvidence.get(item) || 0) + 1)
      })
    })

    return {
      totalSuggestions: suggestionTotal || base.length,
      analyzedSuggestions: base.length,
      decisionSources: toSortedCounts(decisionSources),
      recallSources: toSortedCounts(recallSources),
      positiveFeatures: toSortedCounts(positiveFeatures),
      negativeEvidence: toSortedCounts(negativeEvidence),
      effectiveSignals: {
        sql,
        code,
        runtime,
        cross,
        vector,
        history,
        lexical,
      },
    }
  }, [evidenceSuggestions, suggestionTotal, suggestions])

  const loadTask = async () => {
    if (!parsedTaskId) {
      return
    }

    try {
      const response = await getAsyncTask(parsedTaskId)
      setTask(response.data || null)
    } catch (error: any) {
      message.error(error.message || '获取任务状态失败')
    }
  }

  const loadSuggestions = async () => {
    if (!parsedTaskId) {
      return
    }

    setLoading(true)
    try {
      const response = await getFieldMappingSuggestions(parsedTaskId, {
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

  const loadEvidenceSuggestions = async () => {
    if (!parsedTaskId) {
      return
    }

    setEvidenceLoading(true)
    try {
      const response = await getFieldMappingSuggestions(parsedTaskId, {
        page: 1,
        size: 5000,
      })
      const data: FieldMappingSuggestionResponse | undefined = response.data
      setEvidenceSuggestions(data?.items || [])
    } catch (error) {
      console.error('[FieldMappingTaskDetail] Failed to load evidence suggestions:', error)
      setEvidenceSuggestions([])
    } finally {
      setEvidenceLoading(false)
    }
  }

  const reloadTaskContext = async () => {
    await loadTask()
    if (task && (task.status === 'completed' || task.status === 'partial_success')) {
      await loadSuggestions()
    }
  }

  useEffect(() => {
    if (!parsedTaskId) {
      return
    }
    void loadTask()
  }, [parsedTaskId])

  useEffect(() => {
    if (!task || (task.status !== 'pending' && task.status !== 'running')) {
      return
    }

    const timer = window.setInterval(() => {
      void loadTask()
    }, 3000)

    return () => window.clearInterval(timer)
  }, [task?.status, parsedTaskId])

  useEffect(() => {
    setSuggestionPage(1)
  }, [fieldTypeFilter, methodFilter, pathFilter, searchKeyword, statusFilter])

  useEffect(() => {
    if (task && (task.status === 'completed' || task.status === 'partial_success')) {
      void loadSuggestions()
    }
  }, [fieldTypeFilter, methodFilter, pathFilter, searchKeyword, statusFilter, suggestionPage, suggestionPageSize, task?.status, parsedTaskId])

  useEffect(() => {
    if (task && (task.status === 'completed' || task.status === 'partial_success')) {
      void loadEvidenceSuggestions()
      return
    }
    setEvidenceSuggestions([])
  }, [parsedTaskId, task?.status])

  const handleConfirmSuggestions = async () => {
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
      await loadSuggestions()
      await loadEvidenceSuggestions()
      await loadTask()
    } catch (error: any) {
      message.error(error.message || '应用建议失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRejectSuggestions = async () => {
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
      await loadSuggestions()
      await loadEvidenceSuggestions()
      await loadTask()
    } catch (error: any) {
      message.error(error.message || '拒绝建议失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCancelTask = async () => {
    Modal.confirm({
      title: '确认取消任务',
      content: '取消后任务将停止继续执行，是否继续？',
      okText: '确认',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        setActionLoading('cancel')
        try {
          await cancelAsyncTask(parsedTaskId)
          message.success('任务已取消')
          await loadTask()
        } catch (error: any) {
          message.error(error.message || '取消任务失败')
        } finally {
          setActionLoading(null)
        }
      },
    })
  }

  const handleResumeTask = async () => {
    setActionLoading('resume')
    try {
      await resumeTask(parsedTaskId)
      message.success('任务已继续执行')
      await loadTask()
    } catch (error: any) {
      message.error(error.message || '继续执行失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleResetTask = async () => {
    Modal.confirm({
      title: '确认重置任务',
      content: '重置会清除当前任务阶段进度与结果，任务将回到初始状态。',
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        setActionLoading('reset')
        try {
          await resetTask(parsedTaskId)
          message.success('任务已重置')
          setSelectedRowKeys([])
          setSuggestions([])
          setSuggestionTotal(0)
          await loadTask()
        } catch (error: any) {
          message.error(error.message || '重置任务失败')
        } finally {
          setActionLoading(null)
        }
      },
    })
  }

  const handleRetryStage = async (stageNum: number) => {
    setRetryingStageNum(stageNum)
    try {
      await retryStage(parsedTaskId, stageNum)
      message.success(`已重试阶段 ${stageNum}`)
      await loadTask()
    } catch (error: any) {
      message.error(error.message || '重试阶段失败')
    } finally {
      setRetryingStageNum(null)
    }
  }

  const handleReplaySuggestions = async () => {
    setReplayLoading(true)
    try {
      const response = await replayTaskSuggestions(parsedTaskId)
      const replayStats = response.data
      message.success(
        replayStats
          ? `Recovered ${replayStats.suggestions_count} suggestions`
          : 'Suggestions replayed successfully',
      )
      await loadTask()
      await loadSuggestions()
      await loadEvidenceSuggestions()
    } catch (error: any) {
      message.error(error.message || 'Replay suggestions failed')
    } finally {
      setReplayLoading(false)
    }
  }

  return {
    currentProject,
    currentVersion,
    loading,
    task,
    suggestions,
    selectedRowKeys,
    selectedSuggestion,
    detailOpen,
    historyDrawerOpen,
    stageDetailOpen,
    consistencyDrawerOpen,
    selectedStageNum,
    actionLoading,
    retryingStageNum,
    replayLoading,
    suggestionPage,
    suggestionPageSize,
    suggestionTotal,
    searchKeyword,
    pathFilter,
    statusFilter,
    methodFilter,
    fieldTypeFilter,
    decisionSourceFilter,
    relationTypeFilter,
    visibleSuggestions,
    selectedSuggestions,
    metrics,
    evidenceLoading,
    evidenceContribution,
    setSelectedRowKeys,
    setSelectedSuggestion,
    setDetailOpen,
    setHistoryDrawerOpen,
    setStageDetailOpen,
    setConsistencyDrawerOpen,
    setSelectedStageNum,
    setSuggestionPage,
    setSuggestionPageSize,
    setSearchKeyword,
    setPathFilter,
    setStatusFilter,
    setMethodFilter,
    setFieldTypeFilter,
    setDecisionSourceFilter,
    setRelationTypeFilter,
    reloadTaskContext,
    loadSuggestions,
    handleConfirmSuggestions,
    handleRejectSuggestions,
    handleCancelTask,
    handleResumeTask,
    handleResetTask,
    handleRetryStage,
    handleReplaySuggestions,
  }
}

export default useFieldMappingTaskDetail
