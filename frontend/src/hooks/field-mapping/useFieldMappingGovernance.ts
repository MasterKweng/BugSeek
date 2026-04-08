import { useEffect, useMemo, useState } from 'react'
import { message } from 'antd'
import { useProjectStore } from '../../store/project'
import {
  autoApplyFieldMappings,
  cloneFieldMappings,
  deleteFieldMapping,
  getFieldMappings,
  getLearningStats,
  getPendingFieldMappings,
  updateFieldMappingStatus,
  type FieldMappingWithDetails,
  type PendingFieldMapping,
} from '../../services/fieldMappingGovernance'

export type MappingFilter = 'all' | 'confirmed' | 'rejected' | 'proposed'

export const useFieldMappingGovernance = () => {
  const { currentProject, currentVersion, versions } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [mappingsLoading, setMappingsLoading] = useState(false)
  const [pendingLoading, setPendingLoading] = useState(false)
  const [cloneModalOpen, setCloneModalOpen] = useState(false)
  const [mappingFilter, setMappingFilter] = useState<MappingFilter>('all')
  const [mappings, setMappings] = useState<FieldMappingWithDetails[]>([])
  const [pendingMappings, setPendingMappings] = useState<PendingFieldMapping[]>([])
  const [stats, setStats] = useState<{
    total_mappings: number
    confirmed_mappings: number
    proposed_mappings: number
    rejected_mappings: number
    avg_confidence: number
    ai_mappings: number
    manual_mappings: number
  } | null>(null)

  const contextParams = useMemo(() => ({
    project_id: currentProject?.id,
    version_id: currentVersion?.id,
  }), [currentProject?.id, currentVersion?.id])

  const metrics = useMemo(() => [
    { label: '总映射', value: stats?.total_mappings ?? mappings.length },
    { label: '待处理', value: pendingMappings.length },
    { label: '当前版本', value: currentVersion?.version_number || '-' },
  ], [currentVersion?.version_number, mappings.length, pendingMappings.length, stats?.total_mappings])

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

  const loadPendingMappings = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      setPendingMappings([])
      return
    }

    setPendingLoading(true)
    try {
      const response = await getPendingFieldMappings(contextParams)
      setPendingMappings(response.data?.items || [])
    } catch (error: any) {
      message.error(error.message || '获取待处理映射失败')
    } finally {
      setPendingLoading(false)
    }
  }

  useEffect(() => {
    void loadStats()
    void loadMappings()
    void loadPendingMappings()
  }, [currentProject?.id, currentVersion?.id])

  const handleAutoApply = async () => {
    setLoading(true)
    try {
      const response = await autoApplyFieldMappings({ min_confidence: 0.85 }, contextParams)
      message.success(`已自动应用 ${response.data?.updated_count ?? 0} 条高置信映射`)
      await loadMappings()
      await loadPendingMappings()
      await loadStats()
    } catch (error: any) {
      message.error(error.message || '自动应用失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteMapping = async (mappingId: number) => {
    setMappingsLoading(true)
    try {
      await deleteFieldMapping(mappingId, contextParams)
      message.success('映射已删除')
      await loadMappings()
      await loadPendingMappings()
      await loadStats()
    } catch (error: any) {
      message.error(error.message || '删除映射失败')
    } finally {
      setMappingsLoading(false)
    }
  }

  const handlePendingStatusChange = async (mappingId: number, status: 'confirmed' | 'rejected' | 'proposed') => {
    setPendingLoading(true)
    try {
      await updateFieldMappingStatus(mappingId, status, contextParams)
      message.success('映射状态已更新')
      await loadMappings()
      await loadPendingMappings()
      await loadStats()
    } catch (error: any) {
      message.error(error.message || '更新映射状态失败')
    } finally {
      setPendingLoading(false)
    }
  }

  const handleCloneMappings = async (sourceVersionId: number, targetVersionId: number) => {
    setLoading(true)
    try {
      const response = await cloneFieldMappings({
        from_version_id: sourceVersionId,
        to_version_id: targetVersionId,
      }, { project_id: currentProject?.id })
      message.success(`已克隆 ${response.data?.cloned_count ?? 0} 条映射`)
      await loadMappings()
      await loadPendingMappings()
      await loadStats()
    } catch (error: any) {
      message.error(error.message || '克隆映射失败')
      throw error
    } finally {
      setLoading(false)
    }
  }

  return {
    currentProject,
    currentVersion,
    versions,
    loading,
    mappingsLoading,
    pendingLoading,
    cloneModalOpen,
    mappingFilter,
    mappings,
    pendingMappings,
    stats,
    metrics,
    setCloneModalOpen,
    setMappingFilter,
    handleAutoApply,
    handleDeleteMapping,
    handlePendingStatusChange,
    handleCloneMappings,
  }
}

export default useFieldMappingGovernance
