import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Table, Button, Space, Tag, Modal, Form, Input, Select, InputNumber, message, Popconfirm, Drawer, Descriptions, Spin, Tabs, Empty, Switch } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, ReloadOutlined, MinusCircleOutlined, SafetyOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import * as projectService from '../services/project'
import type { Project, ProjectAssetConfig, ProjectCreate, ProjectUpdate } from '../types'
import { get, post, put, del } from '../services/request'
import WorkspaceModuleHero from '../components/WorkspaceModuleHero'
import { useProjectStore } from '../store/project'

const { TextArea } = Input
const { Option } = Select

const createDefaultProjectAssetConfig = (): ProjectAssetConfig => ({
  repository: {
    repo_url: '',
    default_branch: 'main',
    workspace_root: '',
    orm_framework: '',
  },
  dictionary: {
    enum_rules_text: '',
    business_terms_text: '',
  },
  risk_policy: {
    high_risk_fields_text: '',
    allow_ai_override: false,
    require_manual_review: true,
    auto_accept_min_confidence: 0.95,
  },
  field_mapping_defaults: {
    use_ai: true,
    use_sql_lineage: true,
    use_code_lineage: true,
    use_runtime_verification: true,
    evidence_mode: 'balanced',
  },
})

const normalizeProjectAssetConfig = (config?: ProjectAssetConfig | null): ProjectAssetConfig => {
  const defaults = createDefaultProjectAssetConfig()
  return {
    repository: {
      ...defaults.repository,
      ...(config?.repository || {}),
    },
    dictionary: {
      ...defaults.dictionary,
      ...(config?.dictionary || {}),
    },
    risk_policy: {
      ...defaults.risk_policy,
      ...(config?.risk_policy || {}),
    },
    field_mapping_defaults: {
      ...defaults.field_mapping_defaults,
      ...(config?.field_mapping_defaults || {}),
    },
  }
}

