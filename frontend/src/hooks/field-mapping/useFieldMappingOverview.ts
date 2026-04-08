import { useEffect, useMemo, useState } from 'react'
import { message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '../../store/project'
import { getDbSchemas } from '../../services/dbSchema'
import {
  createFieldMappingSuggestTask,
  listAsyncTasks,
  type AsyncTaskSummary,
} from '../../services/fieldMappingTask'

export const useFieldMappingOverview = () => {
  const navigate = useNavigate()
  const { currentProject, currentVersion } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [schemaCount, setSchemaCount] = useState(0)
  const [recentTasks, setRecentTasks] = useState<AsyncTaskSummary[]>([])

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

  const contextParams = useMemo(() => ({
    project_id: currentProject?.id,
    version_id: currentVersion?.id,
  }), [currentProject?.id, currentVersion?.id])

  const metrics = useMemo(() => {
    const latestTask = recentTasks[0]
    return [
      { label: '最近任务', value: latestTask ? `#${latestTask.id}` : '-' },
      { label: '最近状态', value: latestTask?.status || '-' },
      { label: 'Schema 数量', value: schemaCount },
    ]
  }, [recentTasks, schemaCount])

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

  const loadTaskHistory = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      setRecentTasks([])
      return
    }

    setHistoryLoading(true)
    try {
      const response = await listAsyncTasks({
        project_id: currentProject.id,
        version_id: currentVersion.id,
        task_type: 'field_mapping_suggest',
        limit: 5,
        offset: 0,
      })
      setRecentTasks(response.data?.items || [])
    } catch (error: any) {
      setRecentTasks([])
      message.error(error.message || '获取任务历史失败')
    } finally {
      setHistoryLoading(false)
    }
  }

  useEffect(() => {
    void loadSchemaCount()
    void loadTaskHistory()
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
      const response = await createFieldMappingSuggestTask({
        include_paths: includePaths,
        include_query: includeQuery,
        include_body: includeBody,
        use_ai: useAi,
        use_sql_lineage: useSqlLineage,
        use_code_lineage: useCodeLineage,
        use_runtime_verification: useRuntimeVerification,
        evidence_mode: evidenceMode,
        rebuild_lineage_before_run: rebuildLineageBeforeRun,
        high_priority_enabled: highPriorityEnabled,
        medium_priority_enabled: mediumPriorityEnabled,
        low_priority_enabled: lowPriorityEnabled,
      }, contextParams)

      const taskId = response.data?.task_id
      if (!taskId) {
        throw new Error('任务创建成功，但未返回 task_id')
      }

      message.success('字段映射任务已创建')
      void loadTaskHistory()
      navigate(`/version-center/field-mapping/tasks/${taskId}`)
    } catch (error: any) {
      message.error(error.message || '创建字段映射任务失败')
    } finally {
      setLoading(false)
    }
  }

  return {
    currentProject,
    currentVersion,
    loading,
    historyLoading,
    schemaCount,
    recentTasks,
    includePaths,
    includeQuery,
    includeBody,
    useAi,
    useSqlLineage,
    useCodeLineage,
    useRuntimeVerification,
    evidenceMode,
    rebuildLineageBeforeRun,
    highPriorityEnabled,
    mediumPriorityEnabled,
    lowPriorityEnabled,
    metrics,
    setIncludePaths,
    setIncludeQuery,
    setIncludeBody,
    setUseAi,
    setUseSqlLineage,
    setUseCodeLineage,
    setUseRuntimeVerification,
    setEvidenceMode,
    setRebuildLineageBeforeRun,
    setHighPriorityEnabled,
    setMediumPriorityEnabled,
    setLowPriorityEnabled,
    loadSchemaCount,
    loadTaskHistory,
    handleCreateTask,
  }
}

export default useFieldMappingOverview
