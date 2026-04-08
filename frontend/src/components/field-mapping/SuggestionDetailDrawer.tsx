import React from 'react'
import { Card, Descriptions, Drawer, Empty, List, Space, Tag, Typography } from 'antd'
import type { FieldMappingSuggestion } from '../../services/fieldMappingSuggestion'

const { Text, Title } = Typography

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

const formatPercent = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '-'
  }
  return `${(value * 100).toFixed(1)}%`
}

const renderTraceValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toString() : '-'
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

const renderKeyValueTags = (record: Record<string, unknown>) => {
  const entries = Object.entries(record || {})
  if (entries.length === 0) {
    return <Text type="secondary">-</Text>
  }

  return (
    <Space wrap>
      {entries.map(([key, value]) => (
        <Tag key={key}>{`${key}:${renderTraceValue(value)}`}</Tag>
      ))}
    </Space>
  )
}

interface SuggestionDetailDrawerProps {
  open: boolean
  suggestion: FieldMappingSuggestion | null
  onClose: () => void
}

const SuggestionDetailDrawer: React.FC<SuggestionDetailDrawerProps> = ({
  open,
  suggestion,
  onClose,
}) => {
  return (
    <Drawer title="建议详情" open={open} width={760} onClose={onClose}>
      {suggestion ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="API">
              <Space wrap>
                <Tag color={getMethodColor(suggestion.definition_method)}>
                  {suggestion.definition_method}
                </Tag>
                <Text strong>{suggestion.definition_path}</Text>
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="字段路径">{suggestion.api_field_path}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={getStatusColor(suggestion.status || 'pending')}>
                {suggestion.status || 'pending'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="决策来源">
              <Tag color={getDecisionSourceColor(suggestion.decision_source || suggestion.decision_artifact?.decision_source)}>
                {suggestion.decision_source || suggestion.decision_artifact?.decision_source || 'rule'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="关系类型">
              <Tag color={getRelationTypeColor(suggestion.relation_type || suggestion.decision_artifact?.relation_type)}>
                {suggestion.relation_type || suggestion.decision_artifact?.relation_type || 'direct'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="最终置信度">
              {formatPercent(suggestion.confidence ?? suggestion.decision_artifact?.confidence)}
            </Descriptions.Item>
          </Descriptions>

          {suggestion.decision_artifact ? (
            <Card className="governance-note-card" bordered={false}>
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Title level={5} style={{ marginBottom: 0 }}>决策产物</Title>
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="最高候选">
                    {suggestion.decision_artifact.top_candidate
                      ? `${suggestion.decision_artifact.top_candidate.db_table}.${suggestion.decision_artifact.top_candidate.db_column}`
                      : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="来源">{suggestion.decision_artifact.decision_source || '-'}</Descriptions.Item>
                  <Descriptions.Item label="关系">{suggestion.decision_artifact.relation_type || '-'}</Descriptions.Item>
                  <Descriptions.Item label="置信度">{formatPercent(suggestion.decision_artifact.confidence)}</Descriptions.Item>
                </Descriptions>
              </Space>
            </Card>
          ) : null}

          <Card className="governance-note-card" bordered={false}>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Title level={5} style={{ marginBottom: 0 }}>候选字段</Title>
              {suggestion.candidates?.length ? (
                <List
                  dataSource={suggestion.candidates}
                  renderItem={(candidate) => (
                    <List.Item>
                      <Space direction="vertical" size={2}>
                        <Space wrap>
                          <Text strong>{candidate.db_table}.{candidate.db_column}</Text>
                          <Tag color={candidate.ai_selected ? 'green' : 'blue'}>
                            {candidate.ai_selected ? 'AI 选中' : '规则选中'}
                          </Tag>
                        </Space>
                        <Text type="secondary">score: {(candidate.score * 100).toFixed(1)}%</Text>
                        {typeof candidate.confidence === 'number' ? <Text type="secondary">confidence: {formatPercent(candidate.confidence)}</Text> : null}
                        {candidate.relation_type ? <Text type="secondary">relation: {candidate.relation_type}</Text> : null}
                        {candidate.negative_evidence?.length ? <Text type="secondary">negative: {candidate.negative_evidence.join(' / ')}</Text> : null}
                        {candidate.reject_reasons?.length ? <Text type="secondary">reject: {candidate.reject_reasons.join(' / ')}</Text> : null}
                        <Text type="secondary">{candidate.reasons?.join(' / ') || '无额外说明'}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有候选字段" />
              )}
            </Space>
          </Card>

          {suggestion.decision_trace ? (
            <Card className="governance-note-card" bordered={false}>
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Text type="secondary">决策轨迹</Text>
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="来源">
                    {renderTraceValue(suggestion.decision_trace.decision_source)}
                  </Descriptions.Item>
                  <Descriptions.Item label="最高候选">
                    {renderTraceValue(suggestion.decision_trace.top_candidate_key || suggestion.decision_trace.top_final_candidate)}
                  </Descriptions.Item>
                  <Descriptions.Item label="关系">
                    {renderTraceValue(suggestion.decision_trace.relation_type)}
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">
                    {typeof suggestion.decision_trace.confidence === 'number'
                      ? formatPercent(suggestion.decision_trace.confidence)
                      : renderTraceValue(suggestion.decision_trace.confidence)}
                  </Descriptions.Item>
                  <Descriptions.Item label="降级原因">
                    {renderTraceValue(suggestion.decision_trace.fallback_reason)}
                  </Descriptions.Item>
                  <Descriptions.Item label="运行时先验">
                    {renderKeyValueTags((suggestion.decision_trace.runtime_table_prior || {}) as Record<string, unknown>)}
                  </Descriptions.Item>
                  <Descriptions.Item label="负向证据">
                    {suggestion.candidates?.[0]?.negative_evidence?.length
                      ? suggestion.candidates[0].negative_evidence.join(' / ')
                      : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="拒绝原因">
                    {suggestion.candidates?.[0]?.reject_reasons?.length
                      ? suggestion.candidates[0].reject_reasons.join(' / ')
                      : '-'}
                  </Descriptions.Item>
                </Descriptions>
                <pre className="governance-json-block">
                  {JSON.stringify(suggestion.decision_trace, null, 2)}
                </pre>
              </Space>
            </Card>
          ) : null}
        </Space>
      ) : null}
    </Drawer>
  )
}

export default SuggestionDetailDrawer
