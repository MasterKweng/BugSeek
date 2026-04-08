import React from 'react'
import { Button, Empty, Segmented, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { FieldMappingWithDetails } from '../../services/fieldMappingGovernance'

type MappingFilter = 'all' | 'confirmed' | 'rejected' | 'proposed'

const getMethodColor = (method?: string) => {
  const normalized = (method || '').toUpperCase()
  if (normalized === 'GET') return 'blue'
  if (normalized === 'POST') return 'green'
  if (normalized === 'PUT') return 'gold'
  if (normalized === 'DELETE') return 'red'
  if (normalized === 'PATCH') return 'purple'
  return 'default'
}

const getStatusColor = (status?: string) => {
  if (status === 'confirmed') return 'success'
  if (status === 'rejected') return 'error'
  if (status === 'proposed') return 'processing'
  return 'default'
}

interface MappingsTableProps {
  loading?: boolean
  mappings: FieldMappingWithDetails[]
  mappingFilter: MappingFilter
  onMappingFilterChange: (value: MappingFilter) => void
  onDelete: (mappingId: number) => void
}

const MappingsTable: React.FC<MappingsTableProps> = ({
  loading = false,
  mappings,
  mappingFilter,
  onMappingFilterChange,
  onDelete,
}) => {
  const filteredMappings = mappingFilter === 'all'
    ? mappings
    : mappings.filter((item) => item.status === mappingFilter)

  const columns: ColumnsType<FieldMappingWithDetails> = [
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
      title: '已生效映射',
      key: 'mapping',
      width: 260,
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <span>{record.db_table}.{record.db_column}</span>
          <Space wrap>
            <Tag color="blue">{record.relation_type || 'direct'}</Tag>
            <Tag color={record.source === 'ai' ? 'magenta' : 'default'}>{record.source || 'manual'}</Tag>
          </Space>
        </Space>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 120,
      render: (value: number | null | undefined) => (typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (value: string | undefined) => <Tag color={getStatusColor(value)}>{value || '-'}</Tag>,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (value: string | undefined) => value ? new Date(value).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Button danger type="link" onClick={() => typeof record.id === 'number' && onDelete(record.id)}>
          删除
        </Button>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div className="governance-toolbar">
        <Segmented
          value={mappingFilter}
          onChange={(value) => onMappingFilterChange(value as MappingFilter)}
          options={[
            { label: '全部', value: 'all' },
            { label: '已确认', value: 'confirmed' },
            { label: '已拒绝', value: 'rejected' },
            { label: '待审核', value: 'proposed' },
          ]}
        />
      </div>
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={filteredMappings}
        scroll={{ y: 'calc(100vh - 520px)' }}
        pagination={{ pageSize: 10, hideOnSinglePage: true }}
        locale={{ emptyText: <Empty description="当前版本还没有字段映射" /> }}
      />
    </Space>
  )
}

export default MappingsTable
