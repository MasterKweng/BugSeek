import * as request from './request'
import type { ScenarioTemplate } from '../types/scenario'

export interface ScenarioTemplateCreatePayload {
  name: string
  description?: string | null
  category?: string | null
  version_id?: number | null
  environment_id?: number | null
  scenario_type?: string
  execution_mode?: string
  timeout_seconds?: number
  retry_count?: number
  continue_on_failure?: boolean
  context_init?: Record<string, unknown>
  nodes: Array<Record<string, unknown>>
}

export const listScenarioTemplates = async (
  projectId?: number,
): Promise<{ items: ScenarioTemplate[] }> => request.get('/scenario-templates', { project_id: projectId })

export const createScenarioTemplate = async (
  payload: ScenarioTemplateCreatePayload,
  projectId?: number,
): Promise<ScenarioTemplate> => request.post(`/scenario-templates${projectId ? `?project_id=${projectId}` : ''}`, payload)

export const instantiateScenarioTemplate = async (
  templateId: number,
  variables: Record<string, unknown> = {},
  projectId?: number,
): Promise<{
  scenario_id: number
  name: string
  draft_revision_id?: number | null
  lifecycle_status?: string
  source_template_id: number
}> =>
  request.post(`/scenario-drafts:instantiate-template${projectId ? `?project_id=${projectId}` : ''}`, {
    template_id: templateId,
    variables,
  })
