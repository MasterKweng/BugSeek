import React, { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import api from '../../services/api'
import { useProjectStore } from '../../store/project'
import type { Environment, ScenarioDetail, ScenarioNode } from '../../types/scenario'
import './ScenarioDesigner.css'

interface ApiDefinitionOption {
  id: number
  method: string
  path: string
  summary?: string
}

interface NodeFormValues {
  node_key: string
  node_name?: string
  node_type: string
  ref_type: string
  ref_id: number
  step_order?: number
  depends_on?: string[]
  input_mapping?: string
  extract_rules?: string
  assertion_overrides?: string
  timeout_seconds?: number | null
  retry_count?: number
  continue_on_failure?: boolean
  is_enabled?: boolean
  extra_config?: string
}

const { TextArea } = Input
const { Text } = Typography
const DEFAULT_API_DEFINITION_EXTRA_CONFIG = JSON.stringify(
  {
    case_selection: {
      strategy: 'first_active',
    },
  },
  null,
  2,
)

const safeJsonParse = (value?: string): Record<string, unknown> | null | undefined => {
  if (value === undefined) {
    return undefined
  }
  if (!value.trim()) {
    return null
  }
  return JSON.parse(value)
}

const stringifyJson = (value?: Record<string, unknown> | null) => {
  if (!value || Object.keys(value).length === 0) {
    return ''
  }
  return JSON.stringify(value, null, 2)
}

const isBlankJsonField = (value?: string) => !value || !value.trim()

const normalizeNode = (values: NodeFormValues, currentCount: number, fallback?: ScenarioNode): ScenarioNode => ({
  id: fallback?.id,
  node_key: values.node_key,
  node_name: values.node_name || values.node_key,
  node_type: values.node_type || 'api_call',
  ref_type: values.ref_type || 'api_definition',
  ref_id: values.ref_id,
  step_order: values.step_order || fallback?.step_order || currentCount + 1,
  depends_on: values.depends_on || [],
  input_mapping: safeJsonParse(values.input_mapping) || {},
  extract_rules: safeJsonParse(values.extract_rules) || null,
  assertion_overrides: safeJsonParse(values.assertion_overrides) || null,
  timeout_seconds: values.timeout_seconds ?? null,
  retry_count: values.retry_count ?? 0,
  continue_on_failure: values.continue_on_failure ?? false,
  is_enabled: values.is_enabled ?? true,
  extra_config: safeJsonParse(values.extra_config) || null,
})

const ScenarioDesigner: React.FC = () => {
  const navigate = useNavigate()
  const { scenarioId } = useParams()
  const { currentProject, currentVersion } = useProjectStore()
  const [form] = Form.useForm()
  const [nodeForm] = Form.useForm<NodeFormValues>()
  const [nodes, setNodes] = useState<ScenarioNode[]>([])
  const [apiDefinitions, setApiDefinitions] = useState<ApiDefinitionOption[]>([])
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [nodeModalVisible, setNodeModalVisible] = useState(false)
  const [editingNode, setEditingNode] = useState<ScenarioNode | null>(null)
  const nodeRefType = Form.useWatch('ref_type', nodeForm)

  useEffect(() => {
    if (!nodeModalVisible || nodeRefType !== 'api_definition') {
      return
    }

    const currentExtraConfig = nodeForm.getFieldValue('extra_config')
    if (isBlankJsonField(currentExtraConfig)) {
      nodeForm.setFieldValue('extra_config', DEFAULT_API_DEFINITION_EXTRA_CONFIG)
    }
  }, [nodeForm, nodeModalVisible, nodeRefType])

  useEffect(() => {
    void loadScenario()
  }, [scenarioId])

  useEffect(() => {
    void loadApiDefinitions()
    void loadEnvironments()
  }, [currentProject?.id])

  const sortedNodes = useMemo(
    () => [...nodes].sort((left, right) => left.step_order - right.step_order),
    [nodes],
  )

  const loadScenario = async () => {
    if (!scenarioId) {
      return
    }

    setLoading(true)
    try {
      const response = await api.get(`/scenarios/${scenarioId}`)
      if (response.code === 0) {
        const detail = response.data as ScenarioDetail
        setNodes(detail.nodes || [])
        form.setFieldsValue({
          name: detail.name,
          description: detail.description,
          scenario_type: detail.scenario_type,
          version_id: detail.version_id ?? currentVersion?.id ?? null,
          environment_id: detail.environment_id,
          execution_mode: detail.execution_mode,
          timeout_seconds: detail.timeout_seconds,
          retry_count: detail.retry_count,
          continue_on_failure: detail.continue_on_failure,
          status: detail.status,
          context_init: stringifyJson(detail.context_init),
        })
      }
    } catch (error: any) {
      message.error(error.message || '加载场景失败')
    } finally {
      setLoading(false)
    }
  }

  const loadApiDefinitions = async () => {
    if (!currentProject?.id) {
      setApiDefinitions([])
      return
    }

    try {
      const response = await api.get(`/api-definitions?project_id=${currentProject.id}`)
      if (response.code === 0) {
        setApiDefinitions(response.data.items || [])
      }
    } catch (error) {
      console.error('加载接口定义失败:', error)
    }
  }

  const loadEnvironments = async () => {
    if (!currentProject?.id) {
      setEnvironments([])
      return
    }

    try {
      const response = await api.get(`/environments?project_id=${currentProject.id}`)
      if (response.code === 0) {
        setEnvironments(response.data.environments || [])
      }
    } catch (error) {
      console.error('加载环境失败:', error)
    }
  }

  const handleSave = async () => {
    if (!scenarioId) {
      return
    }

    setSaving(true)
    try {
      const values = await form.validateFields()
      const response = await api.put(`/scenarios/${scenarioId}`, {
        name: values.name,
        description: values.description,
        scenario_type: values.scenario_type,
        version_id: values.version_id ?? null,
        environment_id: values.environment_id ?? null,
        context_init: safeJsonParse(values.context_init) || {},
        execution_mode: values.execution_mode,
        timeout_seconds: values.timeout_seconds,
        retry_count: values.retry_count,
        continue_on_failure: values.continue_on_failure,
        status: values.status,
        nodes: sortedNodes,
      })

      if (response.code === 0) {
        message.success('场景保存成功')
        await loadScenario()
      } else {
        message.error(response.message || '保存场景失败')
      }
    } catch (error: any) {
      if (error instanceof SyntaxError) {
        message.error('JSON 配置格式不正确')
      } else {
        message.error(error.message || '保存场景失败')
      }
    } finally {
      setSaving(false)
    }
  }

  const openNodeModal = (node?: ScenarioNode) => {
    setEditingNode(node || null)
    setNodeModalVisible(true)
    const defaultExtraConfig = !node || node.ref_type === 'api_definition'
      ? (stringifyJson(node?.extra_config as Record<string, unknown> | null) || DEFAULT_API_DEFINITION_EXTRA_CONFIG)
      : stringifyJson(node?.extra_config as Record<string, unknown> | null)
    nodeForm.setFieldsValue({
      node_key: node?.node_key,
      node_name: node?.node_name,
      node_type: node?.node_type || 'api_call',
      ref_type: node?.ref_type || 'api_definition',
      ref_id: node?.ref_id,
      step_order: node?.step_order,
      depends_on: node?.depends_on || [],
      input_mapping: stringifyJson(node?.input_mapping as Record<string, unknown> | null),
      extract_rules: stringifyJson(node?.extract_rules as Record<string, unknown> | null),
      assertion_overrides: stringifyJson(node?.assertion_overrides as Record<string, unknown> | null),
      timeout_seconds: node?.timeout_seconds ?? null,
      retry_count: node?.retry_count ?? 0,
      continue_on_failure: node?.continue_on_failure ?? false,
      is_enabled: node?.is_enabled ?? true,
      extra_config: defaultExtraConfig,
    })
  }

  const handleDeleteNode = (nodeKey: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除节点 "${nodeKey}" 吗？`,
      onOk: () => {
        setNodes((currentNodes) =>
          currentNodes
            .filter((item) => item.node_key !== nodeKey)
            .map((item, index) => ({ ...item, step_order: index + 1 })),
        )
        message.success('节点已删除')
      },
    })
  }

  const handleNodeModalOk = async () => {
    try {
      const values = await nodeForm.validateFields()
      const normalizedNode = normalizeNode(values, nodes.length, editingNode || undefined)

      setNodes((currentNodes) => {
        const nextNodes = editingNode
          ? currentNodes.map((item) => (item.node_key === editingNode.node_key ? normalizedNode : item))
          : [...currentNodes, normalizedNode]
        return nextNodes
          .sort((left, right) => left.step_order - right.step_order)
          .map((item, index) => ({ ...item, step_order: index + 1 }))
      })

      message.success(editingNode ? '节点已更新' : '节点已添加')
      setNodeModalVisible(false)
      nodeForm.resetFields()
    } catch (error: any) {
      if (error instanceof SyntaxError) {
        message.error('节点 JSON 配置格式不正确')
      } else {
        message.error(error.message || '节点保存失败')
      }
    }
  }

  return (
    <div className="scenario-designer">
      <Card
        title="场景编排"
        loading={loading}
        extra={
          <Space>
            <Button onClick={() => navigate(`/scenario/${scenarioId}`)}>返回</Button>
            <Button type="primary" onClick={() => void handleSave()} loading={saving}>保存场景</Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="场景名称" rules={[{ required: true, message: '请输入场景名称' }]}>
            <Input placeholder="请输入场景名称" />
          </Form.Item>
          <Form.Item name="description" label="场景描述">
            <TextArea placeholder="请输入场景描述" rows={3} />
          </Form.Item>
          <Space align="start" wrap style={{ display: 'flex' }}>
            <Form.Item name="scenario_type" label="场景类型" rules={[{ required: true, message: '请选择场景类型' }] }>
              <Select style={{ width: 180 }} options={[
                { label: 'business_flow', value: 'business_flow' },
                { label: 'regression', value: 'regression' },
                { label: 'smoke', value: 'smoke' },
              ]} />
            </Form.Item>
            <Form.Item name="version_id" label="版本 ID">
              <InputNumber min={1} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="environment_id" label="默认环境">
              <Select
                allowClear
                style={{ width: 240 }}
                options={environments.map((item) => ({ label: `${item.name} (${item.base_url})`, value: item.id }))}
              />
            </Form.Item>
            <Form.Item name="execution_mode" label="执行模式" rules={[{ required: true, message: '请选择执行模式' }] }>
              <Select style={{ width: 160 }} options={[{ label: 'sequential', value: 'sequential' }, { label: 'dag', value: 'dag' }]} />
            </Form.Item>
            <Form.Item name="status" label="状态" rules={[{ required: true, message: '请选择状态' }] }>
              <Select style={{ width: 140 }} options={[{ label: 'draft', value: 'draft' }, { label: 'active', value: 'active' }, { label: 'archived', value: 'archived' }]} />
            </Form.Item>
          </Space>
          <Space align="start" wrap style={{ display: 'flex' }}>
            <Form.Item name="timeout_seconds" label="超时（秒）">
              <InputNumber min={1} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="retry_count" label="重试次数">
              <InputNumber min={0} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="continue_on_failure" label="失败后继续" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item name="context_init" label="初始化上下文（JSON）">
            <TextArea rows={6} placeholder='例如：{"user_id": 1}' />
          </Form.Item>
        </Form>

        <div className="nodes-section">
          <div className="nodes-header">
            <h3>场景节点</h3>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => openNodeModal()}>
              添加节点
            </Button>
          </div>

          <div className="nodes-list">
            {sortedNodes.map((node) => {
              const definition = apiDefinitions.find((item) => item.id === node.ref_id)
              return (
                <Card key={node.node_key} size="small" className="node-card">
                  <div className="node-header">
                    <Space wrap>
                      <Tag color="blue">#{node.step_order}</Tag>
                      <strong>{node.node_name || node.node_key}</strong>
                      <Tag>{node.node_key}</Tag>
                      <Tag color={node.is_enabled ? 'success' : 'default'}>{node.is_enabled ? 'enabled' : 'disabled'}</Tag>
                    </Space>
                    <Space>
                      <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openNodeModal(node)}>
                        编辑
                      </Button>
                      <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteNode(node.node_key)}>
                        删除
                      </Button>
                    </Space>
                  </div>
                  <div className="node-details">
                    <div>类型: {node.node_type}</div>
                    <div>引用: {definition ? `${definition.method} ${definition.path}` : `${node.ref_type} #${node.ref_id}`}</div>
                    {node.depends_on.length > 0 && <div>依赖: {node.depends_on.join(', ')}</div>}
                    {node.input_mapping && Object.keys(node.input_mapping).length > 0 && (
                      <div>
                        输入映射: <Text type="secondary">{JSON.stringify(node.input_mapping)}</Text>
                      </div>
                    )}
                  </div>
                </Card>
              )
            })}
          </div>
        </div>

        <Modal
          title={editingNode ? '编辑节点' : '添加节点'}
          open={nodeModalVisible}
          onOk={() => void handleNodeModalOk()}
          onCancel={() => {
            setNodeModalVisible(false)
            nodeForm.resetFields()
          }}
          width={760}
        >
          <Form form={nodeForm} layout="vertical" initialValues={{ node_type: 'api_call', ref_type: 'api_definition', retry_count: 0, continue_on_failure: false, is_enabled: true }}>
            <Space align="start" wrap style={{ display: 'flex' }}>
              <Form.Item name="node_key" label="节点标识" rules={[{ required: true, message: '请输入节点标识' }]}>
                <Input placeholder="例如: create_user" disabled={Boolean(editingNode)} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item name="node_name" label="节点名称" rules={[{ required: true, message: '请输入节点名称' }]}>
                <Input placeholder="例如: 创建用户" style={{ width: 200 }} />
              </Form.Item>
              <Form.Item name="step_order" label="执行顺序">
                <InputNumber min={1} style={{ width: 120 }} />
              </Form.Item>
              <Form.Item name="is_enabled" label="启用" valuePropName="checked">
                <Checkbox />
              </Form.Item>
            </Space>

            <Space align="start" wrap style={{ display: 'flex' }}>
              <Form.Item name="node_type" label="节点类型" rules={[{ required: true, message: '请选择节点类型' }]}>
                <Select style={{ width: 160 }} options={[{ label: 'api_call', value: 'api_call' }]} />
              </Form.Item>
              <Form.Item name="ref_type" label="引用类型" rules={[{ required: true, message: '请选择引用类型' }]}>
                <Select style={{ width: 180 }} options={[{ label: 'api_definition', value: 'api_definition' }, { label: 'api_case', value: 'api_case' }]} />
              </Form.Item>
              <Form.Item name="ref_id" label="接口定义" rules={[{ required: true, message: '请选择接口定义' }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  style={{ width: 320 }}
                  options={apiDefinitions.map((definition) => ({
                    label: `${definition.method} ${definition.path}${definition.summary ? ` - ${definition.summary}` : ''}`,
                    value: definition.id,
                  }))}
                />
              </Form.Item>
            </Space>

            <Space align="start" wrap style={{ display: 'flex' }}>
              <Form.Item name="depends_on" label="依赖节点">
                <Select
                  mode="multiple"
                  allowClear
                  style={{ width: 320 }}
                  options={sortedNodes
                    .filter((node) => node.node_key !== editingNode?.node_key)
                    .map((node) => ({ label: `${node.node_name || node.node_key} (${node.node_key})`, value: node.node_key }))}
                />
              </Form.Item>
              <Form.Item name="timeout_seconds" label="超时（秒）">
                <InputNumber min={1} style={{ width: 140 }} />
              </Form.Item>
              <Form.Item name="retry_count" label="重试次数">
                <InputNumber min={0} style={{ width: 140 }} />
              </Form.Item>
              <Form.Item name="continue_on_failure" label="失败后继续" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Space>

            <Form.Item name="input_mapping" label="输入映射（JSON）">
              <TextArea rows={5} placeholder='例如：{"path_params": {"id": "{{vars.user_id}}"}}' />
            </Form.Item>
            <Form.Item name="extract_rules" label="提取规则（JSON）">
              <TextArea rows={4} placeholder='例如：{"user_id": "$.data.id"}' />
            </Form.Item>
            <Form.Item name="assertion_overrides" label="断言覆盖（JSON）">
              <TextArea rows={4} placeholder='例如：{"status_code": 200}' />
            </Form.Item>
            <Form.Item
              name="extra_config"
              label="额外配置（JSON）"
              extra='当引用类型为 api_definition 时，必须声明 case_selection。示例：{"case_selection":{"strategy":"case_id","case_id":123}} 或 {"case_selection":{"strategy":"first_active"}}'
            >
              <TextArea
                rows={4}
                placeholder='例如：{"case_selection":{"strategy":"case_id","case_id":123}}'
              />
            </Form.Item>
          </Form>
        </Modal>
      </Card>
    </div>
  )
}

export default ScenarioDesigner

