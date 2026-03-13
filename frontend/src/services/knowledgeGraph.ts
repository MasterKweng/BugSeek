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

export async function getTablesByApi(nodeId: string): Promise<{ items: GraphNode[] }> {
  return await get(`/graph/api/${nodeId}/tables`)
}

export async function getApisByTable(nodeId: string): Promise<{ items: GraphNode[] }> {
  return await get(`/graph/table/${nodeId}/apis`)
}
