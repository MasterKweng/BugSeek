import { get } from './request'

export type GraphNode = {
  id: string
  node_type: string
  name: string
  display_name?: string
  source_id?: string
  properties?: Record<string, any>
}

export async function getNode(nodeId: string): Promise<GraphNode> {
  return await get(`/graph/node/${nodeId}`)
}

export async function getNodes(params?: {
  node_type?: string
  search?: string
  limit?: number
}): Promise<{ items: GraphNode[]; total: number }> {
  return await get('/graph/nodes', params)
}

export async function getTablesByApi(nodeId: string): Promise<{ items: GraphNode[] }> {
  return await get(`/graph/api/${nodeId}/tables`)
}

export async function getApisByTable(nodeId: string): Promise<{ items: GraphNode[] }> {
  return await get(`/graph/table/${nodeId}/apis`)
}

export async function getFieldsByApi(nodeId: string): Promise<{ items: GraphNode[] }> {
  return await get(`/graph/api/${nodeId}/fields`)
}

export async function getFieldsByTable(nodeId: string): Promise<{ items: GraphNode[] }> {
  return await get(`/graph/table/${nodeId}/fields`)
}

export async function getApisByField(nodeId: string): Promise<{ items: GraphNode[] }> {
  return await get(`/graph/field/${nodeId}/apis`)
}

export async function getTablesByField(nodeId: string): Promise<{ items: GraphNode[] }> {
  return await get(`/graph/field/${nodeId}/tables`)
}
