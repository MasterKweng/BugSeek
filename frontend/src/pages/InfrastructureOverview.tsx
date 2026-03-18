import React from 'react'
import { Alert, Card, Col, Descriptions, Row, Space, Tag, Typography } from 'antd'
import './InfrastructureOverview.css'

const { Paragraph, Text, Title } = Typography

const InfrastructureOverview: React.FC = () => {
  return (
    <div className="infra-page">
      <Card className="infra-hero" bordered={false}>
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Tag color="geekblue">Infrastructure</Tag>
          <Title level={2} style={{ margin: 0 }}>Foundation Status</Title>
          <Paragraph className="infra-copy">
            This page tracks the core infrastructure decisions shipped for V2: Redis-backed auth cache, PDF report generation,
            and artifact storage configuration for reports, attachments, and graph exports.
          </Paragraph>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card className="infra-card" title="Auth Cache">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Backend">`backend/app/core/auth_service.py`</Descriptions.Item>
              <Descriptions.Item label="Mode">Redis hash + memory fallback</Descriptions.Item>
              <Descriptions.Item label="TTL">`AUTH_CACHE_TTL_SECONDS`</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card className="infra-card" title="PDF Reports">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Backend">`backend/app/core/reporting/generator.py`</Descriptions.Item>
              <Descriptions.Item label="Primary">Playwright HTML to PDF</Descriptions.Item>
              <Descriptions.Item label="Fallback">Built-in text PDF renderer</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card className="infra-card" title="Artifacts">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Settings">`OBJECT_STORAGE_*`</Descriptions.Item>
              <Descriptions.Item label="Local Dir">`ARTIFACT_LOCAL_DIR`</Descriptions.Item>
              <Descriptions.Item label="Ops Doc">`docs/infrastructure_operations.md`</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <Alert
        type="info"
        showIcon
        message="对象存储在这轮先完成配置与运维说明，运行时默认仍走本地制品目录。"
      />

      <Card className="infra-card" title="Recommended Env Vars">
        <Space direction="vertical" size={6}>
          <Text code>REDIS_URL</Text>
          <Text code>AUTH_CACHE_TTL_SECONDS</Text>
          <Text code>OBJECT_STORAGE_ENABLED</Text>
          <Text code>OBJECT_STORAGE_PROVIDER</Text>
          <Text code>OBJECT_STORAGE_BUCKET</Text>
          <Text code>ARTIFACT_LOCAL_DIR</Text>
        </Space>
      </Card>
    </div>
  )
}

export default InfrastructureOverview
