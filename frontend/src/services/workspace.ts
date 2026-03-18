import api from './api'
import type { ApiResponse } from './api'

export interface WorkspaceCountCard {
  key: 'definitions' | 'cases' | 'syncTasks' | 'scenarios'
  total: number
}

export interface WorkspaceOverview {
  counts: WorkspaceCountCard[]
  recentDefinitions: Array<{
    id: number
    method: string
    path: string
    summary: string | null
    sync_status: string
    updated_at: string
    case_count: number
  }>
  recentCases: Array<{
    id: number
    name: string
    priority: string
    case_type: string
    updated_at: string
    definition_id: number
    environment_name: string | null
  }>
  recentSyncTasks: Array<{
    id: number
    name: string
    status: string
    progress: number
    source_type: string
    created_at: string
    completed_at: string | null
  }>
  recentScenarios: Array<{
    id: number
    name: string
    status: string
    scenario_type: string
    updated_at: string
    node_count: number
  }>
}

export const getWorkspaceOverview = async (
  projectId: number,
): Promise<ApiResponse<WorkspaceOverview>> => {
  const results = await Promise.allSettled([
    api.get('/api-definitions?skip=0&limit=5'),
    api.get('/api-cases?skip=0&limit=5'),
    api.get(`/sync-tasks?skip=0&limit=5&project_id=${projectId}`),
    api.get(`/scenarios?skip=0&limit=5&project_id=${projectId}`),
  ])

  const definitions =
    results[0].status === 'fulfilled' ? results[0].value : { data: { total: 0, items: [] } }
  const cases =
    results[1].status === 'fulfilled' ? results[1].value : { data: { total: 0, items: [] } }
  const syncTasks =
    results[2].status === 'fulfilled' ? results[2].value : { data: { total: 0, items: [] } }
  const scenarios =
    results[3].status === 'fulfilled' ? results[3].value : { data: { total: 0, items: [] } }

  return {
    code: 0,
    message: 'success',
    data: {
      counts: [
        { key: 'definitions', total: definitions.data?.total || 0 },
        { key: 'cases', total: cases.data?.total || 0 },
        { key: 'syncTasks', total: syncTasks.data?.total || 0 },
        { key: 'scenarios', total: scenarios.data?.total || 0 },
      ],
      recentDefinitions: definitions.data?.items || [],
      recentCases: cases.data?.items || [],
      recentSyncTasks: syncTasks.data?.items || [],
      recentScenarios: scenarios.data?.items || [],
    },
  }
}
