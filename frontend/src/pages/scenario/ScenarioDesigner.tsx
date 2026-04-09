import React, { useEffect, useMemo, useState } from 'react'
import { Button, Card, Form, Input, InputNumber, Modal, Select, Space, Switch, Tag, Typography, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import api from '../../services/api'
import './ScenarioDesigner.css'
import { useProjectStore } from '../../store/project'
import type {
  Environment,
  ScenarioDetail,
  ScenarioNode,
  ScenarioRevision,
  ScenarioRevisionGraph,
  ScenarioRevisionListItem,
  ScenarioValidationResult,
} from '../../types/scenario'
import {
  getScenario,
  getScenarioRevision,
  getScenarioRevisionGraph,
  getScenarioRevisions,
  lintScenarioRevisionDsl,
  publishScenario,
  updateScenario,
  validateScenario,
} from '../../services/scenario'
import ScenarioDesignerHeaderCard from '../../components/scenario/ScenarioDesignerHeaderCard'
import ScenarioNodeCard from '../../components/scenario/ScenarioNodeCard'
import ScenarioNodeEditorModal, { type NodeFormValues } from '../../components/scenario/ScenarioNodeEditorModal'
import ScenarioRevisionDrawer from '../../components/scenario/ScenarioRevisionDrawer'
import ScenarioGraphDrawer from '../../components/scenario/ScenarioGraphDrawer'

interface ApiDefinitionOption {
  id: number
  method: string
  path: string
  summary?: string
}

const DEFAULT_EXTRA = JSON.stringify({ case_selection: { strategy: 'first_active' } }, null, 2)
const NODE_TYPES = ['api_call', 'condition', 'wait', 'script']
const scenarioTypeOptions = [
  { label: '业务流程', value: 'business_flow' },
  { label: '回归测试', value: 'regression' },
  { label: '冒烟测试', value: 'smoke' },
]
const executionModeOptions = [
  { label: '顺序执行', value: 'sequential' },
  { label: '依赖图执行', value: 'dag' },
]
const lifecycleOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已校验', value: 'validated' },
  { label: '已发布', value: 'published' },
  { label: '已归档', value: 'archived' },
]
const refTypeLabelMap: Record<string, string> = {
  api_definition: '接口定义',
  api_case: '测试用例',
  internal: '内部节点',
}

const parseJson = (value?: string) => {
  if (value === undefined) {
    return undefined
  }
  return value.trim() ? JSON.parse(value) : null
}

const stringifyJson = (value?: Record<string, unknown> | null) =>
  !value || !Object.keys(value).length ? '' : JSON.stringify(value, null, 2)

const normalizeNode = (values: NodeFormValues, count: number, fallback?: ScenarioNode): ScenarioNode => {
  const isApi = (values.node_type || 'api_call') === 'api_call'
  return {
    id: fallback?.id,
    node_key: values.node_key,
    node_name: values.node_name || values.node_key,
    node_type: values.node_type || 'api_call',
    ref_type: isApi ? values.ref_type || 'api_definition' : 'internal',
    ref_id: isApi ? (values.ref_id ?? 0) : 0,
    step_order: values.step_order || fallback?.step_order || count + 1,
    depends_on: values.depends_on || [],
    input_mapping: parseJson(values.input_mapping) || {},
    extract_rules: parseJson(values.extract_rules) || null,
    assertion_overrides: parseJson(values.assertion_overrides) || null,
    timeout_seconds: values.timeout_seconds ?? null,
    retry_count: values.retry_count ?? 0,
    continue_on_failure: values.continue_on_failure ?? false,
    is_enabled: values.is_enabled ?? true,
    extra_config: parseJson(values.extra_config) || null,
  }
}