const Projects: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject: activeProject, setCurrentProject: setActiveProject } = useProjectStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false)
  const [currentProject, setCurrentProject] = useState<Project | null>(null)

  const [createForm] = Form.useForm<ProjectCreate>()
  const [editForm] = Form.useForm<ProjectUpdate>()
  const [createLoading, setCreateLoading] = useState(false)
  const [editLoading, setEditLoading] = useState(false)

  // 环境管理相关状态
  const [environments, setEnvironments] = useState<any[]>([])
  const [envLoading, setEnvLoading] = useState(false)
  const [addEnvModalVisible, setAddEnvModalVisible] = useState(false)
  const [editEnvModalVisible, setEditEnvModalVisible] = useState(false)
  const [currentEnv, setCurrentEnv] = useState<any>(null)
  const [addEnvForm] = Form.useForm()
  const [editEnvForm] = Form.useForm()
  const [addEnvLoading, setAddEnvLoading] = useState(false)
  const [editEnvLoading, setEditEnvLoading] = useState(false)

  // 鉴权配置相关状态（V2.0）
  

  const businessDomains = ['电商', '金融', 'SaaS', '社交']

  const renderAssetConfigFields = () => (
    <>
      <Form.Item name={['asset_config', 'repository', 'repo_url']} label="代码仓库地址">
        <Input placeholder="例如: https://git.example.com/team/service.git" />
      </Form.Item>
      <Form.Item name={['asset_config', 'repository', 'default_branch']} label="默认分支">
        <Input placeholder="例如: main" />
      </Form.Item>
      <Form.Item name={['asset_config', 'repository', 'workspace_root']} label="Workspace Root">
        <Input placeholder="例如: /workspace/backend-service" />
      </Form.Item>
      <Form.Item name={['asset_config', 'repository', 'orm_framework']} label="ORM / Mapper 类型">
        <Input placeholder="例如: MyBatis / JPA / SQLAlchemy" />
      </Form.Item>
      <Form.Item name={['asset_config', 'dictionary', 'business_terms_text']} label="业务术语字典">
        <TextArea rows={3} placeholder="填写关键业务对象、别名、表意词，帮助字段映射理解领域含义" />
      </Form.Item>
      <Form.Item name={['asset_config', 'dictionary', 'enum_rules_text']} label="枚举 / 状态字典">
        <TextArea rows={4} placeholder="填写 status/type/role/code 等字段的取值规则和含义" />
      </Form.Item>
      <Form.Item name={['asset_config', 'risk_policy', 'high_risk_fields_text']} label="高风险字段策略">
        <TextArea rows={4} placeholder="填写需要严格审核的字段，如 amount、status、role、user_id、deleted、time 等" />
      </Form.Item>
      <Form.Item name={['asset_config', 'risk_policy', 'auto_accept_min_confidence']} label="自动通过最低置信度">
        <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item name={['asset_config', 'risk_policy', 'allow_ai_override']} label="高风险字段允许 AI 覆盖" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item name={['asset_config', 'risk_policy', 'require_manual_review']} label="高风险字段默认人工复核" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item name={['asset_config', 'field_mapping_defaults', 'use_ai']} label="默认启用 AI" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item name={['asset_config', 'field_mapping_defaults', 'use_sql_lineage']} label="默认启用 SQL Lineage" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item name={['asset_config', 'field_mapping_defaults', 'use_code_lineage']} label="默认启用 Code Lineage" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item name={['asset_config', 'field_mapping_defaults', 'use_runtime_verification']} label="默认启用 Runtime Verification" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item name={['asset_config', 'field_mapping_defaults', 'evidence_mode']} label="默认证据模式">
        <Select>
          <Option value="balanced">balanced</Option>
          <Option value="conservative">conservative</Option>
          <Option value="aggressive">aggressive</Option>
        </Select>
      </Form.Item>
    </>
  )

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const response = await projectService.getProjects({ page, page_size: pageSize })
      setProjects(response.data.items || [])
      setTotal(response.data.total || 0)
    } catch (error: any) {
      message.error(error.message || '获取项目列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [page, pageSize])

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields()
      setCreateLoading(true)
      await projectService.createProject({
        ...values,
        asset_config: normalizeProjectAssetConfig(values.asset_config),
      })
      message.success('项目创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      fetchProjects()
    } catch (error: any) {
      if (error.errorFields) {
        message.warning('请填写完整信息')
      } else {
        message.error(error.message || '项目创建失败')
      }
    } finally {
      setCreateLoading(false)
    }
  }

  const handleEdit = async () => {
    if (!currentProject) return
    try {
      const values = await editForm.validateFields()
      setEditLoading(true)
      await projectService.updateProject(currentProject.id, {
        ...values,
        asset_config: normalizeProjectAssetConfig(values.asset_config),
      })
      message.success('项目更新成功')
      const refreshed = await projectService.getProject(currentProject.id)
      if (activeProject?.id === currentProject.id) {
        setActiveProject(refreshed.data)
      }
      setEditModalVisible(false)
      editForm.resetFields()
      setCurrentProject(null)
      fetchProjects()
    } catch (error: any) {
      if (error.errorFields) {
        message.warning('请填写完整信息')
      } else {
        message.error(error.message || '项目更新失败')
      }
    } finally {
      setEditLoading(false)
    }
  }

  const handleDelete = async (project: Project) => {
    try {
      await projectService.deleteProject(project.id)
      message.success('项目删除成功')
      fetchProjects()
    } catch (error: any) {
      message.error(error.message || '项目删除失败')
    }
  }

  const handleViewDetail = (project: Project) => {
    setCurrentProject(project)
    setDetailDrawerVisible(true)
  }

  const handleEditClick = (project: Project) => {
    setCurrentProject(project)
    editForm.setFieldsValue({
      ...project,
      description: project.description ?? undefined,
      logo_url: project.logo_url ?? undefined,
      backend_language: project.backend_language ?? undefined,
      backend_framework: project.backend_framework ?? undefined,
      database: project.database ?? undefined,
      frontend_framework: project.frontend_framework ?? undefined,
      asset_config: normalizeProjectAssetConfig(project.asset_config),
    })
    fetchEnvironments(project.id)
    setEditModalVisible(true)
  }
  
    // 获取环境列表
  
      const fetchEnvironments = async (projectId: number) => {
      
              setEnvLoading(true)
      
              try {
      
                const response = await get(`/projects/${projectId}/environments`, { page: 1, page_size: 100 })
      
                if (response && typeof response === 'object') {  
            // 检查是否有 items 字段（完整版接口）
  
            if ('items' in response && Array.isArray(response.items)) {
  
              setEnvironments(response.items)
  
            } 
  
            // 检查是否有 environments 字段（简化版接口）
  
            else if ('environments' in response && Array.isArray(response.environments)) {
  
              setEnvironments(response.environments)
  
            }
  
            // 如果有分页信息但没有 items 字段，设置空数组
            
                        else if ('total' in response && 'page' in response && 'page_size' in response) {
            
                          setEnvironments([])
            
                        } else {
            
                          setEnvironments([])
            
                        }
            
                      } else {
            
                        setEnvironments([])
            
                      }
            
                    } catch (error: any) {  
          message.error(error.message || '获取环境列表失败')
  
          setEnvironments([])
  
        } finally {
  
          setEnvLoading(false)
  
        }
  
      }    // 添加环境
    const handleAddEnv = async () => {
      if (!currentProject) return
      try {
        const values = await addEnvForm.validateFields()
        setAddEnvLoading(true)
        
        // 转换 headers 和 variables 数组为对象
        const payload = {
          ...values,
          headers: values.headers ? Object.fromEntries(values.headers.map((h: any) => [h.key, h.value])) : {},
          variables: values.variables ? Object.fromEntries(values.variables.map((v: any) => [v.key, v.value])) : {}
        }
        
        await post(`/projects/${currentProject.id}/environments`, payload)
        message.success('环境添加成功')
        setAddEnvModalVisible(false)
        addEnvForm.resetFields()
        fetchEnvironments(currentProject.id)
        // 刷新项目详情，更新环境数量
        const projectDetail = await projectService.getProject(currentProject.id)
        setCurrentProject(projectDetail.data)
      } catch (error: any) {
        if (error.errorFields) {
          message.warning('请填写完整信息')
        } else {
          message.error(error.message || '环境添加失败')
        }
      } finally {
        setAddEnvLoading(false)
      }
    }
  
    // 编辑环境
    const handleEditEnv = async () => {
      if (!currentProject || !currentEnv) return
      try {
        const values = await editEnvForm.validateFields()
        setEditEnvLoading(true)
        
        // 转换 headers 和 variables 数组为对象
        const payload = {
          ...values,
          headers: values.headers ? Object.fromEntries(values.headers.map((h: any) => [h.key, h.value])) : {},
          variables: values.variables ? Object.fromEntries(values.variables.map((v: any) => [v.key, v.value])) : {}
        }
        
        await put(`/projects/${currentProject.id}/environments/${currentEnv.id}`, payload)
        message.success('环境更新成功')
        setEditEnvModalVisible(false)
        editEnvForm.resetFields()
        setCurrentEnv(null)
        fetchEnvironments(currentProject.id)
      } catch (error: any) {
        if (error.errorFields) {
          message.warning('请填写完整信息')
        } else {
          message.error(error.message || '环境更新失败')
        }
      } finally {
        setEditEnvLoading(false)
      }
    }
  
    // 删除环境
    const handleDeleteEnv = async (envId: number) => {
      if (!currentProject) return
      try {
        await del(`/projects/${currentProject.id}/environments/${envId}`)
        message.success('环境删除成功')
        fetchEnvironments(currentProject.id)
        // 刷新项目详情，更新环境数量
        const projectDetail = await projectService.getProject(currentProject.id)
        setCurrentProject(projectDetail.data)
      } catch (error: any) {
        message.error(error.message || '环境删除失败')
      }
    }
  
    // 打开编辑环境弹窗
    const handleEditEnvClick = (env: any) => {
      setCurrentEnv(env)
      
      // 转换 headers 和 variables 对象为数组格式以便显示
      const formData = {
        ...env,
        headers: env.headers ? Object.entries(env.headers).map(([key, value]) => ({ key, value })) : [],
        variables: env.variables ? Object.entries(env.variables).map(([key, value]) => ({ key, value })) : []
      }
      
      editEnvForm.setFieldsValue(formData)
      setEditEnvModalVisible(true)
    }

  const columns: ColumnsType<Project> = [
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <span style={{ fontWeight: 500 }}>{text}</span>
    },
    {
      title: '业务领域',
      dataIndex: 'business_domain',
      key: 'business_domain',
      render: (domain: string) => <Tag color="blue">{domain}</Tag>
    },
    {
      title: '技术栈',
      key: 'tech_stack',
      render: (_, record) => (
        <Space size={4}>
          {record.backend_language && <Tag color="geekblue">{record.backend_language}</Tag>}
          {record.frontend_framework && <Tag color="green">{record.frontend_framework}</Tag>}
          {record.database && <Tag color="orange">{record.database}</Tag>}
        </Space>
      )
    },
    {
      title: '环境数',
      dataIndex: 'environments_count',
      key: 'environments_count',
      render: (count: number) => <Tag color="purple">{count} 个</Tag>
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString('zh-CN')
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            详情
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditClick(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            icon={<SafetyOutlined />}
            onClick={() => navigate(`/projects/${record.id}/auth-config`)}
          >
            鉴权配置
          </Button>
          <Popconfirm
            title="确认删除"
            description="确定要删除该项目吗？此操作不可恢复。"
            onConfirm={() => handleDelete(record)}
            okText="确定"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <div className="workspace-page workspace-list-page">
      <WorkspaceModuleHero
        eyebrow="Project Center"
        title="项目管理"
        description="管理项目基础信息、认证配置与环境资产。"
        metrics={[
          { label: '当前页项目数', value: projects.length },
          { label: '项目总数', value: total },
          { label: '分页', value: `${page}/${Math.max(1, Math.ceil((total || 1) / pageSize))}` },
        ]}
        actions={
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={fetchProjects} loading={loading}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
              创建项目
            </Button>
          </Space>
        }
      />
      <Card className="workspace-table-card workspace-list-page__card" bordered={false}>
        <Table
          columns={columns}
          dataSource={projects}
          loading={loading}
          rowKey="id"
          scroll={{ y: 'calc(100vh - 420px)' }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setPage(page)
              setPageSize(pageSize)
            }
          }}
        />
      </Card>

      {/* 创建项目弹窗 */}
      <Modal
        title="创建项目"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          createForm.resetFields()
        }}
        onOk={handleCreate}
        confirmLoading={createLoading}
        destroyOnClose
        width={600}
      >
        <Form
          form={createForm}
          layout="vertical"
          autoComplete="off"
          initialValues={{ asset_config: createDefaultProjectAssetConfig() }}
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item
            name="business_domain"
            label="业务领域"
            rules={[{ required: true, message: '请选择业务领域' }]}
          >
            <Select placeholder="请选择业务领域">
              {businessDomains.map(domain => (
                <Option key={domain} value={domain}>{domain}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="description"
            label="项目描述"
          >
            <TextArea rows={3} placeholder="请输入项目描述" />
          </Form.Item>
          <Form.Item name="backend_language" label="后端语言">
            <Input placeholder="例如: Python" />
          </Form.Item>
          <Form.Item name="backend_framework" label="后端框架">
            <Input placeholder="例如: FastAPI" />
          </Form.Item>
          <Form.Item name="database" label="数据库">
            <Input placeholder="例如: PostgreSQL" />
          </Form.Item>
          <Form.Item name="frontend_framework" label="前端框架">
            <Input placeholder="例如: React" />
          </Form.Item>
          {renderAssetConfigFields()}
        </Form>
      </Modal>

      {/* 编辑项目弹窗 */}
      <Modal
        title="编辑项目"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false)
          editForm.resetFields()
          setCurrentProject(null)
          setEnvironments([])
        }}
        footer={null}
        destroyOnClose
        width={800}
      >
        <Tabs defaultActiveKey="project" items={[
          {
            key: 'project',
            label: '项目信息',
            children: (
              <Form
                form={editForm}
                layout="vertical"
                autoComplete="off"
              >
                <Form.Item
                  name="name"
                  label="项目名称"
                  rules={[{ required: true, message: '请输入项目名称' }]}
                >
                  <Input placeholder="请输入项目名称" />
                </Form.Item>
                <Form.Item
                  name="business_domain"
                  label="业务领域"
                  rules={[{ required: true, message: '请选择业务领域' }]}
                >
                  <Select placeholder="请选择业务领域">
                    {businessDomains.map(domain => (
                      <Option key={domain} value={domain}>{domain}</Option>
                    ))}
                  </Select>
                </Form.Item>
                <Form.Item
                  name="description"
                  label="项目描述"
                >
                  <TextArea rows={3} placeholder="请输入项目描述" />
                </Form.Item>
                <Form.Item name="backend_language" label="后端语言">
                  <Input placeholder="例如: Python" />
                </Form.Item>
                <Form.Item name="backend_framework" label="后端框架">
                  <Input placeholder="例如: FastAPI" />
                </Form.Item>
                <Form.Item name="database" label="数据库">
                  <Input placeholder="例如: PostgreSQL" />
                </Form.Item>
                <Form.Item name="frontend_framework" label="前端框架">
                  <Input placeholder="例如: React" />
                </Form.Item>
                <div style={{ textAlign: 'right', marginTop: 16 }}>
                  <Button onClick={() => setEditModalVisible(false)}>取消</Button>
                  <Button type="primary" onClick={handleEdit} loading={editLoading}>
                    保存项目信息
                  </Button>
                </div>
              </Form>
            )
          },
          {
            key: 'mapping-assets',
            label: '字段映射资产',
            children: (
              <Form
                form={editForm}
                layout="vertical"
                autoComplete="off"
              >
                {renderAssetConfigFields()}
                <div style={{ textAlign: 'right', marginTop: 16 }}>
                  <Button onClick={() => setEditModalVisible(false)}>鍙栨秷</Button>
                  <Button type="primary" onClick={handleEdit} loading={editLoading}>
                    淇濆瓨字段映射资产
                  </Button>
                </div>
              </Form>
            )
          },
          {
            key: 'environments',
            label: '环境管理',
            children: (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => setAddEnvModalVisible(true)}
                  >
                    添加环境
                  </Button>
                </div>
                <Table
                  dataSource={environments}
                  loading={envLoading}
                  rowKey="id"
                  pagination={false}
                  size="small"
                  columns={[
                    {
                      title: '环境名称',
                      dataIndex: 'name',
                      key: 'name'
                    },
                    {
                      title: '基础URL',
                      dataIndex: 'base_url',
                      key: 'base_url',
                      ellipsis: true
                    },
                    {
                      title: '创建时间',
                      dataIndex: 'created_at',
                      key: 'created_at',
                      render: (date: string) => new Date(date).toLocaleString('zh-CN')
                    },
                    {
                      title: '操作',
                      key: 'action',
                      width: 200,
                      render: (_, record) => (
                        <Space size="small">
                          <Button
                            type="link"
                            size="small"
                            onClick={() => handleEditEnvClick(record)}
                          >
                            编辑
                          </Button>
                          <Button
                            type="link"
                            size="small"
                            icon={<SafetyOutlined />}
                            onClick={() => currentProject && navigate(`/projects/${currentProject.id}/auth-config?env=${record.id}`)}
                          >
                            鉴权配置
                          </Button>
                          <Popconfirm
                            title="确认删除"
                            description={`确定要删除环境 "${record.name}" 吗？`}
                            onConfirm={() => handleDeleteEnv(record.id)}
                            okText="确定"
                            cancelText="取消"
                            okButtonProps={{ danger: true }}
                          >
                            <Button
                              type="link"
                              size="small"
                              danger
                            >
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      )
                    }
                  ]}
                />
                {environments.length === 0 && (
                  <Empty description="暂无环境，请点击上方按钮添加" />
                )}
                <div style={{ textAlign: 'right', marginTop: 16 }}>
                  <Button onClick={() => setEditModalVisible(false)}>关闭</Button>
                </div>
              </div>
            )
          }
        ]} />
      </Modal>

      {/* 项目详情抽屉 */}
      <Drawer
        title="项目详情"
        open={detailDrawerVisible}
        onClose={() => {
          setDetailDrawerVisible(false)
          setCurrentProject(null)
        }}
        width={600}
      >
        {currentProject ? (
          <Spin spinning={false}>
            <Descriptions column={1} bordered>
              <Descriptions.Item label="项目名称">{currentProject.name}</Descriptions.Item>
              <Descriptions.Item label="业务领域">
                <Tag color="blue">{currentProject.business_domain}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="项目描述">{currentProject.description || '-'}</Descriptions.Item>
              <Descriptions.Item label="后端语言">{currentProject.backend_language || '-'}</Descriptions.Item>
              <Descriptions.Item label="后端框架">{currentProject.backend_framework || '-'}</Descriptions.Item>
              <Descriptions.Item label="数据库">{currentProject.database || '-'}</Descriptions.Item>
              <Descriptions.Item label="前端框架">{currentProject.frontend_framework || '-'}</Descriptions.Item>
              <Descriptions.Item label="代码仓库">{currentProject.asset_config?.repository?.repo_url || '-'}</Descriptions.Item>
              <Descriptions.Item label="默认分支">{currentProject.asset_config?.repository?.default_branch || '-'}</Descriptions.Item>
              <Descriptions.Item label="Workspace Root">{currentProject.asset_config?.repository?.workspace_root || '-'}</Descriptions.Item>
              <Descriptions.Item label="ORM / Mapper">{currentProject.asset_config?.repository?.orm_framework || '-'}</Descriptions.Item>
              <Descriptions.Item label="字段映射默认策略">
                <Space wrap>
                  <Tag color={currentProject.asset_config?.field_mapping_defaults?.use_ai ? 'green' : 'default'}>AI</Tag>
                  <Tag color={currentProject.asset_config?.field_mapping_defaults?.use_sql_lineage ? 'blue' : 'default'}>SQL Lineage</Tag>
                  <Tag color={currentProject.asset_config?.field_mapping_defaults?.use_code_lineage ? 'purple' : 'default'}>Code Lineage</Tag>
                  <Tag color={currentProject.asset_config?.field_mapping_defaults?.use_runtime_verification ? 'gold' : 'default'}>Runtime Verification</Tag>
                  <Tag>{currentProject.asset_config?.field_mapping_defaults?.evidence_mode || 'balanced'}</Tag>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="高风险字段策略">
                {currentProject.asset_config?.risk_policy?.high_risk_fields_text || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="业务术语字典">
                {currentProject.asset_config?.dictionary?.business_terms_text || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="枚举 / 状态字典">
                {currentProject.asset_config?.dictionary?.enum_rules_text || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(currentProject.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label="更新时间">
                {new Date(currentProject.updated_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label="环境列表">
                {currentProject.environments && currentProject.environments.length > 0 ? (
                  <Space direction="vertical" size="small">
                    {currentProject.environments.map((env: any) => (
                      <Tag key={env.id} color="green">
                        {env.name} - {env.base_url}
                      </Tag>
                    ))}
                    {currentProject.environments_count && currentProject.environments_count > 5 && (
                      <Tag color="default">等 {currentProject.environments_count} 个环境</Tag>
                    )}
                  </Space>
                ) : (
                  <span style={{ color: 'var(--text-tertiary)' }}>暂无环境</span>
                )}
              </Descriptions.Item>
            </Descriptions>
          </Spin>
        ) : null}
      </Drawer>

      {/* 添加环境弹窗 */}
      <Modal
        title="添加环境"
        open={addEnvModalVisible}
        onCancel={() => {
          setAddEnvModalVisible(false)
          addEnvForm.resetFields()
        }}
        onOk={handleAddEnv}
        confirmLoading={addEnvLoading}
        destroyOnClose
        width={800}
      >
        <Form form={addEnvForm} layout="vertical">
          <Form.Item
            name="name"
            label="环境名称"
            rules={[{ required: true, message: '请输入环境名称' }]}
          >
            <Input placeholder="例如: 开发环境" />
          </Form.Item>
          <Form.Item
            name="base_url"
            label="基础URL"
            rules={[{ required: true, message: '请输入基础URL' }]}
          >
            <Input placeholder="例如: http://dev.example.com" />
          </Form.Item>
          <Form.Item
            name="is_default"
            label="设为默认环境"
            valuePropName="checked"
            initialValue={false}
            tooltip="设置后，用例执行时默认选择此环境"
          >
            <Switch />
          </Form.Item>
          
          {/* V2.0 新增：全局 Header 配置 */}
          <Form.Item
            label="全局 Header 配置"
            tooltip="这些 Header 会自动添加到所有请求中"
          >
            <Form.List name="headers">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...restField }) => (
                    <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item
                        {...restField}
                        name={[name, 'key']}
                        rules={[{ required: true, message: '请输入 Header 名称' }]}
                        style={{ margin: 0 }}
                      >
                        <Input placeholder="Header 名称" style={{ width: 150 }} />
                      </Form.Item>
                      <Form.Item
                        {...restField}
                        name={[name, 'value']}
                        rules={[{ required: true, message: '请输入 Header 值' }]}
                        style={{ margin: 0 }}
                      >
                        <Input placeholder="Header 值" style={{ width: 250 }} />
                      </Form.Item>
                      <MinusCircleOutlined onClick={() => remove(name)} />
                    </Space>
                  ))}
                  <Form.Item>
                    <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                      添加 Header
                    </Button>
                  </Form.Item>
                </>
              )}
            </Form.List>
          </Form.Item>
          
          {/* V2.0 新增：环境变量配置 */}
          <Form.Item
            label="环境变量"
            tooltip="用于替换登录请求体模板中的变量，如鉴权账号密码"
          >
            <Form.List name="variables">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...restField }) => (
                    <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item
                        {...restField}
                        name={[name, 'key']}
                        rules={[{ required: true, message: '请输入变量名' }]}
                        style={{ margin: 0 }}
                      >
                        <Input placeholder="变量名（如 auth_user）" style={{ width: 180 }} />
                      </Form.Item>
                      <Form.Item
                        {...restField}
                        name={[name, 'value']}
                        rules={[{ required: true, message: '请输入变量值' }]}
                        style={{ margin: 0 }}
                      >
                        <Input.Password placeholder="变量值" style={{ width: 220 }} />
                      </Form.Item>
                      <MinusCircleOutlined onClick={() => remove(name)} />
                    </Space>
                  ))}
                  <Form.Item>
                    <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                      添加变量
                    </Button>
                  </Form.Item>
                </>
              )}
            </Form.List>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑环境弹窗 */}
      <Modal
        title="编辑环境"
        open={editEnvModalVisible}
        onCancel={() => {
          setEditEnvModalVisible(false)
          editEnvForm.resetFields()
          setCurrentEnv(null)
        }}
        onOk={handleEditEnv}
        confirmLoading={editEnvLoading}
        destroyOnClose
        width={800}
      >
        <Form form={editEnvForm} layout="vertical">
          <Form.Item
            name="name"
            label="环境名称"
            rules={[{ required: true, message: '请输入环境名称' }]}
          >
            <Input placeholder="例如: 开发环境" />
          </Form.Item>
          <Form.Item
            name="base_url"
            label="基础URL"
            rules={[{ required: true, message: '请输入基础URL' }]}
          >
            <Input placeholder="例如: http://dev.example.com" />
          </Form.Item>
          <Form.Item
            name="is_default"
            label="设为默认环境"
            valuePropName="checked"
            tooltip="设置后，用例执行时默认选择此环境"
          >
            <Switch />
          </Form.Item>
          
          {/* V2.0 新增：全局 Header 配置 */}
          <Form.Item
            label="全局 Header 配置"
            tooltip="这些 Header 会自动添加到所有请求中"
          >
            <Form.List name="headers">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...restField }) => (
                    <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item
                        {...restField}
                        name={[name, 'key']}
                        rules={[{ required: true, message: '请输入 Header 名称' }]}
                        style={{ margin: 0 }}
                      >
                        <Input placeholder="Header 名称" style={{ width: 150 }} />
                      </Form.Item>
                      <Form.Item
                        {...restField}
                        name={[name, 'value']}
                        rules={[{ required: true, message: '请输入 Header 值' }]}
                        style={{ margin: 0 }}
                      >
                        <Input placeholder="Header 值" style={{ width: 250 }} />
                      </Form.Item>
                      <MinusCircleOutlined onClick={() => remove(name)} />
                    </Space>
                  ))}
                  <Form.Item>
                    <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                      添加 Header
                    </Button>
                  </Form.Item>
                </>
              )}
            </Form.List>
          </Form.Item>
          
          {/* V2.0 新增：环境变量配置 */}
          <Form.Item
            label="环境变量"
            tooltip="用于替换登录请求体模板中的变量，如鉴权账号密码"
          >
            <Form.List name="variables">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...restField }) => (
                    <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item
                        {...restField}
                        name={[name, 'key']}
                        rules={[{ required: true, message: '请输入变量名' }]}
                        style={{ margin: 0 }}
                      >
                        <Input placeholder="变量名（如 auth_user）" style={{ width: 180 }} />
                      </Form.Item>
                      <Form.Item
                        {...restField}
                        name={[name, 'value']}
                        rules={[{ required: true, message: '请输入变量值' }]}
                        style={{ margin: 0 }}
                      >
                        <Input.Password placeholder="变量值" style={{ width: 220 }} />
                      </Form.Item>
                      <MinusCircleOutlined onClick={() => remove(name)} />
                    </Space>
                  ))}
                  <Form.Item>
                    <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                      添加变量
                    </Button>
                  </Form.Item>
                </>
              )}
            </Form.List>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default Projects
