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

const EnvironmentManagement = () => {
  const { currentProject } = useProjectStore()
  const projectId = currentProject?.id

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
      message.error(error.message || 'Failed to load environments')
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
      const response = await getEnvironmentVariables(projectId, envId, 1, 200)
      setVariableList(response.items || [])
    } catch (error: any) {
      message.error(error.message || 'Failed to load variables')
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
        message.success('Environment updated')
      } else {
        await createEnvironment(projectId, payload)
        message.success('Environment created')
      }

      setEnvironmentModalOpen(false)
      setEditingEnvironment(null)
      environmentForm.resetFields()
      await loadEnvironments()
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }
      message.error(error.message || 'Failed to save environment')
    }
  }

  const removeEnvironment = async (env: Environment) => {
    if (!projectId) {
      return
    }

    try {
      await deleteEnvironment(projectId, env.id)
      message.success('Environment deleted')
      await loadEnvironments()
    } catch (error: any) {
      message.error(error.message || 'Failed to delete environment')
    }
  }

  const openCreateVariable = () => {
    if (!selectedEnvironmentId) {
      message.warning('Select an environment first')
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
        message.success('Variable updated')
      } else {
        await createEnvironmentVariable(projectId, selectedEnvironmentId, payload)
        message.success('Variable created')
      }

      setVariableModalOpen(false)
      setEditingVariable(null)
      variableForm.resetFields()
      await loadVariables(selectedEnvironmentId)
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }
      message.error(error.message || 'Failed to save variable')
    }
  }

  const removeVariable = async (variable: Variable) => {
    if (!projectId || !selectedEnvironmentId) {
      return
    }

    try {
      await deleteEnvironmentVariable(projectId, selectedEnvironmentId, variable.id)
      message.success('Variable deleted')
      await loadVariables(selectedEnvironmentId)
    } catch (error: any) {
      message.error(error.message || 'Failed to delete variable')
    }
  }

  const environmentColumns: ColumnsType<Environment> = [
    {
      title: 'Name',
      dataIndex: 'name',
      width: 180,
    },
    {
      title: 'Base URL',
      dataIndex: 'base_url',
      ellipsis: true,
    },
    {
      title: 'Default',
      dataIndex: 'is_default',
      width: 110,
      render: (value: boolean) => (value ? <Tag color="gold">Default</Tag> : <Tag>Normal</Tag>),
    },
    {
      title: 'Headers',
      dataIndex: 'headers',
      width: 120,
      render: (value: Record<string, string> | undefined) => <Tag color="blue">{Object.keys(value || {}).length}</Tag>,
    },
    {
      title: 'Variables',
      dataIndex: 'variables',
      width: 120,
      render: (value: Record<string, any> | undefined) => <Tag color="purple">{Object.keys(value || {}).length}</Tag>,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space size="small" wrap>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditEnvironment(record)}>
            Edit
          </Button>
          <Button
            size="small"
            icon={<EnvironmentOutlined />}
            onClick={() => {
              setActiveTab('variables')
              setSelectedEnvironmentId(record.id)
            }}
          >
            Vars
          </Button>
          <Popconfirm
            title="Delete this environment?"
            description="This action cannot be undone."
            okButtonProps={{ danger: true }}
            onConfirm={() => void removeEnvironment(record)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const variableColumns: ColumnsType<Variable> = [
    {
      title: 'Key',
      dataIndex: 'var_key',
      width: 220,
    },
    {
      title: 'Value',
      dataIndex: 'var_value',
      ellipsis: true,
      render: (value: string, record) => (record.is_sensitive ? '******' : value),
    },
    {
      title: 'Sensitive',
      dataIndex: 'is_sensitive',
      width: 120,
      render: (value: boolean) => (value ? <Tag color="red">Yes</Tag> : <Tag>No</Tag>),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditVariable(record)}>
            Edit
          </Button>
          <Popconfirm
            title="Delete this variable?"
            description="This action cannot be undone."
            okButtonProps={{ danger: true }}
            onConfirm={() => void removeVariable(record)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow="Project Center"
        title="Environment & Variable Management"
        description="Manage project environments and environment variables using only the real backend CRUD APIs."
        metrics={[
          { label: 'Environments', value: environmentList.length },
          { label: 'Variables', value: variableList.length },
          { label: 'Selected env', value: selectedEnvironment?.name || '-' },
        ]}
        actions={
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => void loadEnvironments()} loading={environmentLoading}>
              Refresh
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateEnvironment}>
              New environment
            </Button>
          </Space>
        }
      />

      {!projectId ? (
        <Alert type="warning" showIcon message="Select a project first" />
      ) : null}

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as 'environments' | 'variables')}
          items={[
            {
              key: 'environments',
              label: 'Environments',
              children: (
                <Table
                  rowKey="id"
                  loading={environmentLoading}
                  dataSource={environmentList}
                  columns={environmentColumns}
                  pagination={false}
                  locale={{ emptyText: <Empty description="No environments" /> }}
                />
              ),
            },
            {
              key: 'variables',
              label: 'Variables',
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size="large">
                  <Card size="small">
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Space wrap>
                        <Text strong>Environment</Text>
                        <Select
                          style={{ minWidth: 280 }}
                          value={selectedEnvironmentId ?? undefined}
                          onChange={(value) => setSelectedEnvironmentId(value)}
                          placeholder="Select environment"
                          options={environmentList.map((item) => ({
                            value: item.id,
                            label: item.is_default ? `${item.name} (default)` : item.name,
                          }))}
                        />
                        <Button icon={<ReloadOutlined />} onClick={() => void loadVariables(selectedEnvironmentId)}>
                          Refresh variables
                        </Button>
                        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateVariable} disabled={!selectedEnvironmentId}>
                          New variable
                        </Button>
                      </Space>
                      {selectedEnvironment ? (
                        <Descriptions column={1} bordered size="small">
                          <Descriptions.Item label="Base URL">{selectedEnvironment.base_url}</Descriptions.Item>
                          <Descriptions.Item label="Headers">{Object.keys(selectedEnvironment.headers || {}).length}</Descriptions.Item>
                          <Descriptions.Item label="Variables">{Object.keys(selectedEnvironment.variables || {}).length}</Descriptions.Item>
                        </Descriptions>
                      ) : (
                        <Empty description="Select an environment to manage variables" />
                      )}
                    </Space>
                  </Card>

                  <Table
                    rowKey="id"
                    loading={variableLoading}
                    dataSource={variableList}
                    columns={variableColumns}
                    pagination={false}
                    locale={{ emptyText: <Empty description="No variables" /> }}
                  />
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title={editingEnvironment ? 'Edit environment' : 'New environment'}
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
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Please enter a name' }]}>
            <Input placeholder="dev / test / staging / prod" />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL" rules={[{ required: true, message: 'Please enter a base URL' }]}>
            <Input placeholder="https://example.com" />
          </Form.Item>
          <Form.Item name="is_default" label="Default environment" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="headers_json" label="Headers JSON" rules={[{ required: true, message: 'Please enter headers JSON' }]}>
            <TextArea rows={5} spellCheck={false} />
          </Form.Item>
          <Form.Item name="variables_json" label="Variables JSON" rules={[{ required: true, message: 'Please enter variables JSON' }]}>
            <TextArea rows={5} spellCheck={false} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingVariable ? 'Edit variable' : 'New variable'}
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
          <Form.Item name="var_key" label="Key" rules={[{ required: true, message: 'Please enter a key' }]}>
            <Input placeholder="ACCESS_TOKEN" />
          </Form.Item>
          <Form.Item name="var_value" label="Value" rules={[{ required: true, message: 'Please enter a value' }]}>
            <Input.Password placeholder="value" />
          </Form.Item>
          <Form.Item name="is_sensitive" label="Sensitive" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default EnvironmentManagement
