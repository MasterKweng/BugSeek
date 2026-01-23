import { useState, useEffect } from 'react'
import { Table, Input, Select, Tag, Space } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import api from '../services/api'
import type { ApiEndpoint } from '../types'

const { Search } = Input
const { Option } = Select

const ApiEndpoints: React.FC = () => {
  const [endpoints, setEndpoints] = useState<ApiEndpoint[]>([])
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [methodFilter, setMethodFilter] = useState<string | undefined>()

  const fetchEndpoints = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (methodFilter) {
        params.method = methodFilter
      }
      if (searchText) {
        params.search = searchText
      }

      const result = await api.get('/api-integration/endpoints', { params })
      if (result.code === 0) {
        setEndpoints(result.data.endpoints || [])
      }
    } catch (error: any) {
      console.error('获取接口列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEndpoints()
  }, [methodFilter, searchText])

  const getMethodColor = (method: string) => {
    const colors: Record<string, string> = {
      GET: 'green',
      POST: 'blue',
      PUT: 'orange',
      DELETE: 'red',
      PATCH: 'purple',
    }
    return colors[method] || 'default'
  }

  const columns: ColumnsType<ApiEndpoint> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      width: 100,
      render: (method: string) => (
        <Tag color={getMethodColor(method)}>{method}</Tag>
      ),
    },
    {
      title: '路径',
      dataIndex: 'path',
      key: 'path',
      ellipsis: true,
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: true,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 200,
      render: (tags: string[] | null) => (
        <Space size="small" wrap>
          {tags?.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      <h1>接口定义管理</h1>

      <Space style={{ marginBottom: '16px' }}>
        <Search
          placeholder="搜索接口"
          allowClear
          enterButton={<SearchOutlined />}
          style={{ width: 300 }}
          onSearch={setSearchText}
        />
        <Select
          placeholder="选择方法"
          allowClear
          style={{ width: 120 }}
          onChange={setMethodFilter}
        >
          <Option value="GET">GET</Option>
          <Option value="POST">POST</Option>
          <Option value="PUT">PUT</Option>
          <Option value="DELETE">DELETE</Option>
          <Option value="PATCH">PATCH</Option>
        </Select>
      </Space>

      <Table
        columns={columns}
        dataSource={endpoints}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />
    </div>
  )
}

export default ApiEndpoints