const ScenarioDesigner: React.FC = () => {
  const navigate = useNavigate()
  const { scenarioId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const { currentProject, currentVersion } = useProjectStore()
  const [form] = Form.useForm()
  const [nodeForm] = Form.useForm<NodeFormValues>()
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null)
  const [nodes, setNodes] = useState<ScenarioNode[]>([])
  const [apiDefinitions, setApiDefinitions] = useState<ApiDefinitionOption[]>([])
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [revisions, setRevisions] = useState<ScenarioRevisionListItem[]>([])
  const [selectedRevision, setSelectedRevision] = useState<ScenarioRevision | null>(null)
  const [revisionGraph, setRevisionGraph] = useState<ScenarioRevisionGraph | null>(null)
  const [validationResult, setValidationResult] = useState<ScenarioValidationResult | null>(null)
  const [lintResult, setLintResult] = useState<{ valid: boolean; errors: Array<Record<string, unknown>>; warnings: Array<Record<string, unknown>> } | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [validating, setValidating] = useState(false)
  const [linting, setLinting] = useState(false)
  const [nodeModalVisible, setNodeModalVisible] = useState(false)
  const [revisionDrawerVisible, setRevisionDrawerVisible] = useState(false)
  const [graphDrawerVisible, setGraphDrawerVisible] = useState(false)
  const [editingNode, setEditingNode] = useState<ScenarioNode | null>(null)
  const nodeType = Form.useWatch('node_type', nodeForm)
  const sortedNodes = useMemo(() => [...nodes].sort((a, b) => a.step_order - b.step_order), [nodes])

  const fillForm = (detail: ScenarioDetail) => {
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
      status: detail.lifecycle_status ?? detail.status,
      context_init: stringifyJson(detail.context_init),
    })
  }

  const loadScenario = async () => {
    if (!scenarioId) return
    setLoading(true)
    try {
      const detail = await getScenario(Number(scenarioId))
      setScenario(detail)
      setNodes(detail.nodes || [])
      fillForm(detail)
    } catch (error: any) {
      message.error(error.message || '加载场景失败')
    } finally {
      setLoading(false)
    }
  }

  const loadRevisions = async () => {
    if (!scenarioId) return
    try {
      const result = await getScenarioRevisions(Number(scenarioId))
      setRevisions(result.items || [])
    } catch {
      setRevisions([])
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
    } catch {
      setApiDefinitions([])
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
    } catch {
      setEnvironments([])
    }
  }

  const selectRevision = async (revisionId: number) => {
    try {
      const [revision, graph] = await Promise.all([
        getScenarioRevision(revisionId),
        getScenarioRevisionGraph(revisionId),
      ])
      setSelectedRevision(revision)
      setRevisionGraph(graph)
      setNodes(revision.snapshot?.nodes || [])
      const next = new URLSearchParams(searchParams)
      next.set('revisionId', String(revisionId))
      setSearchParams(next, { replace: true })
    } catch (error: any) {
      message.error(error.message || '加载版本快照失败')
    }
  }

  useEffect(() => {
    void loadScenario()
    void loadRevisions()
  }, [scenarioId])

  useEffect(() => {
    void loadApiDefinitions()
    void loadEnvironments()
  }, [currentProject?.id])

  useEffect(() => {
    if (!scenario || selectedRevision || !revisions.length) return
    const preferred = Number(
      searchParams.get('revisionId') ||
      scenario.draft_revision_id ||
      scenario.published_revision_id ||
      revisions[0]?.id,
    )
    if (preferred) {
      void selectRevision(preferred)
    }
  }, [scenario, revisions, selectedRevision, searchParams])

  const handleSave = async () => {
    if (!scenarioId) return
    setSaving(true)
    try {
      const values = await form.validateFields()
      await updateScenario(Number(scenarioId), {
        name: values.name,
        description: values.description,
        version_id: values.version_id ?? null,
        environment_id: values.environment_id ?? null,
        context_init: parseJson(values.context_init) || {},
        execution_mode: values.execution_mode,
        timeout_seconds: values.timeout_seconds,
        retry_count: values.retry_count,
        continue_on_failure: values.continue_on_failure,
        status: values.status,
        nodes: sortedNodes,
      })
      message.success('场景保存成功')
      setSelectedRevision(null)
      setRevisionGraph(null)
      setValidationResult(null)
      setLintResult(null)
      await loadScenario()
      await loadRevisions()
    } catch (error: any) {
      message.error(error.message || '保存场景失败')
    } finally {
      setSaving(false)
    }
  }

  const handleValidate = async () => {
    if (!scenarioId) return
    setValidating(true)
    try {
      const values = form.getFieldsValue()
      const result = await validateScenario(Number(scenarioId), {
        environment_id: values.environment_id ?? scenario?.environment_id,
      })
      setValidationResult(result)
      message[result.readiness_valid ? 'success' : 'warning'](
        result.readiness_valid ? '场景校验通过' : '结构通过，但执行准备未通过',
      )
    } catch (error: any) {
      message.error(error.message || '场景校验失败')
    } finally {
      setValidating(false)
    }
  }

  const handlePublish = async () => {
    if (!scenarioId) return
    setPublishing(true)
    try {
      const result = await publishScenario(Number(scenarioId), { publish_note: 'published from designer' })
      message.success(`已发布版本 #${result.revision_no}`)
      await loadScenario()
      await loadRevisions()
      if (result.revision_id) {
        await selectRevision(result.revision_id)
      }
    } catch (error: any) {
      message.error(error.message || '发布失败')
    } finally {
      setPublishing(false)
    }
  }

  const handleLint = async () => {
    const revisionId = selectedRevision?.id || scenario?.draft_revision_id || scenario?.published_revision_id
    if (!revisionId) {
      message.warning('当前没有可检查的版本快照')
      return
    }
    setLinting(true)
    try {
      const result = await lintScenarioRevisionDsl(revisionId, true)
      setLintResult({
        valid: result.valid,
        errors: result.errors || [],
        warnings: result.warnings || [],
      })
      message.success(result.valid ? '规则检查通过' : '规则检查发现问题')
    } catch (error: any) {
      message.error(error.message || '规则检查失败')
    } finally {
      setLinting(false)
    }
  }

  const openNodeModal = (node?: ScenarioNode) => {
    setEditingNode(node || null)
    setNodeModalVisible(true)
    nodeForm.setFieldsValue({
      node_key: node?.node_key,
      node_name: node?.node_name,
      node_type: node?.node_type || 'api_call',
      ref_type: node?.ref_type || 'api_definition',
      ref_id: node?.ref_id ?? undefined,
      step_order: node?.step_order,
      depends_on: node?.depends_on || [],
      input_mapping: stringifyJson(node?.input_mapping as Record<string, unknown> | null),
      extract_rules: stringifyJson(node?.extract_rules as Record<string, unknown> | null),
      assertion_overrides: stringifyJson(node?.assertion_overrides as Record<string, unknown> | null),
      timeout_seconds: node?.timeout_seconds ?? null,
      retry_count: node?.retry_count ?? 0,
      continue_on_failure: node?.continue_on_failure ?? false,
      is_enabled: node?.is_enabled ?? true,
      extra_config: stringifyJson(node?.extra_config as Record<string, unknown> | null) || DEFAULT_EXTRA,
    })
  }

  const handleDeleteNode = (nodeKey: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除节点 "${nodeKey}" 吗？`,
      onOk: () =>
        setNodes((items) =>
          items
            .filter((item) => item.node_key !== nodeKey)
            .map((item, index) => ({ ...item, step_order: index + 1 })),
        ),
    })
  }

  const handleNodeModalOk = async () => {
    try {
      const values = await nodeForm.validateFields()
      const nextNode = normalizeNode(values, nodes.length, editingNode || undefined)
      setNodes((items) => {
        const next = editingNode
          ? items.map((item) => (item.node_key === editingNode.node_key ? nextNode : item))
          : [...items, nextNode]
        return next
          .sort((a, b) => a.step_order - b.step_order)
          .map((item, index) => ({ ...item, step_order: index + 1 }))
      })
      setNodeModalVisible(false)
      nodeForm.resetFields()
      message.success(editingNode ? '节点已更新' : '节点已添加')
    } catch (error: any) {
      message.error(error.message || '节点保存失败')
    }
  }

  if (loading && !scenario) {
    return (
      <div style={{ padding: 24 }}>
        <Typography.Text>加载中...</Typography.Text>
      </div>
    )
  }

  if (!scenario) {
    return (
      <div style={{ padding: 24 }}>
        <Card>
          <Typography.Text>未找到场景</Typography.Text>
        </Card>
      </div>
    )
  }

  return (
    <div className="scenario-designer">
      <ScenarioDesignerHeaderCard
        scenario={scenario}
        selectedRevision={selectedRevision}
        validationResult={validationResult}
        lintResult={lintResult}
        validating={validating}
        linting={linting}
        publishing={publishing}
        saving={saving}
        hasRevisionGraph={Boolean(revisionGraph)}
        onOpenRevisions={() => setRevisionDrawerVisible(true)}
        onOpenGraph={() => setGraphDrawerVisible(true)}
        onValidate={() => void handleValidate()}
        onLint={() => void handleLint()}
        onPublish={() => void handlePublish()}
        onSave={() => void handleSave()}
        onBack={() => navigate(`/scenario/${scenarioId}`)}
      />

      <Card style={{ marginTop: 24 }}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="场景名称" rules={[{ required: true, message: '请输入场景名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="场景描述">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Space align="start" wrap style={{ display: 'flex' }}>
            <Form.Item name="scenario_type" label="场景类型" rules={[{ required: true, message: '请选择场景类型' }]}>
              <Select style={{ width: 180 }} options={scenarioTypeOptions} />
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
            <Form.Item name="execution_mode" label="执行模式">
              <Select style={{ width: 160 }} options={executionModeOptions} />
            </Form.Item>
            <Form.Item name="status" label="生命周期状态">
              <Select style={{ width: 160 }} options={lifecycleOptions} />
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
            <Input.TextArea rows={5} />
          </Form.Item>
        </Form>

        <div className="nodes-section">
          <div className="nodes-header">
            <h3>场景节点</h3>
            <Space>
              {selectedRevision ? <Tag color="blue">版本快照 #{selectedRevision.id}</Tag> : null}
              <Button type="primary" icon={<PlusOutlined />} onClick={() => openNodeModal()}>
                添加节点
              </Button>
            </Space>
          </div>
          <div className="nodes-list">
            {sortedNodes.map((node) => {
              const definition = apiDefinitions.find((item) => item.id === node.ref_id)
              const referenceLabel = node.node_type === 'api_call'
                ? (definition
                  ? `${definition.method} ${definition.path}`
                  : `${refTypeLabelMap[node.ref_type || 'api_definition'] || node.ref_type} #${node.ref_id}`)
                : '内部节点'

              return (
                <ScenarioNodeCard
                  key={node.node_key}
                  node={node}
                  referenceLabel={referenceLabel}
                  onEdit={openNodeModal}
                  onDelete={handleDeleteNode}
                />
              )
            })}
          </div>
        </div>
      </Card>

      <ScenarioNodeEditorModal
        open={nodeModalVisible}
        editingNode={editingNode}
        form={nodeForm}
        nodeType={nodeType}
        nodes={sortedNodes}
        apiDefinitions={apiDefinitions}
        defaultExtra={DEFAULT_EXTRA}
        nodeTypes={NODE_TYPES}
        onOk={() => void handleNodeModalOk()}
        onCancel={() => {
          setNodeModalVisible(false)
          nodeForm.resetFields()
        }}
      />

      <ScenarioRevisionDrawer
        open={revisionDrawerVisible}
        revisions={revisions}
        selectedRevision={selectedRevision}
        onClose={() => setRevisionDrawerVisible(false)}
        onSelectRevision={(revisionId) => void selectRevision(revisionId)}
      />

      <ScenarioGraphDrawer
        open={graphDrawerVisible}
        graph={revisionGraph}
        onClose={() => setGraphDrawerVisible(false)}
      />
    </div>
  )
}

export default ScenarioDesigner
