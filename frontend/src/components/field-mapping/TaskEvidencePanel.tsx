import React from 'react'
import { Card, Collapse, Col, Empty, Row, Space, Statistic, Tag, Typography } from 'antd'
import type { TaskEvidenceContribution } from '../../hooks/field-mapping/useFieldMappingTaskDetail'

const { Text, Title } = Typography

interface TaskEvidencePanelProps {
  loading?: boolean
  contribution: TaskEvidenceContribution | null
}

const renderTagList = (title: string, items: Array<{ key: string; count: number }>) => (
  <Space direction="vertical" size={8} style={{ width: '100%' }}>
    <Text strong>{title}</Text>
    {items.length ? (
      <Space wrap>
        {items.map((item) => (
          <Tag key={`${title}-${item.key}`}>
            {item.key}: {item.count}
          </Tag>
        ))}
      </Space>
    ) : (
      <Text type="secondary">No signal</Text>
    )}
  </Space>
)

const TaskEvidencePanel: React.FC<TaskEvidencePanelProps> = ({ loading = false, contribution }) => {
  return (
    <Card className="workspace-table-card" bordered={false} loading={loading} title="Evidence Contribution">
      {!contribution ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No completed suggestions available yet" />
      ) : (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Row gutter={[16, 16]}>
            <Col xs={12} md={12}>
              <Statistic title="Total suggestions" value={contribution.totalSuggestions} />
            </Col>
            <Col xs={12} md={12}>
              <Statistic title="Analyzed" value={contribution.analyzedSuggestions} />
            </Col>
            <Col xs={12} md={12}>
              <Statistic title="SQL hits" value={contribution.effectiveSignals.sql} />
            </Col>
            <Col xs={12} md={12}>
              <Statistic title="Code hits" value={contribution.effectiveSignals.code} />
            </Col>
            <Col xs={12} md={12}>
              <Statistic title="Runtime hits" value={contribution.effectiveSignals.runtime} />
            </Col>
            <Col xs={12} md={12}>
              <Statistic title="Cross hits" value={contribution.effectiveSignals.cross} />
            </Col>
            <Col xs={12} md={12}>
              <Statistic title="Vector hits" value={contribution.effectiveSignals.vector} />
            </Col>
            <Col xs={12} md={12}>
              <Statistic title="History hits" value={contribution.effectiveSignals.history} />
            </Col>
          </Row>

          <Text type="secondary">
            Lexical evidence hit count: {contribution.effectiveSignals.lexical}
          </Text>

          <Row gutter={[16, 16]}>
            <Col xs={24}>
              {renderTagList('Decision sources', contribution.decisionSources)}
            </Col>
            <Col xs={24}>
              {renderTagList('Recall sources', contribution.recallSources)}
            </Col>
          </Row>

          <Collapse
            size="small"
            ghost
            items={[
              {
                key: 'advanced-features',
                label: 'Advanced signals',
                children: (
                  <Row gutter={[16, 16]}>
                    <Col xs={24}>
                      {renderTagList('Top positive features', contribution.positiveFeatures)}
                    </Col>
                    <Col xs={24}>
                      {renderTagList('Top negative evidence', contribution.negativeEvidence)}
                    </Col>
                  </Row>
                ),
              },
            ]}
          />

          {contribution.analyzedSuggestions < contribution.totalSuggestions ? (
            <Title level={5} style={{ margin: 0 }}>
              Sampled {contribution.analyzedSuggestions} of {contribution.totalSuggestions} suggestions for this view.
            </Title>
          ) : null}
        </Space>
      )}
    </Card>
  )
}

export default TaskEvidencePanel
