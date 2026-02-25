import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Drawer,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Result,
  Space,
  Spin,
  Table,
  Upload,
  Tabs
} from 'antd'
import { UploadOutlined, DownOutlined, RightOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { DbSchemaDetail, DbSchemaSummary } from '../../types'
import { useProjectStore } from '../../store/project'
import {
  deleteDbSchema,
  getDbSchemaDetail,
  getDbSchemas,
  importDbSchema,
  importDbSchemaFromSql,
  previewSqlSchema
} from '../../services/dbSchema'
import api from '../../services/api'

const DbSchema: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject, currentVersion } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<DbSchemaSummary[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detail, setDetail] = useState<DbSchemaDetail | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importLoading, setImportLoading] = useState(false)
  const [importTab, setImportTab] = useState<'json' | 'sql'>('json') // 新增：导入方式标签
  const [schemaJson, setSchemaJson] = useState<Record<string, any> | null>(null)
  const [sqlFile, setSqlFile] = useState<File | null>(null) // 新增：SQL文件状态
  const [fileName, setFileName] = useState<string>('')
  const [sqlFileName, setSqlFileName] = useState<string>('') // 新增：SQL文件名状态
  const [sqlContent, setSqlContent] = useState<string>('') // 新增：SQL文件内容
  const [sqlPreview, setSqlPreview] = useState<any>(null) // 新增：SQL预览结果
  const [sqlPreviewLoading, setSqlPreviewLoading] = useState(false) // 新增：预览加载状态
  const [warningsExpanded, setWarningsExpanded] = useState(false) // 新增：警告列表展开状态
  const [form] = Form.useForm()

  const requestParams = useMemo(() => {
    return {
      project_id: currentProject?.id,
      version_id: currentVersion?.id
    }
  }, [currentProject?.id, currentVersion?.id])

  const fetchList = async () => {
    if (!currentProject || !currentVersion) {
      setData([])
      return
    }
    setLoading(true)
    try {
      const res = await getDbSchemas(requestParams)
      setData(res.data?.items || [])
    } catch (error: any) {
      message.error(error.message || '获取数据库结构失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchList()
  }, [currentProject?.id, currentVersion?.id])

  const handleView = async (record: DbSchemaSummary) => {
    if (!currentProject || !currentVersion) {
      return
    }
    setDetailLoading(true)
    try {
      const res = await getDbSchemaDetail(record.id, requestParams)
      setDetail(res.data)
      setDrawerOpen(true)
    } catch (error: any) {
      message.error(error.message || '获取结构详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleDelete = async (record: DbSchemaSummary) => {
    if (!currentProject || !currentVersion) {
      return
    }
    try {
      await deleteDbSchema(record.id, requestParams)
      message.success('删除成功')
      fetchList()
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const openImport = () => {
    setSchemaJson(null)
    setFileName('')
    form.resetFields()
    setImportOpen(true)
  }

  const handleJsonFileBeforeUpload = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const json = JSON.parse(String(reader.result || '{}'))
        setSchemaJson(json)
        setFileName(file.name)
        if (!form.getFieldValue('name')) {
          form.setFieldsValue({ name: file.name.replace(/\.[^.]+$/, '') })
        }
        message.success('结构文件解析成功')
      } catch (err) {
        setSchemaJson(null)
        message.error('结构文件格式错误，请上传 JSON')
      }
    }
    reader.readAsText(file)
    return false
  }

  const handleSqlFileBeforeUpload = (file: File) => {
    // 验证文件类型
    if (!file.name.toLowerCase().endsWith('.sql') && !file.name.toLowerCase().endsWith('.txt')) {
      message.error('仅支持上传 .sql 或 .txt 文件')
      return false
    }
    
    setSqlFile(file)
    setSqlFileName(file.name)
    if (!form.getFieldValue('name')) {
      form.setFieldsValue({ name: file.name.replace(/\.[^.]+$/, '') })
    }
    
    // 读取文件内容并预览
    const reader = new FileReader()
    reader.onload = async () => {
      try {
        const content = String(reader.result || '')
        setSqlContent(content)
        
        // 自动预览
        await handlePreviewSql(content)
      } catch (err) {
        message.error('读取SQL文件失败')
      }
    }
    reader.readAsText(file)
    
    message.success('SQL文件上传成功，正在预览...')
    return false
  }

  // 预览SQL文件
  const handlePreviewSql = async (content?: string) => {
    const sqlText = content || sqlContent
    if (!sqlText) {
      return
    }

    setSqlPreviewLoading(true)
    try {
      const response = await previewSqlSchema(sqlText, requestParams)
      if (response.code === 0 && response.data) {
        setSqlPreview(response.data)
        
        const tables = response.data.tables || []
        const warnings = response.data.warnings || []
        
        message.success(`预览成功：解析出 ${tables.length} 个表${warnings.length > 0 ? `，${warnings.length} 个警告` : ''}`)
      } else {
        message.error(response.message || '预览失败')
        setSqlPreview(null)
      }
    } catch (error: any) {
      console.error('预览SQL失败:', error)
      message.error(error.message || '预览失败')
      setSqlPreview(null)
    } finally {
      setSqlPreviewLoading(false)
    }
  }

  const handleImport = async () => {
    if (importTab === 'json') {
      // JSON导入方式
      try {
        const values = await form.validateFields()
        if (!schemaJson) {
          message.error('请上传结构文件')
          return
        }
        setImportLoading(true)
        await importDbSchema(
          {
            name: values.name,
            source_type: 'upload',
            source_version: values.source_version,
            schema_snapshot: schemaJson
          },
          requestParams
        )
        message.success('导入成功')
        setImportOpen(false)
        fetchList()
      } catch (error: any) {
        if (error?.errorFields) {
          return
        }
        message.error(error.message || '导入失败')
      } finally {
        setImportLoading(false)
      }
    } else if (importTab === 'sql') {
      // SQL导入方式
      try {
        const values = await form.validateFields()
        if (!sqlFile) {
          message.error('请上传SQL文件')
          return
        }
        
        setImportLoading(true)
        
        // 创建FormData并添加文件和其他参数
        const formData = new FormData()
        formData.append('file', sqlFile)
        formData.append('name', values.name)
        if (values.source_version) {
          formData.append('source_version', values.source_version)
        }
        
        // 添加项目和版本参数
        if (requestParams.project_id) {
          formData.append('project_id', String(requestParams.project_id))
        }
        if (requestParams.version_id) {
          formData.append('version_id', String(requestParams.version_id))
        }
        
        // 调用后端API
        const response = await importDbSchemaFromSql(formData, requestParams)

        if (response.code === 0) {
          message.success('SQL文件导入成功')
          setImportOpen(false)
          fetchList()
        } else {
          message.error(response.message || '导入失败')
        }
      } catch (error: any) {
        if (error?.errorFields) {
          return
        }
        message.error(error.message || '导入失败')
      } finally {
        setImportLoading(false)
      }
    }
  }

  const columns: ColumnsType<DbSchemaSummary> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name'
    },
    {
      title: '来源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 120
    },
    {
      title: '来源版本',
      dataIndex: 'source_version',
      key: 'source_version',
      width: 140,
      render: (val) => val || '-'
    },
    {
      title: '表数量',
      dataIndex: 'table_count',
      key: 'table_count',
      width: 100
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
      width: 140,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => handleView(record)}>
            查看
          </Button>
          <Popconfirm
            title="确定要删除该结构吗？"
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>数据结构 - {currentProject.name} / {currentVersion.version_number}</h2>
        <Button type="primary" onClick={openImport}>导入结构</Button>
      </div>

      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={data}
        pagination={{ pageSize: 10 }}
      />

      <Drawer
        title="结构详情"
        open={drawerOpen}
        width={720}
        onClose={() => setDrawerOpen(false)}
      >
        <Spin spinning={detailLoading}>
          {detail ? (
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {JSON.stringify(detail.schema_snapshot, null, 2)}
            </pre>
          ) : null}
        </Spin>
      </Drawer>

      <Modal
        title="导入数据库结构"
        open={importOpen}
        onCancel={() => setImportOpen(false)}
        onOk={handleImport}
        confirmLoading={importLoading}
        okText="导入"
        cancelText="取消"
        width={700}
      >
        <Tabs 
          activeKey={importTab} 
          onChange={setImportTab}
          items={[
            {
              key: 'json',
              label: 'JSON文件',
              children: (
                <Form form={form} layout="vertical">
                  <Form.Item
                    label="结构名称"
                    name="name"
                    rules={[{ required: true, message: '请输入结构名称' }]}
                  >
                    <Input placeholder="例如：v2.0.3_schema" />
                  </Form.Item>
                  <Form.Item label="来源版本" name="source_version">
                    <Input placeholder="例如：v2.0.3" />
                  </Form.Item>
                  <Form.Item
                    label="结构文件(JSON)"
                    required
                  >
                    <Upload
                      accept=".json,application/json"
                      beforeUpload={handleJsonFileBeforeUpload}
                      showUploadList={false}
                      disabled={importLoading}
                    >
                      <Button icon={<UploadOutlined />}>选择JSON文件</Button>
                    </Upload>
                    {fileName ? (
                      <div style={{ marginTop: 8, color: 'var(--text-tertiary)' }}>已选择：{fileName}</div>
                    ) : null}
                  </Form.Item>
                </Form>
              )
            },
            {
              key: 'sql',
              label: 'SQL文件',
              children: (
                <Form form={form} layout="vertical">
                  <Form.Item
                    label="结构名称"
                    name="name"
                    rules={[{ required: true, message: '请输入结构名称' }]}
                  >
                    <Input placeholder="例如：v2.0.3_schema_from_sql" />
                  </Form.Item>
                  <Form.Item label="来源版本" name="source_version">
                    <Input placeholder="例如：v2.0.3" />
                  </Form.Item>
                  <Form.Item
                    label="SQL文件"
                    required
                  >
                    <Upload
                      accept=".sql,.txt"
                      beforeUpload={handleSqlFileBeforeUpload}
                      showUploadList={false}
                      disabled={importLoading}
                    >
                      <Button icon={<UploadOutlined />}>选择SQL文件</Button>
                    </Upload>
                    {sqlFileName ? (
                      <div style={{ marginTop: 8, color: 'var(--text-tertiary)' }}>已选择：{sqlFileName}</div>
                    ) : null}
                  </Form.Item>
                  
                  {/* SQL预览区域 */}
                  {sqlPreview && (
                    <div style={{ marginTop: 16 }}>
                      <div style={{ fontWeight: 'bold', marginBottom: 8 }}>
                        解析结果预览
                      </div>
                      {sqlPreview.tables && sqlPreview.tables.length > 0 && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ color: '#52c41a', marginBottom: 4 }}>
                            ✓ 检测到 {sqlPreview.tables.length} 个表
                          </div>
                          <div style={{ maxHeight: 200, overflow: 'auto', border: '1px solid #d9d9d9', borderRadius: 4, padding: 8 }}>
                            {sqlPreview.tables.map((table: any, idx: number) => (
                              <div key={idx} style={{ marginBottom: 4, fontSize: 12 }}>
                                <strong>{table.name}</strong>
                                <span style={{ color: 'var(--text-tertiary)', marginLeft: 8 }}>
                                  ({table.columns?.length || 0} 个字段)
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {sqlPreview.warnings && sqlPreview.warnings.length > 0 && (
                        <div style={{ marginBottom: 12 }}>
                          <div 
                            style={{ color: '#faad14', marginBottom: 4, cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                            onClick={() => setWarningsExpanded(!warningsExpanded)}
                          >
                            {warningsExpanded ? <DownOutlined /> : <RightOutlined />}
                            <span style={{ marginLeft: 8 }}>⚠ {sqlPreview.warnings.length} 个警告</span>
                          </div>
                          {warningsExpanded && (
                            <div style={{ marginTop: 8, border: '1px solid #d9d9d9', borderRadius: 4, padding: 8, backgroundColor: '#fafafa' }}>
                              {sqlPreview.warnings.map((warning: string, idx: number) => (
                                <div key={idx} style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 2 }}>
                                  - {warning}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div style={{ marginTop: 16, padding: 12, backgroundColor: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4 }}>
                    <div style={{ fontWeight: 'bold', marginBottom: 4 }}>支持的功能：</div>
                    <ul style={{ margin: 0, padding: '0 0 0 18px' }}>
                      <li>CREATE TABLE（创建表）</li>
                      <li>ALTER TABLE（添加/修改/删除列）</li>
                      <li>CREATE INDEX（创建索引）</li>
                      <li>单行/多行注释处理</li>
                      <li>多语句分割（分号分隔）</li>
                    </ul>
                    <div style={{ fontWeight: 'bold', marginTop: 8, marginBottom: 4 }}>注意事项：</div>
                    <ul style={{ margin: 0, padding: '0 0 0 18px' }}>
                      <li>请确保SQL文件使用UTF-8编码</li>
                      <li>支持的数据库：MySQL、PostgreSQL、SQLite</li>
                      <li>不支持的语句将被跳过并在警告中提示</li>
                    </ul>
                  </div>
                </Form>
              )
            }
          ]}
        />
      </Modal>
    </div>
  )
}

export default DbSchema
