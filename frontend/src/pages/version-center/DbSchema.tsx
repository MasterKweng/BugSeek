import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Breadcrumb,
  Button,
  Card,
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
  Upload
} from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { DbSchemaDetail, DbSchemaSummary } from '../../types'
import { useProjectStore } from '../../store/project'
import {
  deleteDbSchema,
  getDbSchemaDetail,
  getDbSchemas,
  importDbSchema
} from '../../services/dbSchema'

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
  const [schemaJson, setSchemaJson] = useState<Record<string, any> | null>(null)
  const [fileName, setFileName] = useState<string>('')
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

  const handleFileBeforeUpload = (file: File) => {
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

  const handleImport = async () => {
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
      <Breadcrumb style={{ marginBottom: 16 }}>
        <Breadcrumb.Item>版本中心</Breadcrumb.Item>
        <Breadcrumb.Item>数据结构</Breadcrumb.Item>
      </Breadcrumb>

      <Card
        title={`数据结构 - ${currentProject.name} / ${currentVersion.version_number}`}
        extra={<Button type="primary" onClick={openImport}>导入结构</Button>}
      >
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={data}
          pagination={{ pageSize: 10 }}
        />
      </Card>

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
      >
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
              beforeUpload={handleFileBeforeUpload}
              showUploadList={false}
              disabled={importLoading}
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
            {fileName ? (
              <div style={{ marginTop: 8, color: '#999' }}>已选择：{fileName}</div>
            ) : null}
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default DbSchema
