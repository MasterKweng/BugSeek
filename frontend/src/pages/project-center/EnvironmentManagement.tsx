import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  DeleteOutlined,
  EditOutlined,
  EnvironmentOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import { useAppPreferences } from '../../preferences/AppPreferencesProvider'
import { useProjectStore } from '../../store/project'
import {
  createEnvironment,
  deleteEnvironment,
  getProjectEnvironments,
  updateEnvironment,
  type Environment,
} from '../../services/environments'
import {
  createEnvironmentVariable,
  deleteEnvironmentVariable,
  getEnvironmentVariables,
  updateEnvironmentVariable,
  type Variable,
} from '../../services/variables'

const { TextArea } = Input
const { Text } = Typography

const jsonToString = (value: unknown) => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return '{}'
  }
}

const parseJsonObject = (text: string, fallback: Record<string, any> = {}) => {
  if (!text.trim()) {
    return fallback
  }

  const parsed = JSON.parse(text)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('JSON must be an object')
  }

  return parsed
}

const tmKey = 'environmentManagement'

const EnvironmentManagement = () => {
  const { t } = useAppPreferences()
  const { currentProject } = useProjectStore()
  const projectId = currentProject?.id
  const tm = (key: string, fallback: string) => t(`${tmKey}.${key}`, fallback)

  const [activeTab, setActiveTab] = useState<'environments' | 'variables'>('environments')
  const [environmentLoading, setEnvironmentLoading] = useState(false)
  const [environmentList, setEnvironmentList] = useState<Environment[]>([])
  const [environmentModalOpen, setEnvironmentModalOpen] = useState(false)
  const [editingEnvironment, setEditingEnvironment] = useState<Environment | null>(null)
  const [environmentForm] = Form.useForm()

  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState<number | null>(null)
  const [variableLoading, setVariableLoading] = useState(false)
  const [variableList, setVariableList] = useState<Variable[]>([])
  const [variableModalOpen, setVariableModalOpen] = useState(false)
  const [editingVariable, setEditingVariable] = useState<Variable | null>(null)
  const [variableForm] = Form.useForm()

  const selectedEnvironment = useMemo(
    () => environmentList.find((item) => item.id === selectedEnvironmentId) || null,
    [environmentList, selectedEnvironmentId],
  )

  const loadEnvironments = async () => {
    if (!projectId) {
      setEnvironmentList([])
      setSelectedEnvironmentId(null)
      return
    }

    setEnvironmentLoading(true)
    try {
      const response = await getProjectEnvironments(projectId, 1, 100)
      const items = response.items || []
      setEnvironmentList(items)

      setSelectedEnvironmentId((current) => {
        if (current && items.some((item) => item.id === current)) {
          return current
        }

        const preferred = items.find((item) => item.is_default) || items[0] || null
        return preferred?.id ?? null
      })
    } catch (error: any) {
      message.error(error.message || tm('messages.loadEnvironmentsFailed', 'Failed to load environments'))
      setEnvironmentList([])
      setSelectedEnvironmentId(null)
    } finally {
      setEnvironmentLoading(false)
    }
  }

  const loadVariables = async (envId: number | null) => {
    if (!projectId || !envId) {
      setVariableList([])
      return
    }

    setVariableLoading(true)
    try {
      const response = await getEnvironmentVariables(projectId, envId, 1, 100)
      setVariableList(response.items || [])
    } catch (error: any) {
      message.error(error.message || tm('messages.loadVariablesFailed', 'Failed to load variables'))
      setVariableList([])
    } finally {
      setVariableLoading(false)
    }
  }

  useEffect(() => {
    void loadEnvironments()
  }, [projectId])

  useEffect(() => {
    void loadVariables(selectedEnvironmentId)
  }, [projectId, selectedEnvironmentId])

  const openCreateEnvironment = () => {
    setEditingEnvironment(null)
    environmentForm.setFieldsValue({
      name: '',
      base_url: '',
      is_default: false,
      headers_json: '{}',
      variables_json: '{}',
    })
    setEnvironmentModalOpen(true)
  }

  const openEditEnvironment = (env: Environment) => {
    setEditingEnvironment(env)
    environmentForm.setFieldsValue({
      name: env.name,
      base_url: env.base_url,
      is_default: !!env.is_default,
      headers_json: jsonToString(env.headers || {}),
      variables_json: jsonToString(env.variables || {}),
    })
    setEnvironmentModalOpen(true)
  }

  const saveEnvironment = async () => {
    if (!projectId) {
      return
    }

    try {
      const values = await environmentForm.validateFields()
      const payload = {
        name: values.name,
        base_url: values.base_url,
        is_default: !!values.is_default,
        headers: parseJsonObject(values.headers_json),
        variables: parseJsonObject(values.variables_json),
      }

      if (editingEnvironment) {
        await updateEnvironment(projectId, editingEnvironment.id, payload)
        message.success(tm('messages.environmentUpdated', 'Environment updated'))
      } else {
        await createEnvironment(projectId, payload)
        message.success(tm('messages.environmentCreated', 'Environment created'))
      }

      setEnvironmentModalOpen(false)
      setEditingEnvironment(null)
      environmentForm.resetFields()
      await loadEnvironments()
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }
      message.error(error.message || tm('messages.saveEnvironmentFailed', 'Failed to save environment'))
    }
  }

  const removeEnvironment = async (env: Environment) => {
    if (!projectId) {
      return
    }

    try {
      await deleteEnvironment(projectId, env.id)
      message.success(tm('messages.environmentDeleted', 'Environment deleted'))
      await loadEnvironments()
    } catch (error: any) {
      message.error(error.message || tm('messages.deleteEnvironmentFailed', 'Failed to delete environment'))
    }
  }

  const openCreateVariable = () => {
    if (!selectedEnvironmentId) {
      message.warning(tm('messages.selectEnvironmentFirst', 'Select an environment first'))
      return
    }

    setEditingVariable(null)
    variableForm.setFieldsValue({
      var_key: '',
      var_value: '',
      is_sensitive: false,
    })
    setVariableModalOpen(true)
  }

  const openEditVariable = (variable: Variable) => {
    setEditingVariable(variable)
    variableForm.setFieldsValue({
      var_key: variable.var_key,
      var_value: variable.is_sensitive ? '' : variable.var_value,
      is_sensitive: variable.is_sensitive,
    })
    setVariableModalOpen(true)
  }

  const saveVariable = async () => {
    if (!projectId || !selectedEnvironmentId) {
      return
    }

    try {
      const values = await variableForm.validateFields()
      const payload = {
        var_key: values.var_key,
        var_value: values.var_value,
        is_sensitive: !!values.is_sensitive,
      }

      if (editingVariable) {
        await updateEnvironmentVariable(projectId, selectedEnvironmentId, editingVariable.id, payload)
        message.success(tm('messages.variableUpdated', 'Variable updated'))
      } else {
        await createEnvironmentVariable(projectId, selectedEnvironmentId, payload)
        message.success(tm('messages.variableCreated', 'Variable created'))
      }

      setVariableModalOpen(false)
      setEditingVariable(null)
      variableForm.resetFields()
      await loadVariables(selectedEnvironmentId)
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }
      message.error(error.message || tm('messages.saveVariableFailed', 'Failed to save variable'))
    }
  }

  const removeVariable = async (variable: Variable) => {
    if (!projectId || !selectedEnvironmentId) {
      return
    }

    try {
      await deleteEnvironmentVariable(projectId, selectedEnvironmentId, variable.id)
      message.success(tm('messages.variableDeleted', 'Variable deleted'))
      await loadVariables(selectedEnvironmentId)
    } catch (error: any) {
      message.error(error.message || tm('messages.deleteVariableFailed', 'Failed to delete variable'))
    }
  }

  const environmentColumns: ColumnsType<Environment> = [
    {
      title: tm('columns.environment.name', 'Name'),
      dataIndex: 'name',
      width: 180,
    },
    {
      title: tm('columns.environment.baseUrl', 'Base URL'),
      dataIndex: 'base_url',
      ellipsis: true,
    },
    {
      title: tm('columns.environment.default', 'Default'),
      dataIndex: 'is_default',
      width: 110,
      render: (value: boolean) => (value ? <Tag color="gold">{tm('tags.default', 'Default')}</Tag> : <Tag>{tm('tags.normal', 'Normal')}</Tag>),
    },
    {
      title: tm('columns.environment.headers', 'Headers'),
      dataIndex: 'headers',
      width: 120,
      render: (value: Record<string, string> | undefined) => <Tag color="blue">{Object.keys(value || {}).length}</Tag>,
    },
    {
      title: tm('columns.environment.variables', 'Variables'),
      dataIndex: 'variables',
      width: 120,
      render: (value: Record<string, any> | undefined) => <Tag color="purple">{Object.keys(value || {}).length}</Tag>,
    },
    {
      title: tm('columns.actions', 'Actions'),
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space size="small" wrap>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditEnvironment(record)}>
            {tm('actions.edit', 'Edit')}
          </Button>
          <Button
            size="small"
            icon={<EnvironmentOutlined />}
            onClick={() => {
              setActiveTab('variables')
              setSelectedEnvironmentId(record.id)
            }}
          >
            {tm('actions.vars', 'Vars')}
          </Button>
          <Popconfirm
            title={tm('confirm.deleteEnvironmentTitle', 'Delete this environment?')}
            description={tm('confirm.deleteDescription', 'This action cannot be undone.')}
            okButtonProps={{ danger: true }}
            onConfirm={() => void removeEnvironment(record)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {tm('actions.delete', 'Delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const variableColumns: ColumnsType<Variable> = [
    {
      title: tm('columns.variable.key', 'Key'),
      dataIndex: 'var_key',
      width: 220,
    },
    {
      title: tm('columns.variable.value', 'Value'),
      dataIndex: 'var_value',
      ellipsis: true,
      render: (value: string, record) => (record.is_sensitive ? '******' : value),
    },
    {
      title: tm('columns.variable.sensitive', 'Sensitive'),
      dataIndex: 'is_sensitive',
      width: 120,
      render: (value: boolean) => (value ? <Tag color="red">{tm('tags.yes', 'Yes')}</Tag> : <Tag>{tm('tags.no', 'No')}</Tag>),
    },
    {
      title: tm('columns.actions', 'Actions'),
      key: 'actions',
      width: 180,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditVariable(record)}>
            {tm('actions.edit', 'Edit')}
          </Button>
          <Popconfirm
            title={tm('confirm.deleteVariableTitle', 'Delete this variable?')}
            description={tm('confirm.deleteDescription', 'This action cannot be undone.')}
            okButtonProps={{ danger: true }}
            onConfirm={() => void removeVariable(record)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {tm('actions.delete', 'Delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow={tm('hero.eyebrow', 'Project Center')}
        title={tm('hero.title', 'Environment & Variable Management')}
        description={tm('hero.description', 'Manage project environments and environment variables using only the real backend CRUD APIs.')}
        metrics={[
          { label: tm('metrics.environments', 'Environments'), value: environmentList.length },
          { label: tm('metrics.variables', 'Variables'), value: variableList.length },
          { label: tm('metrics.selectedEnv', 'Selected env'), value: selectedEnvironment?.name || '-' },
        ]}
        actions={
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => void loadEnvironments()} loading={environmentLoading}>
              {tm('actions.refresh', 'Refresh')}
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateEnvironment}>
              {tm('actions.newEnvironment', 'New environment')}
            </Button>
          </Space>
        }
      />

      {!projectId ? (
        <Alert type="warning" showIcon message={tm('messages.selectProjectFirst', 'Select a project first')} />
      ) : null}

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as 'environments' | 'variables')}
          items={[
            {
              key: 'environments',
              label: tm('tabs.environments', 'Environments'),
              children: (
                <Table
                  rowKey="id"
                  loading={environmentLoading}
                  dataSource={environmentList}
                  columns={environmentColumns}
                  pagination={false}
                  locale={{ emptyText: <Empty description={tm('empty.environments', 'No environments')} /> }}
                />
              ),
            },
            {
              key: 'variables',
              label: tm('tabs.variables', 'Variables'),
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size="large">
                  <Card size="small">
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Space wrap>
                        <Text strong>{tm('labels.environment', 'Environment')}</Text>
                        <Select
                          style={{ minWidth: 280 }}
                          value={selectedEnvironmentId ?? undefined}
                          onChange={(value) => setSelectedEnvironmentId(value)}
                          placeholder={tm('placeholders.selectEnvironment', 'Select environment')}
                          options={environmentList.map((item) => ({
                            value: item.id,
                            label: item.is_default ? `${item.name} (${tm('tags.defaultLower', 'default')})` : item.name,
                          }))}
                        />
                        <Button icon={<ReloadOutlined />} onClick={() => void loadVariables(selectedEnvironmentId)}>
                          {tm('actions.refreshVariables', 'Refresh variables')}
                        </Button>
                        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateVariable} disabled={!selectedEnvironmentId}>
                          {tm('actions.newVariable', 'New variable')}
                        </Button>
                      </Space>
                      {selectedEnvironment ? (
                        <Descriptions column={1} bordered size="small">
                          <Descriptions.Item label={tm('columns.environment.baseUrl', 'Base URL')}>{selectedEnvironment.base_url}</Descriptions.Item>
                          <Descriptions.Item label={tm('columns.environment.headers', 'Headers')}>{Object.keys(selectedEnvironment.headers || {}).length}</Descriptions.Item>
                          <Descriptions.Item label={tm('columns.environment.variables', 'Variables')}>{Object.keys(selectedEnvironment.variables || {}).length}</Descriptions.Item>
                        </Descriptions>
                      ) : (
                        <Empty description={tm('empty.selectEnvironmentToManageVariables', 'Select an environment to manage variables')} />
                      )}
                    </Space>
                  </Card>

                  <Table
                    rowKey="id"
                    loading={variableLoading}
                    dataSource={variableList}
                    columns={variableColumns}
                    pagination={false}
                    locale={{ emptyText: <Empty description={tm('empty.variables', 'No variables')} /> }}
                  />
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title={editingEnvironment ? tm('modals.editEnvironment', 'Edit environment') : tm('modals.newEnvironment', 'New environment')}
        open={environmentModalOpen}
        onCancel={() => {
          setEnvironmentModalOpen(false)
          setEditingEnvironment(null)
          environmentForm.resetFields()
        }}
        onOk={() => void saveEnvironment()}
        destroyOnClose
        width={760}
      >
        <Form form={environmentForm} layout="vertical" autoComplete="off">
          <Form.Item name="name" label={tm('columns.environment.name', 'Name')} rules={[{ required: true, message: tm('validation.enterName', 'Please enter a name') }]}>
            <Input placeholder="dev / test / staging / prod" />
          </Form.Item>
          <Form.Item name="base_url" label={tm('columns.environment.baseUrl', 'Base URL')} rules={[{ required: true, message: tm('validation.enterBaseUrl', 'Please enter a base URL') }]}>
            <Input placeholder="https://example.com" />
          </Form.Item>
          <Form.Item name="is_default" label={tm('labels.defaultEnvironment', 'Default environment')} valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="headers_json" label={tm('labels.headersJson', 'Headers JSON')} rules={[{ required: true, message: tm('validation.enterHeadersJson', 'Please enter headers JSON') }]}>
            <TextArea rows={5} spellCheck={false} />
          </Form.Item>
          <Form.Item name="variables_json" label={tm('labels.variablesJson', 'Variables JSON')} rules={[{ required: true, message: tm('validation.enterVariablesJson', 'Please enter variables JSON') }]}>
            <TextArea rows={5} spellCheck={false} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingVariable ? tm('modals.editVariable', 'Edit variable') : tm('modals.newVariable', 'New variable')}
        open={variableModalOpen}
        onCancel={() => {
          setVariableModalOpen(false)
          setEditingVariable(null)
          variableForm.resetFields()
        }}
        onOk={() => void saveVariable()}
        destroyOnClose
      >
        <Form form={variableForm} layout="vertical" autoComplete="off">
          <Form.Item name="var_key" label={tm('columns.variable.key', 'Key')} rules={[{ required: true, message: tm('validation.enterKey', 'Please enter a key') }]}>
            <Input placeholder="ACCESS_TOKEN" />
          </Form.Item>
          <Form.Item name="var_value" label={tm('columns.variable.value', 'Value')} rules={[{ required: true, message: tm('validation.enterValue', 'Please enter a value') }]}>
            <Input.Password placeholder="value" />
          </Form.Item>
          <Form.Item name="is_sensitive" label={tm('columns.variable.sensitive', 'Sensitive')} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default EnvironmentManagement
