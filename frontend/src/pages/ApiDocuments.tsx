import { useState, useEffect } from 'react'
import { Table, Button, Upload, message, Modal, Space, Input } from 'antd'
import { UploadOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import type { UploadChangeParam } from 'antd/es/upload'
import type { ColumnsType } from 'antd/es/table'
import api from '../services/api'
import type { ApiDocument } from '../types'

const ApiDocuments: React.FC = () => {
  const [documents, setDocuments] = useState<ApiDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [documentName, setDocumentName] = useState('')

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      const result = await api.get('/api-integration/documents')
      if (result.code === 0) {
        setDocuments(result.data.documents || [])
      }
    } catch (error: any) {
      message.error(error.message || '获取文档列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDocuments()
  }, [])

  const handleUpload = async () => {
    if (!uploadFile) {
      message.error('请选择文件')
      return
    }

    const formData = new FormData()
    formData.append('file', uploadFile)
    if (documentName) {
      formData.append('name', documentName)
    }

    setLoading(true)
    try {
      const result = await api.post('/api-integration/documents/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      if (result.code === 0) {
        message.success('文档导入成功')
        setUploadModalVisible(false)
        setUploadFile(null)
        setDocumentName('')
        fetchDocuments()
      }
    } catch (error: any) {
      message.error(error.message || '文档导入失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      const result = await api.delete(`/api-integration/documents/${id}`)
      if (result.code === 0) {
        message.success('删除成功')
        fetchDocuments()
      }
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const handleFileChange = (info: UploadChangeParam) => {
    if (info.fileList.length > 0) {
      setUploadFile(info.fileList[0].originFileObj as File)
    }
  }

  const columns: ColumnsType<ApiDocument> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '文档名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '来源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 120,
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 100,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            icon={<EyeOutlined />}
            size="small"
          >
            查看
          </Button>
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            size="small"
            onClick={() => handleDelete(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h1>接口文档管理</h1>
        <Button
          type="primary"
          icon={<UploadOutlined />}
          onClick={() => setUploadModalVisible(true)}
        >
          导入文档
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={documents}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="导入接口文档"
        open={uploadModalVisible}
        onOk={handleUpload}
        onCancel={() => {
          setUploadModalVisible(false)
          setUploadFile(null)
          setDocumentName('')
        }}
        confirmLoading={loading}
      >
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px' }}>文档名称（可选）</label>
          <Input
            placeholder="请输入文档名称"
            value={documentName}
            onChange={(e) => setDocumentName(e.target.value)}
          />
        </div>
        <Upload
          accept=".json,.yaml,.yml"
          beforeUpload={() => false}
          onChange={handleFileChange}
          maxCount={1}
        >
          <Button icon={<UploadOutlined />}>选择文件</Button>
        </Upload>
        {uploadFile && (
          <div style={{ marginTop: '8px', color: '#52c41a' }}>
            已选择: {uploadFile.name}
          </div>
        )}
      </Modal>
    </div>
  )
}

export default ApiDocuments