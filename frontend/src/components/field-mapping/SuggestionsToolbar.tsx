import React from 'react'
import { Button, Input, Select, Space } from 'antd'
import { CheckOutlined, CloseOutlined, ReloadOutlined } from '@ant-design/icons'

type SuggestionStatusFilter = 'all' | 'pending' | 'confirmed' | 'rejected'
type MethodFilter = 'all' | 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
type FieldTypeFilter = 'all' | 'path' | 'query' | 'body'
type DecisionSourceFilter = 'all' | 'rule' | 'ai' | 'fallback'
type RelationTypeFilter = 'all' | 'direct' | 'fk' | 'derived'

interface SuggestionsToolbarProps {
  searchKeyword: string
  onSearchKeywordChange: (value: string) => void
  pathFilter: string
  onPathFilterChange: (value: string) => void
  statusFilter: SuggestionStatusFilter
  onStatusFilterChange: (value: SuggestionStatusFilter) => void
  methodFilter: MethodFilter
  onMethodFilterChange: (value: MethodFilter) => void
  fieldTypeFilter: FieldTypeFilter
  onFieldTypeFilterChange: (value: FieldTypeFilter) => void
  decisionSourceFilter: DecisionSourceFilter
  onDecisionSourceFilterChange: (value: DecisionSourceFilter) => void
  relationTypeFilter: RelationTypeFilter
  onRelationTypeFilterChange: (value: RelationTypeFilter) => void
  selectedCount: number
  loading?: boolean
  onConfirm: () => void
  onReject: () => void
  onRefresh: () => void
}

const SuggestionsToolbar: React.FC<SuggestionsToolbarProps> = ({
  searchKeyword,
  onSearchKeywordChange,
  pathFilter,
  onPathFilterChange,
  statusFilter,
  onStatusFilterChange,
  methodFilter,
  onMethodFilterChange,
  fieldTypeFilter,
  onFieldTypeFilterChange,
  decisionSourceFilter,
  onDecisionSourceFilterChange,
  relationTypeFilter,
  onRelationTypeFilterChange,
  selectedCount,
  loading = false,
  onConfirm,
  onReject,
  onRefresh,
}) => {
  return (
    <>
      <div className="governance-toolbar">
        <Input.Search
          allowClear
          value={searchKeyword}
          placeholder="搜索 API 字段、表名或列名"
          onChange={(event) => onSearchKeywordChange(event.target.value.trim())}
          onSearch={(value) => onSearchKeywordChange(value.trim())}
          style={{ maxWidth: 280 }}
        />
        <Input
          allowClear
          value={pathFilter}
          placeholder="按 API 路径过滤"
          onChange={(event) => onPathFilterChange(event.target.value.trim())}
          style={{ maxWidth: 260 }}
        />
        <Select value={statusFilter} onChange={onStatusFilterChange} style={{ width: 140 }}>
          <Select.Option value="all">全部状态</Select.Option>
          <Select.Option value="pending">待审核</Select.Option>
          <Select.Option value="confirmed">已确认</Select.Option>
          <Select.Option value="rejected">已拒绝</Select.Option>
        </Select>
        <Select value={methodFilter} onChange={onMethodFilterChange} style={{ width: 120 }}>
          <Select.Option value="all">全部方法</Select.Option>
          <Select.Option value="GET">GET</Select.Option>
          <Select.Option value="POST">POST</Select.Option>
          <Select.Option value="PUT">PUT</Select.Option>
          <Select.Option value="DELETE">DELETE</Select.Option>
          <Select.Option value="PATCH">PATCH</Select.Option>
        </Select>
        <Select value={fieldTypeFilter} onChange={onFieldTypeFilterChange} style={{ width: 120 }}>
          <Select.Option value="all">全部位置</Select.Option>
          <Select.Option value="path">path</Select.Option>
          <Select.Option value="query">query</Select.Option>
          <Select.Option value="body">body</Select.Option>
        </Select>
        <Select value={decisionSourceFilter} onChange={onDecisionSourceFilterChange} style={{ width: 140 }}>
          <Select.Option value="all">全部来源</Select.Option>
          <Select.Option value="rule">规则</Select.Option>
          <Select.Option value="ai">AI</Select.Option>
          <Select.Option value="fallback">降级</Select.Option>
        </Select>
        <Select value={relationTypeFilter} onChange={onRelationTypeFilterChange} style={{ width: 140 }}>
          <Select.Option value="all">全部关系</Select.Option>
          <Select.Option value="direct">direct</Select.Option>
          <Select.Option value="fk">fk</Select.Option>
          <Select.Option value="derived">derived</Select.Option>
        </Select>
      </div>

      <Space wrap>
        <Button
          type="primary"
          icon={<CheckOutlined />}
          disabled={selectedCount === 0}
          loading={loading}
          onClick={onConfirm}
        >
          批量确认
        </Button>
        <Button
          danger
          icon={<CloseOutlined />}
          disabled={selectedCount === 0}
          loading={loading}
          onClick={onReject}
        >
          批量拒绝
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={loading}
          onClick={onRefresh}
        >
          刷新结果
        </Button>
      </Space>
    </>
  )
}

export default SuggestionsToolbar
