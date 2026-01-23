import React, { useState, useEffect } from 'react'
import { Card, Table, Button, Space, Tag, Modal, Form, Input, Select, message, Popconfirm, Drawer, Descriptions, Spin } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import * as projectService from '../services/project'
import type { Project, ProjectCreate, ProjectUpdate } from '../types'

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
    setEditModalVisible(true)
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
        }}
        onOk={handleEdit}
        confirmLoading={editLoading}
        destroyOnClose
        width={600}
      >
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
        </Form>
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
            </Descriptions>
          </Spin>
        ) : null}
      </Drawer>
    </div>
  )
}

export default Projects