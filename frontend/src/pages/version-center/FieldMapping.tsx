import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Breadcrumb,
  Button,
  Card,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Result,
  Select,
  Slider,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Progress,
  Popover
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import api from '../../services/api'
import type { FieldMapping, DbSchemaDetail, DbSchemaSummary } from '../../types'
import { useProjectStore } from '../../store/project'
import { getDbSchemaDetail, getDbSchemas } from '../../services/dbSchema'
import {
  createFieldMapping,
  deleteFieldMapping,
  getFieldMappings,
  getPendingFieldMappings,
  cloneFieldMappings,
  autoApplyFieldMappings,
  getLearningStats
} from '../../services/fieldMapping'
import FieldMappingSuggestions from '../FieldMappingSuggestions'

interface ApiDefinitionOption {
  id: number
  path: string
  method: string
  summary?: string | null
}

const FieldMappingPage: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject, currentVersion } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [tabKey, setTabKey] = useState('manual')
  const [data, setData] = useState<FieldMapping[]>([])
  const [pendingData, setPendingData] = useState<FieldMapping[]>([])
  const [definitions, setDefinitions] = useState<ApiDefinitionOption[]>([])
  const [schemaList, setSchemaList] = useState<DbSchemaSummary[]>([])
  const [schemaDetail, setSchemaDetail] = useState<DbSchemaDetail | null>(null)
  const [selectedSchemaId, setSelectedSchemaId] = useState<number | null>(null)
  const [selectedDefinitionId, setSelectedDefinitionId] = useState<number | undefined>(undefined)
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [cloneModalOpen, setCloneModalOpen] = useState(false)
  const [autoApplyModalOpen, setAutoApplyModalOpen] = useState(false)
  const [learningStats, setLearningStats] = useState<any>(null)
  const [autoApplyConfidence, setAutoApplyConfidence] = useState(0.85)
  const [cloneFromVersion, setCloneFromVersion] = useState<number | undefined>(undefined)
  const [versions, setVersions] = useState<any[]>([])
  const [form] = Form.useForm()

  const requestParams = useMemo(() => {
    return {
      project_id: currentProject?.id,
      version_id: currentVersion?.id
    }
  }, [currentProject?.id, currentVersion?.id])

  const fetchVersions = async () => {
    if (!currentProject) return
    try {
      const res = await api.get(`/projects/${currentProject.id}/versions`)
      const items = res.data?.items || []
      setVersions(items.filter((v: any) => v.id !== currentVersion?.id)) // 排除当前版本
    } catch (error: any) {
      message.error(error.message || '获取版本列表失败')
    }
  }

  const fetchLearningStats = async () => {
    if (!currentProject || !currentVersion) return
    try {
      const res = await getLearningStats(requestParams)
      setLearningStats(res.data)
    } catch (error: any) {
      console.error('获取学习统计失败', error)
    }
  }

  const fetchDefinitions = async () => {
    if (!currentProject || !currentVersion) {
      setDefinitions([])
      return
    }
    try {
      const res = await api.get('/api-definitions', {
        params: { ...requestParams, limit: 200 }
      })
      const items = res.data?.items || []
      setDefinitions(items.map((item: any) => ({
        id: item.id,
        path: item.path,
        method: item.method,
        summary: item.summary
      })))
    } catch (error: any) {
      message.error(error.message || '获取接口列表失败')
    }
  }

  const fetchSchemas = async () => {
    if (!currentProject || !currentVersion) {
      setSchemaList([])
      return
    }
    try {
      const res = await getDbSchemas(requestParams)
      const items = res.data?.items || []
      setSchemaList(items)
      if (items.length > 0) {
        setSelectedSchemaId(items[0].id)
      } else {
        setSelectedSchemaId(null)
        setSchemaDetail(null)
      }
    } catch (error: any) {
      message.error(error.message || '获取结构列表失败')
    }
  }

  const fetchSchemaDetail = async (schemaId: number) => {
    if (!currentProject || !currentVersion) {
      return
    }
    try {
      const res = await getDbSchemaDetail(schemaId, requestParams)
      setSchemaDetail(res.data)
    } catch (error: any) {
      message.error(error.message || '获取结构详情失败')
      setSchemaDetail(null)
    }
  }

  const fetchMappings = async () => {
    if (!currentProject || !currentVersion) {
      setData([])
      return
    }
    setLoading(true)
    try {
      const res = await getFieldMappings({
        ...requestParams,
        definition_id: selectedDefinitionId
      })
      setData(res.data?.items || [])
    } catch (error: any) {
      message.error(error.message || '获取字段映射失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchPendingMappings = async () => {
    if (!currentProject || !currentVersion) {
      setPendingData([])
      return
    }
    try {
      const res = await getPendingFieldMappings(requestParams)
      setPendingData(res.data?.items || [])
    } catch (error: any) {
      message.error(error.message || '获取待审核映射失败')
    }
  }

  useEffect(() => {
    fetchVersions()
    fetchLearningStats()
    fetchDefinitions()
    fetchSchemas()
  }, [currentProject?.id, currentVersion?.id])

  useEffect(() => {
    if (selectedSchemaId) {
      fetchSchemaDetail(selectedSchemaId)
    }
  }, [selectedSchemaId])

  useEffect(() => {
    fetchMappings()
    fetchPendingMappings()
  }, [currentProject?.id, currentVersion?.id, selectedDefinitionId])

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      setCreateLoading(true)
      await createFieldMapping(values, requestParams)
      message.success('创建成功')
      setCreateOpen(false)
      fetchMappings()
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }
      message.error(error.message || '创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const handleDelete = async (record: FieldMapping) => {
    try {
      await deleteFieldMapping(record.id, requestParams)
      message.success('删除成功')
      fetchMappings()
      fetchPendingMappings() // 更新待审核列表
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const handleClone = async () => {
    if (!cloneFromVersion || !currentVersion) {
      message.error('请选择源版本')
      return
    }
    
    try {
      await cloneFieldMappings({
        from_version_id: cloneFromVersion,
        to_version_id: currentVersion.id
      }, { project_id: currentProject?.id })
      message.success('克隆成功')
      setCloneModalOpen(false)
      fetchMappings()
      fetchPendingMappings()
    } catch (error: any) {
      message.error(error.message || '克隆失败')
    }
  }

  const handleAutoApply = async () => {
    try {
      await autoApplyFieldMappings({
        min_confidence: autoApplyConfidence
      }, requestParams)
      message.success(`已自动应用置信度≥${autoApplyConfidence}的映射`)
      setAutoApplyModalOpen(false)
      fetchMappings()
      fetchPendingMappings()
    } catch (error: any) {
      message.error(error.message || '自动应用失败')
    }
  }

  const tableOptions = useMemo(() => {
    const tables = schemaDetail?.schema_snapshot?.tables
    if (!Array.isArray(tables)) {
      return []
    }
    return tables.map((t: any) => ({
      label: t.name,
      value: t.name,
      columns: Array.isArray(t.columns) ? t.columns : []
    }))
  }, [schemaDetail])

  const columnOptions = (tableName?: string) => {
    const table = tableOptions.find((t) => t.value === tableName)
    if (!table) return []
    return table.columns.map((c: any) => ({
      label: c.name,
      value: c.name
    }))
  }

  const manualColumns: ColumnsType<FieldMapping> = [
    {
      title: '接口',
      dataIndex: 'definition_path',
      key: 'definition_path',
      render: (_, record) => (
        <span>{record.definition_method} {record.definition_path}</span>
      )
    },
    {
      title: 'API 字段',
      dataIndex: 'api_field_path',
      key: 'api_field_path',
      width: 180
    },
    {
      title: '表',
      dataIndex: 'db_table',
      key: 'db_table',
      width: 140
    },
    {
      title: '字段',
      dataIndex: 'db_column',
      key: 'db_column',
      width: 140
    },
    {
      title: '关系',
      dataIndex: 'relation_type',
      key: 'relation_type',
      width: 120
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 100,
      render: (value) => value ? (
        <div>
          <div>{(value * 100).toFixed(0)}%</div>
          <Progress percent={Math.round(value * 100)} size="small" showInfo={false} />
        </div>
      ) : 'N/A'
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (value) => (
        <Tag color={value === 'ai' ? 'blue' : 'green'}>
          {value === 'ai' ? 'AI' : '手动'}
        </Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value) => {
        const colorMap: Record<string, string> = {
          proposed: 'orange',
          confirmed: 'green',
          rejected: 'red'
        }
        return <Tag color={colorMap[value] || 'default'}>{value}</Tag>
      }
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 200
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Space>
          <Popconfirm
            title="确定要删除该映射吗？"
            onConfirm={() => handleDelete(record)}
          >
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  const pendingColumns: ColumnsType<FieldMapping> = [
    ...manualColumns.slice(0, -1), // 复制除操作列外的所有列
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button 
            size="small" 
            type="primary"
            onClick={() => {
              // 更新状态为confirmed
              api.put(`/field-mappings/${record.id}/status`, { status: 'confirmed' }, { params: requestParams })
                .then(() => {
                  message.success('确认成功')
                  fetchMappings()
                  fetchPendingMappings()
                })
                .catch(error => message.error(error.message || '确认失败'))
            }}
          >
            确认
          </Button>
          <Button 
            size="small" 
            danger
            onClick={() => {
              // 更新状态为rejected
              api.put(`/field-mappings/${record.id}/status`, { status: 'rejected' }, { params: requestParams })
                .then(() => {
                  message.success('驳回成功')
                  fetchPendingMappings()
                })
                .catch(error => message.error(error.message || '驳回失败'))
            }}
          >
            驳回
          </Button>
          <Popconfirm
            title="确定要删除该映射吗？"
            onConfirm={() => handleDelete(record)}
          >
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  if (!currentProject) {
    return (
      <Result
        status="warning"
        title="请先选择项目"
        extra={
          <Button type="primary" onClick={() => navigate('/projects')}>
            前往项目管理
          </Button>
        }
      />
    )
  }

  if (!currentVersion) {
    return (
      <Result
        status="warning"
        title="请先选择版本"
        extra={
          <Button type="primary" onClick={() => navigate(`/projects/${currentProject.id}/versions`)}>
            前往版本管理
          </Button>
        }
      />
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <Breadcrumb style={{ marginBottom: 16 }}>
        <Breadcrumb.Item>版本中心</Breadcrumb.Item>
        <Breadcrumb.Item>字段映射</Breadcrumb.Item>
      </Breadcrumb>

      <Card
        title={
          <Space>
            <span>字段映射 - {currentProject.name} / {currentVersion.version_number}</span>
            {learningStats && (
              <Tooltip title="学习统计信息">
                <div style={{ fontSize: '12px', color: '#999' }}>
                  总映射: {learningStats.total_mappings}, 确认: {learningStats.confirmed_mappings}, 
                  AI: {learningStats.ai_mappings}, 平均置信度: {(learningStats.avg_confidence * 100).toFixed(1)}%
                </div>
              </Tooltip>
            )}
          </Space>
        }
        extra={
          <Space>
            <Button
              type="primary"
              onClick={() => setAutoApplyModalOpen(true)}
            >
              自动应用高置信度
            </Button>
            <Button
              onClick={() => setCloneModalOpen(true)}
            >
              从其他版本继承
            </Button>
            <Button
              type="primary"
              onClick={() => setCreateOpen(true)}
              disabled={schemaList.length === 0}
            >
              新建映射
            </Button>
          </Space>
        }
      >
        <Tabs
          activeKey={tabKey}
          onChange={setTabKey}
          items={[
            {
              key: 'manual',
              label: '手动映射',
              children: (
                <>
                  <Space style={{ marginBottom: 16 }} wrap>
                    <Select
                      style={{ width: 320 }}
                      placeholder="筛选接口（可选）"
                      allowClear
                      value={selectedDefinitionId}
                      onChange={(value) => setSelectedDefinitionId(value)}
                      options={definitions.map((d) => ({
                        label: `${d.method} ${d.path}`,
                        value: d.id
                      }))}
                    />
                    <Select
                      style={{ width: 260 }}
                      placeholder="选择结构版本"
                      value={selectedSchemaId || undefined}
                      onChange={(value) => setSelectedSchemaId(value)}
                      options={schemaList.map((s) => ({
                        label: s.name,
                        value: s.id
                      }))}
                    />
                  </Space>

                  {schemaList.length === 0 ? (
                    <Result
                      status="info"
                      title="当前版本尚未导入数据库结构"
                      subTitle="请先在“版本中心-数据结构”导入结构后再创建映射"
                    />
                  ) : (
                    <Table
                      rowKey="id"
                      loading={loading}
                      columns={manualColumns}
                      dataSource={data}
                      pagination={{ pageSize: 10 }}
                    />
                  )}
                </>
              )
            },
            {
              key: 'suggestions',
              label: '映射建议',
              children: <FieldMappingSuggestions />
            },
            {
              key: 'pending',
              label: `待审核 (${pendingData.length})`,
              children: (
                <Table
                  rowKey="id"
                  loading={loading}
                  columns={pendingColumns}
                  dataSource={pendingData}
                  pagination={{ pageSize: 10 }}
                />
              )
            }
          ]}
        />
      </Card>

      <Modal
        title="新建字段映射"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        okText="创建"
        cancelText="取消"
        confirmLoading={createLoading}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="接口"
            name="definition_id"
            rules={[{ required: true, message: '请选择接口' }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="选择接口"
              options={definitions.map((d) => ({
                label: `${d.method} ${d.path}`,
                value: d.id
              }))}
            />
          </Form.Item>
          <Form.Item
            label="API 字段路径"
            name="api_field_path"
            rules={[{ required: true, message: '请输入 API 字段路径' }]}
          >
            <Input placeholder="例如：body.order_id / path.id" />
          </Form.Item>
          <Form.Item
            label="数据库表"
            name="db_table"
            rules={[{ required: true, message: '请选择数据库表' }]}
          >
            <Select
              placeholder="选择表"
              options={tableOptions.map((t) => ({
                label: t.label,
                value: t.value
              }))}
              onChange={() => {
                form.setFieldsValue({ db_column: undefined })
              }}
            />
          </Form.Item>
          <Form.Item
            label="数据库字段"
            name="db_column"
            rules={[{ required: true, message: '请选择数据库字段' }]}
          >
            <Select
              placeholder="选择字段"
              options={columnOptions(form.getFieldValue('db_table'))}
            />
          </Form.Item>
          <Form.Item label="关系类型" name="relation_type">
            <Select
              options={[
                { label: 'direct', value: 'direct' },
                { label: 'fk', value: 'fk' },
                { label: 'derived', value: 'derived' }
              ]}
            />
          </Form.Item>
          <Form.Item label="来源" name="source">
            <Select
              options={[
                { label: '手动', value: 'manual' },
                { label: 'AI', value: 'ai' }
              ]}
            />
          </Form.Item>
          <Form.Item label="状态" name="status">
            <Select
              options={[
                { label: '待确认', value: 'proposed' },
                { label: '已确认', value: 'confirmed' },
                { label: '已驳回', value: 'rejected' }
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="从其他版本继承映射"
        open={cloneModalOpen}
        onCancel={() => setCloneModalOpen(false)}
        onOk={handleClone}
        okText="克隆"
        cancelText="取消"
      >
        <Form layout="vertical">
          <Form.Item label="源版本">
            <Select
              value={cloneFromVersion}
              onChange={setCloneFromVersion}
              placeholder="选择要克隆映射的源版本"
              options={versions.map(v => ({
                label: `${v.version_number} (${v.status})`,
                value: v.id
              }))}
            />
          </Form.Item>
        </Form>
        <p>将从选定版本复制所有字段映射到当前版本</p>
      </Modal>

      <Modal
        title="自动应用高置信度映射"
        open={autoApplyModalOpen}
        onCancel={() => setAutoApplyModalOpen(false)}
        onOk={handleAutoApply}
        okText="应用"
        cancelText="取消"
      >
        <Form layout="vertical">
          <Form.Item label={`最小置信度阈值: ${autoApplyConfidence}`}>
            <Slider
              min={0}
              max={1}
              step={0.05}
              value={autoApplyConfidence}
              onChange={setAutoApplyConfidence}
            />
          </Form.Item>
        </Form>
        <p>将自动确认置信度≥{(autoApplyConfidence * 100).toFixed(0)}%的建议映射</p>
      </Modal>
    </div>
  )
}

export default FieldMappingPage