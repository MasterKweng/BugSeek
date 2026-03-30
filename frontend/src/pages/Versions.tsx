import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  message,
} from 'antd'
import {
  ArrowLeftOutlined,
  CopyOutlined,
  EditOutlined,
  LockOutlined,
  PlusOutlined,
  ProjectOutlined,
  UnlockOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import * as projectService from '../services/project'
import * as versionService from '../services/version'
import { getDbSchemas } from '../services/dbSchema'
import { getExecutions } from '../services/executions'
import { useProjectStore } from '../store/project'
import type { ExecutionSummary } from '../types/execution'
import type {
  DbSchemaSummary,
  Project,
  Version,
  VersionCreate,
  VersionMappingConfig,
  VersionUpdate,
} from '../types'
import WorkspaceModuleHero from '../components/WorkspaceModuleHero'

const { TextArea } = Input
const { Option } = Select

const createDefaultVersionMappingConfig = (): VersionMappingConfig => ({
  schema_binding: {
    selected_schema_id: null,
  },
  runtime_binding: {
    selected_execution_ids: [],
    auto_build_sql_lineage: false,
  },
  field_mapping_overrides: {
    use_sql_lineage: true,
    use_code_lineage: true,
    use_runtime_verification: true,
    allow_ai: true,
    high_risk_manual_review: true,
    rule_overrides_text: '',
  },
})

const normalizeVersionMappingConfig = (config?: VersionMappingConfig | null): VersionMappingConfig => {
  const defaults = createDefaultVersionMappingConfig()
  return {
    schema_binding: {
      ...defaults.schema_binding,
      ...(config?.schema_binding || {}),
    },
    runtime_binding: {
      ...defaults.runtime_binding,
      ...(config?.runtime_binding || {}),
    },
    field_mapping_overrides: {
      ...defaults.field_mapping_overrides,
      ...(config?.field_mapping_overrides || {}),
    },
  }
}

const Versions: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { currentVersion: activeVersion, setCurrentVersion } = useProjectStore()

  const [project, setProject] = useState<Project | null>(null)
  const [versions, setVersions] = useState<Version[]>([])
  const [parentVersions, setParentVersions] = useState<Version[]>([])
  const [schemaOptions, setSchemaOptions] = useState<DbSchemaSummary[]>([])
  const [executionOptions, setExecutionOptions] = useState<ExecutionSummary[]>([])

  const [loading, setLoading] = useState(false)
  const [invalidProject, setInvalidProject] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [cloneModalVisible, setCloneModalVisible] = useState(false)
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false)

  const [currentVersion, setCurrentVersionLocal] = useState<Version | null>(null)
  const [createLoading, setCreateLoading] = useState(false)
  const [editLoading, setEditLoading] = useState(false)
  const [cloneLoading, setCloneLoading] = useState(false)

  const [createForm] = Form.useForm<VersionCreate>()
  const [editForm] = Form.useForm<VersionUpdate>()
  const [cloneForm] = Form.useForm<{ new_version_number: string }>()

  const versionStatuses = [
    { label: '规划中', value: 'planning', color: 'default' },
    { label: '开发中', value: 'developing', color: 'processing' },
    { label: '测试中', value: 'testing', color: 'warning' },
    { label: '已发布', value: 'released', color: 'success' },
    { label: '已锁定', value: 'locked', color: 'error' },
  ]

  const numericProjectId = Number(projectId)

  const fetchProject = async () => {
    if (!projectId || Number.isNaN(numericProjectId)) {
      setInvalidProject(true)
      return
    }
    try {
      const response = await projectService.getProject(numericProjectId)
      setProject(response.data)
      setInvalidProject(false)
    } catch (error: any) {
      setInvalidProject(true)
      message.error(error.message || '获取项目信息失败')
    }
  }

  const fetchVersions = async () => {
    if (!projectId || Number.isNaN(numericProjectId)) {
      setInvalidProject(true)
      return
    }
    setLoading(true)
    try {
      const response = await versionService.getVersions(numericProjectId, { page, page_size: pageSize })
      setVersions(response.data.items || [])
      setTotal(response.data.total || 0)
    } catch (error: any) {
      message.error(error.message || '获取版本列表失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchParentVersions = async () => {
    if (!projectId || Number.isNaN(numericProjectId)) return
    try {
      const response = await versionService.getVersions(numericProjectId, { page: 1, page_size: 100 })
      setParentVersions(response.data.items || [])
    } catch (error) {
      console.error('获取父版本列表失败', error)
    }
  }

  const fetchVersionAssets = async (versionId?: number) => {
    if (!projectId || Number.isNaN(numericProjectId)) return
    try {
      const [schemas, executions] = await Promise.all([
        getDbSchemas({
          project_id: numericProjectId,
          version_id: versionId,
        }),
        getExecutions({
          version_id: versionId,
          page: 1,
          page_size: 100,
        }),
      ])
      setSchemaOptions(schemas.data?.items || [])
      setExecutionOptions(executions.items || [])
    } catch (error) {
      console.error('获取版本资产失败', error)
      setSchemaOptions([])
      setExecutionOptions([])
    }
  }

  useEffect(() => {
    void fetchProject()
    void fetchVersions()
    void fetchParentVersions()
  }, [projectId, page, pageSize])

  const renderMappingFields = () => (
    <>
      <Form.Item name={['mapping_config', 'schema_binding', 'selected_schema_id']} label="绑定 Schema Snapshot">
        <Select allowClear placeholder="选择当前版本用于字段映射的 schema">
          {schemaOptions.map((schema) => (
            <Option key={schema.id} value={schema.id}>
              {schema.name}
            </Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item name={['mapping_config', 'runtime_binding', 'selected_execution_ids']} label="绑定 Execution / Trace">
        <Select mode="multiple" allowClear placeholder="选择可作为字段映射证据来源的执行记录">
          {executionOptions.map((execution) => (
            <Option key={execution.id} value={execution.id}>
              #{execution.id} {execution.title || execution.execution_type}
            </Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item
        name={['mapping_config', 'runtime_binding', 'auto_build_sql_lineage']}
        label="运行前自动构建 SQL Lineage"
        valuePropName="checked"
      >
        <Switch />
      </Form.Item>
      <Form.Item
        name={['mapping_config', 'field_mapping_overrides', 'use_sql_lineage']}
        label="默认启用 SQL Lineage"
        valuePropName="checked"
      >
        <Switch />
      </Form.Item>
      <Form.Item
        name={['mapping_config', 'field_mapping_overrides', 'use_code_lineage']}
        label="默认启用 Code Lineage"
        valuePropName="checked"
      >
        <Switch />
      </Form.Item>
      <Form.Item
        name={['mapping_config', 'field_mapping_overrides', 'use_runtime_verification']}
        label="默认启用 Runtime Verification"
        valuePropName="checked"
      >
        <Switch />
      </Form.Item>
      <Form.Item
        name={['mapping_config', 'field_mapping_overrides', 'allow_ai']}
        label="默认允许 AI 补强"
        valuePropName="checked"
      >
        <Switch />
      </Form.Item>
      <Form.Item
        name={['mapping_config', 'field_mapping_overrides', 'high_risk_manual_review']}
        label="高风险字段默认人工审核"
        valuePropName="checked"
      >
        <Switch />
      </Form.Item>
      <Form.Item name={['mapping_config', 'field_mapping_overrides', 'rule_overrides_text']} label="版本级规则覆盖">
        <TextArea rows={4} placeholder="填写版本特有的字段映射规则、排除项或注意事项" />
      </Form.Item>
    </>
  )

  const handleOpenCreateModal = async () => {
    await fetchParentVersions()
    await fetchVersionAssets()
    createForm.setFieldsValue({
      mapping_config: createDefaultVersionMappingConfig(),
    })
    setCreateModalVisible(true)
  }

  const handleCreate = async () => {
    if (!projectId || Number.isNaN(numericProjectId)) return
    try {
      const values = await createForm.validateFields()
      setCreateLoading(true)
      await versionService.createVersion(numericProjectId, {
        ...values,
        project_id: numericProjectId,
        mapping_config: normalizeVersionMappingConfig(values.mapping_config),
      })
      message.success('版本创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      await fetchVersions()
      await fetchParentVersions()
    } catch (error: any) {
      if (error.errorFields) {
        message.warning('请填写完整信息')
      } else {
        message.error(error.message || '版本创建失败')
      }
    } finally {
      setCreateLoading(false)
    }
  }

  const handleEditClick = async (version: Version) => {
    setCurrentVersionLocal(version)
    editForm.setFieldsValue({
      version_number: version.version_number,
      status: version.status,
      change_summary: version.change_summary ?? undefined,
      requirement_doc: version.requirement_doc ?? undefined,
      test_scope: version.test_scope ?? undefined,
      mapping_config: normalizeVersionMappingConfig(version.mapping_config),
    })
    await fetchVersionAssets(version.id)
    setEditModalVisible(true)
  }

  const handleEdit = async () => {
    if (!currentVersion || !projectId || Number.isNaN(numericProjectId)) return
    try {
      const values = await editForm.validateFields()
      setEditLoading(true)
      await versionService.updateVersion(numericProjectId, currentVersion.id, {
        ...values,
        mapping_config: normalizeVersionMappingConfig(values.mapping_config),
      })
      const refreshed = await versionService.getVersion(numericProjectId, currentVersion.id)
      if (activeVersion?.id === currentVersion.id) {
        setCurrentVersion(refreshed.data)
      }
      message.success('版本配置更新成功')
      setEditModalVisible(false)
      editForm.resetFields()
      setCurrentVersionLocal(null)
      await fetchVersions()
    } catch (error: any) {
      if (error.errorFields) {
        message.warning('请填写完整信息')
      } else {
        message.error(error.message || '版本配置更新失败')
      }
    } finally {
      setEditLoading(false)
    }
  }

  const handleCloneClick = (version: Version) => {
    setCurrentVersionLocal(version)
    setCloneModalVisible(true)
  }

  const handleClone = async () => {
    if (!currentVersion || !projectId || Number.isNaN(numericProjectId)) return
    try {
      const values = await cloneForm.validateFields()
      setCloneLoading(true)
      await versionService.cloneVersion(numericProjectId, currentVersion.id, values.new_version_number)
      message.success('版本克隆成功')
      setCloneModalVisible(false)
      cloneForm.resetFields()
      setCurrentVersionLocal(null)
      await fetchVersions()
      await fetchParentVersions()
    } catch (error: any) {
      if (error.errorFields) {
        message.warning('请输入新版本号')
      } else {
        message.error(error.message || '版本克隆失败')
      }
    } finally {
      setCloneLoading(false)
    }
  }

  const handleLock = async (version: Version) => {
    if (!projectId || Number.isNaN(numericProjectId)) return
    try {
      await versionService.lockVersion(numericProjectId, version.id)
      message.success('版本锁定成功')
      await fetchVersions()
    } catch (error: any) {
      message.error(error.message || '版本锁定失败')
    }
  }

  const handleUnlock = async (version: Version) => {
    if (!projectId || Number.isNaN(numericProjectId)) return
    try {
      await versionService.unlockVersion(numericProjectId, version.id)
      message.success('版本解锁成功')
      await fetchVersions()
    } catch (error: any) {
      message.error(error.message || '版本解锁失败')
    }
  }

  const handleDelete = async (version: Version) => {
    if (!projectId || Number.isNaN(numericProjectId)) return
    try {
      await versionService.deleteVersion(numericProjectId, version.id)
      message.success('版本删除成功')
      await fetchVersions()
    } catch (error: any) {
      message.error(error.message || '版本删除失败')
    }
  }

  const handleViewDetail = async (version: Version) => {
    setCurrentVersionLocal(version)
    await fetchVersionAssets(version.id)
    setDetailDrawerVisible(true)
  }

  const columns: ColumnsType<Version> = [
    {
      title: '版本号',
      dataIndex: 'version_number',
      key: 'version_number',
      render: (text: string) => <span style={{ fontWeight: 500 }}>{text}</span>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusConfig = versionStatuses.find((item) => item.value === status)
        return statusConfig ? <Tag color={statusConfig.color}>{statusConfig.label}</Tag> : status
      },
    },
    {
      title: '父版本',
      dataIndex: 'parent_version_id',
      key: 'parent_version_id',
      render: (parentId: number | null) => {
        const parent = parentVersions.find((item) => item.id === parentId)
        return parent ? <Tag>{parent.version_number}</Tag> : '-'
      },
    },
    {
      title: '接口数',
      dataIndex: 'endpoints_count',
      key: 'endpoints_count',
    },
    {
      title: '用例数',
      dataIndex: 'test_cases_count',
      key: 'test_cases_count',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" onClick={() => void handleViewDetail(record)}>
            详情
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => void handleEditClick(record)}>
            编辑
          </Button>
          {record.status !== 'locked' ? (
            <>
              <Button type="link" size="small" icon={<LockOutlined />} onClick={() => void handleLock(record)}>
                锁定
              </Button>
              <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => handleCloneClick(record)}>
                克隆
              </Button>
              <Popconfirm
                title="确认删除"
                description="确定要删除该版本吗？此操作不可恢复。"
                onConfirm={() => void handleDelete(record)}
                okText="确定"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button type="link" size="small" danger>
                  删除
                </Button>
              </Popconfirm>
            </>
          ) : (
            <Button type="link" size="small" icon={<UnlockOutlined />} onClick={() => void handleUnlock(record)}>
              解锁
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div className="workspace-page workspace-list-page">
      {invalidProject ? (
        <Card>
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <ProjectOutlined style={{ fontSize: '64px', color: '#d9d9d9', marginBottom: '24px' }} />
            <h2 style={{ marginBottom: '12px' }}>项目不存在</h2>
            <p style={{ color: 'var(--text-tertiary)', marginBottom: '24px' }}>
              您访问的项目 ID 无效或已被删除。
            </p>
            <Space>
              <Button onClick={() => window.history.back()}>返回上一页</Button>
              <Button type="primary" onClick={() => navigate('/projects')}>
                前往项目管理
              </Button>
            </Space>
          </div>
        </Card>
      ) : (
        <>
          <WorkspaceModuleHero
            eyebrow="Version Center"
            title={`版本管理 · ${project?.name || '-'}`}
            description="管理版本生命周期、字段映射资产绑定和版本级规则覆盖。"
            metrics={[
              { label: '当前页版本数', value: versions.length },
              { label: '版本总数', value: total },
              { label: '已锁定', value: versions.filter((item) => item.status === 'locked').length },
            ]}
          />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>版本管理 - {project?.name || ''}</h2>
            <Space>
              <Button icon={<ArrowLeftOutlined />} onClick={() => window.history.back()}>
                返回
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => void handleOpenCreateModal()}>
                新建版本
              </Button>
            </Space>
          </div>

          <Card className="workspace-table-card workspace-list-page__card" bordered={false}>
            <Table
              columns={columns}
              dataSource={versions}
              loading={loading}
              rowKey="id"
              scroll={{ y: 'calc(100vh - 470px)' }}
              pagination={{
                current: page,
                pageSize,
                total,
                showSizeChanger: true,
                showTotal: (count) => `共 ${count} 条`,
                onChange: (nextPage, nextPageSize) => {
                  setPage(nextPage)
                  setPageSize(nextPageSize)
                },
              }}
            />
          </Card>
        </>
      )}

      <Modal
        title="新建版本"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          createForm.resetFields()
        }}
        onOk={() => void handleCreate()}
        confirmLoading={createLoading}
        destroyOnClose
        width={680}
      >
        <Form
          form={createForm}
          layout="vertical"
          autoComplete="off"
          initialValues={{ mapping_config: createDefaultVersionMappingConfig() }}
        >
          <Form.Item name="version_number" label="版本号" rules={[{ required: true, message: '请输入版本号' }]}>
            <Input placeholder="例如: V1.2.0" />
          </Form.Item>
          <Form.Item name="parent_version_id" label="父版本">
            <Select allowClear placeholder="选择父版本（可选）">
              {parentVersions.map((item) => (
                <Option key={item.id} value={item.id}>
                  {item.version_number}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="change_summary" label="变更摘要">
            <TextArea rows={3} placeholder="填写本版本的主要变更" />
          </Form.Item>
          <Form.Item name="requirement_doc" label="需求文档">
            <TextArea rows={3} placeholder="填写版本需求说明或链接摘要" />
          </Form.Item>
          {renderMappingFields()}
        </Form>
      </Modal>

      <Modal
        title={`编辑版本 ${currentVersion?.version_number || ''}`}
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false)
          editForm.resetFields()
          setCurrentVersionLocal(null)
        }}
        onOk={() => void handleEdit()}
        confirmLoading={editLoading}
        destroyOnClose
        width={680}
      >
        <Form
          form={editForm}
          layout="vertical"
          autoComplete="off"
          initialValues={{ mapping_config: createDefaultVersionMappingConfig() }}
        >
          <Form.Item name="version_number" label="版本号" rules={[{ required: true, message: '请输入版本号' }]}>
            <Input placeholder="例如: V1.2.0" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select allowClear>
              {versionStatuses.map((item) => (
                <Option key={item.value} value={item.value}>
                  {item.label}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="change_summary" label="变更摘要">
            <TextArea rows={3} placeholder="填写本版本的主要变更" />
          </Form.Item>
          <Form.Item name="requirement_doc" label="需求文档">
            <TextArea rows={3} placeholder="填写版本需求说明或链接摘要" />
          </Form.Item>
          {renderMappingFields()}
        </Form>
      </Modal>

      <Modal
        title={`克隆版本 ${currentVersion?.version_number || ''}`}
        open={cloneModalVisible}
        onCancel={() => {
          setCloneModalVisible(false)
          cloneForm.resetFields()
          setCurrentVersionLocal(null)
        }}
        onOk={() => void handleClone()}
        confirmLoading={cloneLoading}
        destroyOnClose
      >
        <Form form={cloneForm} layout="vertical" autoComplete="off">
          <Form.Item name="new_version_number" label="新版本号" rules={[{ required: true, message: '请输入新版本号' }]}>
            <Input placeholder="例如: V1.3.0" />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title="版本详情"
        open={detailDrawerVisible}
        onClose={() => {
          setDetailDrawerVisible(false)
          setCurrentVersionLocal(null)
        }}
        width={680}
      >
        {currentVersion ? (
          <Spin spinning={false}>
            <Descriptions column={1} bordered>
              <Descriptions.Item label="版本号">{currentVersion.version_number}</Descriptions.Item>
              <Descriptions.Item label="状态">
                {(() => {
                  const statusConfig = versionStatuses.find((item) => item.value === currentVersion.status)
                  return statusConfig ? <Tag color={statusConfig.color}>{statusConfig.label}</Tag> : currentVersion.status
                })()}
              </Descriptions.Item>
              <Descriptions.Item label="父版本">
                {currentVersion.parent_version_id
                  ? parentVersions.find((item) => item.id === currentVersion.parent_version_id)?.version_number || '-'
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="变更摘要">{currentVersion.change_summary || '-'}</Descriptions.Item>
              <Descriptions.Item label="需求文档">{currentVersion.requirement_doc || '-'}</Descriptions.Item>
              <Descriptions.Item label="测试范围">
                {currentVersion.test_scope?.length ? (
                  <Space wrap>
                    {currentVersion.test_scope.map((tag) => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                  </Space>
                ) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="绑定 Schema Snapshot">
                {schemaOptions.find((item) => item.id === currentVersion.mapping_config?.schema_binding?.selected_schema_id)?.name
                  || currentVersion.mapping_config?.schema_binding?.selected_schema_id
                  || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="绑定 Execution / Trace">
                {(currentVersion.mapping_config?.runtime_binding?.selected_execution_ids || []).length ? (
                  <Space wrap>
                    {(currentVersion.mapping_config?.runtime_binding?.selected_execution_ids || []).map((executionId) => (
                      <Tag key={executionId}>#{executionId}</Tag>
                    ))}
                  </Space>
                ) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="运行前自动构建 SQL Lineage">
                {currentVersion.mapping_config?.runtime_binding?.auto_build_sql_lineage ? '是' : '否'}
              </Descriptions.Item>
              <Descriptions.Item label="字段映射覆盖策略">
                <Space wrap>
                  <Tag color={currentVersion.mapping_config?.field_mapping_overrides?.use_sql_lineage ? 'blue' : 'default'}>
                    SQL Lineage
                  </Tag>
                  <Tag color={currentVersion.mapping_config?.field_mapping_overrides?.use_code_lineage ? 'purple' : 'default'}>
                    Code Lineage
                  </Tag>
                  <Tag color={currentVersion.mapping_config?.field_mapping_overrides?.use_runtime_verification ? 'gold' : 'default'}>
                    Runtime Verification
                  </Tag>
                  <Tag color={currentVersion.mapping_config?.field_mapping_overrides?.allow_ai ? 'green' : 'default'}>
                    AI
                  </Tag>
                  <Tag color={currentVersion.mapping_config?.field_mapping_overrides?.high_risk_manual_review ? 'red' : 'default'}>
                    高风险人工审核
                  </Tag>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="版本级规则覆盖">
                {currentVersion.mapping_config?.field_mapping_overrides?.rule_overrides_text || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="接口数">{currentVersion.endpoints_count}</Descriptions.Item>
              <Descriptions.Item label="用例数">{currentVersion.test_cases_count}</Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(currentVersion.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label="更新时间">
                {new Date(currentVersion.updated_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
            </Descriptions>
          </Spin>
        ) : null}
      </Drawer>
    </div>
  )
}

export default Versions
