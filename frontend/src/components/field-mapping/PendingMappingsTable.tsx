import React from 'react'
import { Button, Empty, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { PendingFieldMapping } from '../../services/fieldMappingGovernance'

const getMethodColor = (method?: string) => {
  const normalized = (method || '').toUpperCase()
  if (normalized === 'GET') return 'blue'
  if (normalized === 'POST') return 'green'
  if (normalized === 'PUT') return 'gold'
  if (normalized === 'DELETE') return 'red'
  if (normalized === 'PATCH') return 'purple'
  return 'default'
}

interface PendingMappingsTableProps {
  loading?: boolean
  items: PendingFieldMapping[]
  onStatusChange: (mappingId: number, status: 'confirmed' | 'rejected' | 'proposed') => void
}

const PendingMappingsTable: React.FC<PendingMappingsTableProps> = ({
  loading = false,
  items,
  onStatusChange,
}) => {
  const columns: ColumnsType<PendingFieldMapping> = [
    {
      title: 'API',
      key: 'api',
      width: 280,
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Space wrap>
            <Tag color={getMethodColor(record.definition_method)}>{record.definition_method || '-'}</Tag>
            <span>{record.definition_path || '-'}</span>
          </Space>
          <span>{record.api_field_path}</span>
        </Space>
      ),
    },
    {
      title: '候选映射',
      key: 'mapping',
      width: 240,
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <span>{record.db_table}.{record.db_column}</span>
          <Space wrap>
            <Tag color="blue">{record.relation_type || 'direct'}</Tag>
            <Tag>{record.source || 'manual'}</Tag>
          </Space>
        </Space>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 120,
      render: (value: number | undefined) => (typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space wrap>
          <Button type="link" onClick={() => onStatusChange(record.id, 'confirmed')}>确认</Button>
          <Button type="link" danger onClick={() => onStatusChange(record.id, 'rejected')}>拒绝</Button>
          <Button type="link" onClick={() => onStatusChange(record.id, 'proposed')}>设回待审核</Button>
        </Space>
      ),
    },
  ]

  return (
    <Table
      rowKey="id"
      loading={loading}
      columns={columns}
      dataSource={items}
      pagination={{ pageSize: 10, hideOnSinglePage: true }}
      locale={{ emptyText: <Empty description="当前没有待处理映射" /> }}
    />
  )
}

export default PendingMappingsTable
