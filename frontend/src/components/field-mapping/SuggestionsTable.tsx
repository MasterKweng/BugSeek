import React from 'react'
import { Button, Empty, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { FieldMappingSuggestion } from '../../services/fieldMappingSuggestion'

const { Text } = Typography

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
  if (status === 'failed') return 'error'
  if (status === 'partial_success') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'running') return 'processing'
  return 'default'
}

const getDecisionSourceColor = (value?: string | null) => {
  if (value === 'ai') return 'magenta'
  if (value === 'fallback') return 'orange'
  if (value === 'rule') return 'blue'
  return 'default'
}

const getRelationTypeColor = (value?: string | null) => {
  if (value === 'direct') return 'green'
  if (value === 'fk') return 'gold'
  if (value === 'derived') return 'purple'
  return 'default'
}

interface SuggestionsTableProps {
  loading?: boolean
  suggestions: FieldMappingSuggestion[]
  selectedRowKeys: React.Key[]
  onSelectedRowKeysChange: (keys: React.Key[]) => void
  onViewDetail: (suggestion: FieldMappingSuggestion) => void
  suggestionPage: number
  suggestionPageSize: number
  suggestionTotal: number
  onPageChange: (page: number, pageSize: number) => void
}

const suggestionPageSizeOptions = ['20', '50', '100']

const SuggestionsTable: React.FC<SuggestionsTableProps> = ({
  loading = false,
  suggestions,
  selectedRowKeys,
  onSelectedRowKeysChange,
  onViewDetail,
  suggestionPage,
  suggestionPageSize,
  suggestionTotal,
  onPageChange,
}) => {
  const columns: ColumnsType<FieldMappingSuggestion> = [
    {
      title: 'API',
      key: 'api',
      width: 280,
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Space wrap>
            <Tag color={getMethodColor(record.definition_method)}>{record.definition_method}</Tag>
            <Text strong>{record.definition_path}</Text>
          </Space>
          <Text type="secondary">{record.api_field_path}</Text>
        </Space>
      ),
    },
    {
      title: '候选映射',
      key: 'candidate',
      render: (_, record) => {
        const candidate = record.top_candidate || record.candidates?.[0]
        if (!candidate) {
          return <Text type="secondary">暂无候选</Text>
        }

        return (
          <Space direction="vertical" size={2}>
            <Text strong>{candidate.db_table}.{candidate.db_column}</Text>
            <Text type="secondary">{candidate.reasons?.join(' / ') || '暂无说明'}</Text>
          </Space>
        )
      },
    },
    {
      title: '置信度',
      key: 'confidence',
      width: 180,
      render: (_, record) => {
        const confidence = (
          record.confidence
          ?? record.top_candidate?.confidence
          ?? record.candidates?.[0]?.confidence
          ?? record.candidates?.[0]?.score
        ) || 0
        return <Progress percent={Number((confidence * 100).toFixed(1))} size="small" />
      },
    },
    {
      title: '决策',
      key: 'decision',
      width: 180,
      render: (_, record) => {
        const decisionSource = record.decision_source || record.decision_artifact?.decision_source || 'rule'
        const relationType = record.relation_type || record.decision_artifact?.relation_type || 'direct'
        return (
          <Space wrap>
            <Tag color={getDecisionSourceColor(decisionSource)}>{decisionSource}</Tag>
            <Tag color={getRelationTypeColor(relationType)}>{relationType}</Tag>
          </Space>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string | undefined) => <Tag color={getStatusColor(value || 'pending')}>{value || 'pending'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 110,
      render: (_, record) => (
        <Button type="link" onClick={() => onViewDetail(record)}>
          查看
        </Button>
      ),
    },
  ]

  return (
    <Table
      rowKey={(record) => record.id || `${record.definition_id}-${record.api_field_path}`}
      rowSelection={{
        selectedRowKeys,
        onChange: onSelectedRowKeysChange,
        getCheckboxProps: (record) => ({
          disabled: !record.id || !record.candidates?.length || record.status === 'confirmed',
        }),
      }}
      loading={loading}
      columns={columns}
      dataSource={suggestions}
      scroll={{ y: 'calc(100vh - 520px)' }}
      pagination={{
        current: suggestionPage,
        pageSize: suggestionPageSize,
        total: suggestionTotal,
        showSizeChanger: true,
        pageSizeOptions: suggestionPageSizeOptions,
        hideOnSinglePage: false,
        showTotal: (total) => `共 ${total} 条`,
        onChange: onPageChange,
      }}
      locale={{ emptyText: <Empty description="当前任务还没有可审阅的建议结果" /> }}
    />
  )
}

export default SuggestionsTable
