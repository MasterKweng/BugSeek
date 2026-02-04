import React, { useState, useEffect } from 'react'
import { Card, Table, Button, Space, Tag, Modal, Form, Input, Select, message, Popconfirm, Drawer, Descriptions, Spin, Tabs, Empty, Switch } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, ReloadOutlined, MinusCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import * as projectService from '../services/project'
import type { Project, ProjectCreate, ProjectUpdate } from '../types'
import { get, post, put, del } from '../services/request'

const { TextArea } = Input
const { Option } = Select

const Projects: React.FC = () => {
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
  const [authConfig, setAuthConfig] = useState<any>(null)
  const [authConfigLoading, setAuthConfigLoading] = useState(false)
  const [authConfigForm] = Form.useForm()
  const [authConfigSaving, setAuthConfigSaving] = useState(false)

  const businessDomains = ['电商', '金融', 'SaaS', '社交']

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
      await projectService.createProject(values)
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
      await projectService.updateProject(currentProject.id, values)
      message.success('项目更新成功')
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
    editForm.setFieldsValue(project)
    fetchEnvironments(project.id)
    fetchAuthConfig(project.id)
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
    const handleDeleteEnv = async (envId: number, envName: string) => {
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

  // 鉴权配置相关函数（V2.0）
  const fetchAuthConfig = async (projectId: number) => {
    setAuthConfigLoading(true)
    try {
      const response = await get(`/projects/${projectId}/auth-config`)
      // 检查 response 是否存在且 data 不为 null
      if (response && response.data) {
        setAuthConfig(response.data)
        authConfigForm.setFieldsValue(response.data)
      } else {
        setAuthConfig(null)
        authConfigForm.resetFields()
      }
    } catch (error: any) {
      if (error.response?.status !== 404) {
        message.error(error.message || '获取鉴权配置失败')
      }
      setAuthConfig(null)
      authConfigForm.resetFields()
    } finally {
      setAuthConfigLoading(false)
    }
  }

  const handleSaveAuthConfig = async () => {
    if (!currentProject) return
    try {
      const values = await authConfigForm.validateFields()
      setAuthConfigSaving(true)
      await post(`/projects/${currentProject.id}/auth-config`, values)
      message.success('鉴权配置保存成功')
      fetchAuthConfig(currentProject.id)
    } catch (error: any) {
      if (error.errorFields) {
        message.warning('请填写完整信息')
      } else {
        message.error(error.message || '鉴权配置保存失败')
      }
    } finally {
      setAuthConfigSaving(false)
    }
  }

  const handleDeleteAuthConfig = async () => {
    if (!currentProject) return
    try {
      await del(`/projects/${currentProject.id}/auth-config`)
      message.success('鉴权配置删除成功')
      setAuthConfig(null)
      authConfigForm.resetFields()
    } catch (error: any) {
      message.error(error.message || '鉴权配置删除失败')
    }
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
    <div style={{ padding: '24px' }}>
      <Card
        title="项目管理"
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchProjects}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
            >
              创建项目
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={projects}
          loading={loading}
          rowKey="id"
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
                      width: 150,
                      render: (_, record) => (
                        <Space size="small">
                          <Button
                            type="link"
                            size="small"
                            onClick={() => handleEditEnvClick(record)}
                          >
                            编辑
                          </Button>
                          <Popconfirm
                            title="确认删除"
                            description={`确定要删除环境 "${record.name}" 吗？`}
                            onConfirm={() => handleDeleteEnv(record.id, record.name)}
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
          },
          {
            key: 'auth',
            label: '鉴权配置',
            children: (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <span style={{ color: '#666' }}>配置项目级别的自动鉴权策略，用例执行时会自动登录并注入 Token</span>
                </div>
                <Spin spinning={authConfigLoading}>
                  <Form
                    form={authConfigForm}
                    layout="vertical"
                    autoComplete="off"
                  >
                    <Form.Item
                      name="enabled"
                      label="启用鉴权"
                      valuePropName="checked"
                    >
                      <Switch />
                    </Form.Item>
                    <Form.Item
                      name="auth_type"
                      label="鉴权类型"
                      rules={[{ required: true }]}
                    >
                      <Select>
                        <Option value="bearer">Bearer Token</Option>
                        <Option value="api_key">API Key</Option>
                        <Option value="custom">自定义</Option>
                      </Select>
                    </Form.Item>
                    <Form.Item
                      name="login_url"
                      label="登录接口 URL"
                      rules={[{ required: true }]}
                    >
                      <Input placeholder="例如: https://api.example.com/login" />
                    </Form.Item>
                    <Form.Item
                      name="login_method"
                      label="登录请求方法"
                      rules={[{ required: true }]}
                    >
                      <Select>
                        <Option value="POST">POST</Option>
                        <Option value="GET">GET</Option>
                      </Select>
                    </Form.Item>
                    <Form.Item
                      name="login_body_template"
                      label="登录请求体模板（支持变量）"
                      tooltip="使用 {{变量名}} 引用环境变量，例如: {{auth_user}}, {{auth_password}}"
                    >
                      <Input.TextArea rows={4} placeholder='{"username": "{{auth_user}}", "password": "{{auth_password}}"}' />
                    </Form.Item>
                    <Form.Item
                      name="token_extract_expression"
                      label="Token 提取表达式"
                      tooltip="使用 JSONPath 提取 Token，例如: $.data.token"
                      rules={[{ required: true }]}
                    >
                      <Input placeholder="例如: $.data.token" />
                    </Form.Item>
                    <Form.Item
                      name="token_inject_header"
                      label="Token 注入 Header 名称"
                      rules={[{ required: true }]}
                    >
                      <Input placeholder="例如: Authorization" />
                    </Form.Item>
                    <Form.Item
                      name="token_inject_template"
                      label="Token 注入模板"
                      tooltip="使用 {token} 作为占位符"
                      rules={[{ required: true }]}
                    >
                      <Input placeholder="例如: Bearer {token}" />
                    </Form.Item>
                    <div style={{ textAlign: 'right', marginTop: 16 }}>
                      {authConfig && (
                        <Popconfirm
                          title="确认删除"
                          description="确定要删除鉴权配置吗？"
                          onConfirm={handleDeleteAuthConfig}
                          okText="确定"
                          cancelText="取消"
                          okButtonProps={{ danger: true }}
                        >
                          <Button danger style={{ marginRight: 8 }}>
                            删除配置
                          </Button>
                        </Popconfirm>
                      )}
                      <Button onClick={() => setEditModalVisible(false)}>关闭</Button>
                      <Button 
                        type="primary" 
                        onClick={handleSaveAuthConfig} 
                        loading={authConfigSaving}
                      >
                        保存配置
                      </Button>
                    </div>
                  </Form>
                </Spin>
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
                  <span style={{ color: '#999' }}>暂无环境</span>
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