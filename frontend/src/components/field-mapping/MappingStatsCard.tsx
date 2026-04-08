import React from 'react'
import { Button, Card, Descriptions, Space, Typography } from 'antd'

const { Paragraph, Title } = Typography

interface MappingStatsCardProps {
  stats: {
    total_mappings: number
    confirmed_mappings: number
    proposed_mappings: number
    rejected_mappings: number
    avg_confidence: number
    ai_mappings: number
    manual_mappings: number
  } | null
  fallbackTotal: number
  loading?: boolean
  onAutoApply: () => void
  onOpenClone: () => void
}

const MappingStatsCard: React.FC<MappingStatsCardProps> = ({
  stats,
  fallbackTotal,
  loading = false,
  onAutoApply,
  onOpenClone,
}) => {
  return (
    <Card className="workspace-table-card" bordered={false}>
      <div className="governance-filter-grid">
        <div className="governance-note-card">
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <div>
              <Title level={5} style={{ marginBottom: 4 }}>映射质量概览</Title>
              <Descriptions size="small" column={1}>
                <Descriptions.Item label="总映射">{stats?.total_mappings ?? fallbackTotal}</Descriptions.Item>
                <Descriptions.Item label="已确认">{stats?.confirmed_mappings ?? 0}</Descriptions.Item>
                <Descriptions.Item label="待处理">{stats?.proposed_mappings ?? 0}</Descriptions.Item>
                <Descriptions.Item label="AI 来源">{stats?.ai_mappings ?? 0}</Descriptions.Item>
                <Descriptions.Item label="平均置信度">
                  {stats?.avg_confidence ? `${(stats.avg_confidence * 100).toFixed(1)}%` : '-'}
                </Descriptions.Item>
              </Descriptions>
            </div>
          </Space>
        </div>

        <div className="governance-note-card">
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <div>
              <Title level={5} style={{ marginBottom: 4 }}>治理动作</Title>
              <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                这里处理长期映射资产，包括自动应用高置信映射，以及跨版本克隆已有映射。
              </Paragraph>
            </div>
            <Space wrap>
              <Button onClick={onOpenClone}>克隆映射</Button>
              <Button type="primary" loading={loading} onClick={onAutoApply}>
                自动应用高置信映射
              </Button>
            </Space>
          </Space>
        </div>
      </div>
    </Card>
  )
}

export default MappingStatsCard
