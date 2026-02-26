import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Table, Button, Space, Tag, Modal, Form, Input, Select, message, Popconfirm, Drawer, Descriptions, Spin } from 'antd'
import { PlusOutlined, LockOutlined, UnlockOutlined, CopyOutlined, ArrowLeftOutlined, ProjectOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import * as versionService from '../services/version'
import * as projectService from '../services/project'
import type { Version, VersionCreate, VersionUpdate, Project } from '../types'

const { TextArea } = Input
const { Option } = Select

const Versions: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [versions, setVersions] = useState<Version[]>([])
  const [loading, setLoading] = useState(false)
  const [invalidProject, setInvalidProject] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [cloneModalVisible, setCloneModalVisible] = useState(false)
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false)
  const [currentVersion, setCurrentVersion] = useState<Version | null>(null)
  const [parentVersions, setParentVersions] = useState<Version[]>([])

  const [createForm] = Form.useForm<VersionCreate>()
  const [cloneForm] = Form.useForm<{ new_version_number: string }>()
  const [createLoading, setCreateLoading] = useState(false)
  const [cloneLoading, setCloneLoading] = useState(false)

  const versionStatuses = [
    { label: '规划中', value: 'planning', color: 'default' },
    { label: '开发中', value: 'developing', color: 'processing' },
    { label: '测试中', value: 'testing', color: 'warning' },
    { label: '已发布', value: 'released', color: 'success' },
    { label: '已锁定', value: 'locked', color: 'error' }
  ]

  const fetchProject = async () => {
    if (!projectId) {
      setInvalidProject(true)
      return
    }

    const numProjectId = Number(projectId)
    if (isNaN(numProjectId)) {
      setInvalidProject(true)
      message.error('无效的项目 ID')
      return
    }

    try {
      const response = await projectService.getProject(numProjectId)
      setProject(response.data)
      setInvalidProject(false)
    } catch (error: any) {
      console.error('获取项目信息失败:', error)
      setInvalidProject(true)
      if (error.response?.status === 404) {
        message.error('项目不存在')
      } else {
        message.error(error.message || '获取项目信息失败')
      }
    }
  }

  const fetchVersions = async () => {
    if (!projectId || invalidProject) return

    const numProjectId = Number(projectId)
    if (isNaN(numProjectId)) {
      message.error('无效的项目 ID')
      return
    }

    setLoading(true)
    try {
      const response = await versionService.getVersions(numProjectId, { page, page_size: pageSize })
      setVersions(response.data.items || [])
      setTotal(response.data.total || 0)
    } catch (error: any) {
      console.error('获取版本列表失败:', error)
      if (error.response?.status === 404) {
        message.error('项目不存在')
        setInvalidProject(true)
      } else {
        message.error(error.message || '获取版本列表失败')
      }
    } finally {
      setLoading(false)
    }
  }

  const fetchParentVersions = async () => {
    if (!projectId) return
    try {
      const response = await versionService.getVersions(Number(projectId), { page: 1, page_size: 100 })
      setParentVersions(response.data.items || [])
    } catch (error: any) {
      console.error('获取父版本列表失败:', error)
    }
  }

  useEffect(() => {
    fetchProject()
    fetchVersions()
  }, [projectId, page, pageSize])

  const handleCreate = async () => {
    if (!projectId) return
    try {
      const values = await createForm.validateFields()
      setCreateLoading(true)
      await versionService.createVersion(Number(projectId), {
        ...values,
        project_id: Number(projectId)
      })
      message.success('版本创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      fetchVersions()
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

  const handleClone = async () => {
    if (!currentVersion || !projectId) return
    try {
      const values = await cloneForm.validateFields()
      setCloneLoading(true)
      await versionService.cloneVersion(Number(projectId), currentVersion.id, values.new_version_number)
      message.success('版本克隆成功')
      setCloneModalVisible(false)
      cloneForm.resetFields()
      setCurrentVersion(null)
      fetchVersions()
    } catch (error: any) {
      if (error.errorFields) {
        message.warning('请填写新版本号')
      } else {
        message.error(error.message || '版本克隆失败')
      }
    } finally {
      setCloneLoading(false)
    }
  }

  const handleLock = async (version: Version) => {
    if (!projectId) return
    try {
      await versionService.lockVersion(Number(projectId), version.id)
      message.success('版本锁定成功')
      fetchVersions()
    } catch (error: any) {
      message.error(error.message || '版本锁定失败')
    }
  }

  const handleUnlock = async (version: Version) => {
    if (!projectId) return
    try {
      await versionService.unlockVersion(Number(projectId), version.id)
      message.success('版本解锁成功')
      fetchVersions()
    } catch (error: any) {
      message.error(error.message || '版本解锁失败')
    }
  }

  const handleDelete = async (version: Version) => {
    if (!projectId) return
    try {
      await versionService.deleteVersion(Number(projectId), version.id)
      message.success('版本删除成功')
      fetchVersions()
    } catch (error: any) {
      message.error(error.message || '版本删除失败')
    }
  }

  const handleViewDetail = (version: Version) => {
    setCurrentVersion(version)
    setDetailDrawerVisible(true)
  }

  const handleCloneClick = (version: Version) => {
    setCurrentVersion(version)
    setCloneModalVisible(true)
  }

  const handleOpenCreateModal = () => {
    fetchParentVersions()
    setCreateModalVisible(true)
  }

  const columns: ColumnsType<Version> = [
    {
      title: '版本号',
      dataIndex: 'version_number',
      key: 'version_number',
      render: (text: string) => <span style={{ fontWeight: 500 }}>{text}</span>
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusConfig = versionStatuses.find(s => s.value === status)
        return statusConfig ? <Tag color={statusConfig.color}>{statusConfig.label}</Tag> : status
      }
    },
    {
      title: '父版本',
      dataIndex: 'parent_version_id',
      key: 'parent_version_id',
      render: (parentId: number | null) => {
        const parent = parentVersions.find(v => v.id === parentId)
        return parent ? <Tag>{parent.version_number}</Tag> : '-'
      }
    },
    {
      title: '接口数',
      dataIndex: 'endpoints_count',
      key: 'endpoints_count',
      render: (count: number) => <span>{count}</span>
    },
    {
      title: '用例数',
      dataIndex: 'test_cases_count',
      key: 'test_cases_count',
      render: (count: number) => <span>{count}</span>
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
            onClick={() => handleViewDetail(record)}
          >
            详情
          </Button>
          {record.status !== 'locked' && (
            <>
              <Button
                type="link"
                size="small"
                icon={<LockOutlined />}
                onClick={() => handleLock(record)}
              >
                锁定
              </Button>
              <Button
                type="link"
                size="small"
                icon={<CopyOutlined />}
                onClick={() => handleCloneClick(record)}
              >
                克隆
              </Button>
              <Popconfirm
                title="确认删除"
                description="确定要删除该版本吗？此操作不可恢复。"
                onConfirm={() => handleDelete(record)}
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
            </>
          )}
          {record.status === 'locked' && (
            <Button
              type="link"
              size="small"
              icon={<UnlockOutlined />}
              onClick={() => handleUnlock(record)}
            >
              解锁
            </Button>
          )}
        </Space>
      )
    }
  ]

  return (
    <div style={{ padding: '24px' }}>
      {invalidProject ? (
        <Card>
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <ProjectOutlined style={{ fontSize: '64px', color: '#d9d9d9', marginBottom: '24px' }} />
            <h2 style={{ marginBottom: '12px' }}>项目不存在</h2>
            <p style={{ color: 'var(--text-tertiary)', marginBottom: '24px' }}>
              您访问的项目 ID 无效或已被删除
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
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>版本管理 - {project?.name || ''}</h2>
            <Space>
              <Button
                icon={<ArrowLeftOutlined />}
                onClick={() => window.history.back()}
              >
                返回
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleOpenCreateModal}
              >
                新建版本
              </Button>
            </Space>
          </div>

          <Table
            columns={columns}
            dataSource={versions}
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
        </>
      )}

      {/* 创建版本弹窗 */}
      <Modal
        title="新建版本"
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
            name="version_number"
            label="版本号"
            rules={[{ required: true, message: '请输入版本号' }]}
          >
            <Input placeholder="例如: V1.2.0" />
          </Form.Item>
          <Form.Item
            name="parent_version_id"
            label="父版本"
          >
            <Select placeholder="请选择父版本（可选）" allowClear>
              {parentVersions.map(v => (
                <Option key={v.id} value={v.id}>{v.version_number}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="change_summary"
            label="变更摘要"
          >
            <TextArea rows={3} placeholder="请输入变更摘要" />
          </Form.Item>
          <Form.Item
            name="requirement_doc"
            label="需求文档"
          >
            <TextArea rows={3} placeholder="请输入需求文档内容" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 克隆版本弹窗 */}
      <Modal
        title={`克隆版本 ${currentVersion?.version_number}`}
        open={cloneModalVisible}
        onCancel={() => {
          setCloneModalVisible(false)
          cloneForm.resetFields()
          setCurrentVersion(null)
        }}
        onOk={handleClone}
        confirmLoading={cloneLoading}
        destroyOnClose
      >
        <Form
          form={cloneForm}
          layout="vertical"
          autoComplete="off"
        >
          <Form.Item
            name="new_version_number"
            label="新版本号"
            rules={[{ required: true, message: '请输入新版本号' }]}
          >
            <Input placeholder="例如: V1.3.0" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 版本详情抽屉 */}
      <Drawer
        title="版本详情"
        open={detailDrawerVisible}
        onClose={() => {
          setDetailDrawerVisible(false)
          setCurrentVersion(null)
        }}
        width={600}
      >
        {currentVersion ? (
          <Spin spinning={false}>
            <Descriptions column={1} bordered>
              <Descriptions.Item label="版本号">{currentVersion.version_number}</Descriptions.Item>
              <Descriptions.Item label="状态">
                {(() => {
                  const statusConfig = versionStatuses.find(s => s.value === currentVersion.status)
                  return statusConfig ? <Tag color={statusConfig.color}>{statusConfig.label}</Tag> : currentVersion.status
                })()}
              </Descriptions.Item>
              <Descriptions.Item label="父版本">
                {currentVersion.parent_version_id ? (
                  (() => {
                    const parent = parentVersions.find(v => v.id === currentVersion.parent_version_id)
                    return parent ? parent.version_number : '-'
                  })()
                ) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="变更摘要">{currentVersion.change_summary || '-'}</Descriptions.Item>
              <Descriptions.Item label="需求文档">{currentVersion.requirement_doc || '-'}</Descriptions.Item>
              <Descriptions.Item label="测试范围">
                {currentVersion.test_scope?.length ? (
                  <Space wrap>
                    {currentVersion.test_scope.map(tag => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                  </Space>
                ) : '-'}
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