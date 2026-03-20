import React from 'react'
import { Alert, Card, Descriptions, Empty, Progress, Space, Steps, Tag, Typography } from 'antd'

import type { AsyncTask } from '../services/fieldMapping'

const { Text } = Typography

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN')
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

const mapStageStatus = (status?: string): 'wait' | 'process' | 'finish' | 'error' => {
  if (status === 'running') return 'process'
  if (status === 'completed') return 'finish'
  if (status === 'failed' || status === 'cancelled') return 'error'
  return 'wait'
}

interface FieldMappingTaskObservabilityProps {
  task: AsyncTask | null
}

const FieldMappingTaskObservability: React.FC<FieldMappingTaskObservabilityProps> = ({ task }) => {
  if (!task) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有字段映射任务" />
  }

  const artifactsSummary = task.artifacts_summary
  const consistencyOk = task.statistics?.consistency_ok

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Descriptions size="small" column={1}>
        <Descriptions.Item label="任务 ID">#{task.id}</Descriptions.Item>
        <Descriptions.Item label="状态">
          <Tag color={getStatusColor(task.status)}>{task.status}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="进度">{task.progress}%</Descriptions.Item>
        <Descriptions.Item label="创建时间">{formatDateTime(task.created_at)}</Descriptions.Item>
        <Descriptions.Item label="Engine">{task.engine_version || '-'}</Descriptions.Item>
        <Descriptions.Item label="Artifacts">{artifactsSummary?.total_artifacts ?? 0}</Descriptions.Item>
        <Descriptions.Item label="Consistency">
          {consistencyOk === true ? (
            <Tag color="success">OK</Tag>
          ) : consistencyOk === false ? (
            <Tag color="error">Mismatch</Tag>
          ) : (
            <Tag>Unknown</Tag>
          )}
        </Descriptions.Item>
      </Descriptions>

      <Progress
        percent={task.progress}
        status={task.status === 'failed' ? 'exception' : task.status === 'completed' ? 'success' : 'active'}
      />

      {artifactsSummary ? (
        <Text type="secondary">
          by stage: {Object.entries(artifactsSummary.by_stage || {}).map(([key, value]) => `${key}:${value}`).join(', ') || '-'}
        </Text>
      ) : null}
      {typeof task.statistics?.consistency_diff === 'number' ? (
        <Text type="secondary">consistency diff: {task.statistics.consistency_diff}</Text>
      ) : null}
      {task.progress_message ? <Text type="secondary">{task.progress_message}</Text> : null}
      {task.error_message ? <Alert type="error" showIcon message={task.error_message} /> : null}

      {task.stages && task.stages.length > 0 ? (
        <Card size="small" title="阶段详情">
          <Steps
            direction="vertical"
            size="small"
            current={Math.max(task.stages.findIndex((stage) => stage.status === 'running'), 0)}
            items={task.stages.map((stage, index) => ({
              key: `${stage.name}-${index}`,
              title: stage.name,
              description: stage.description || undefined,
              status: mapStageStatus(stage.status),
            }))}
          />
        </Card>
      ) : null}
    </Space>
  )
}

export default FieldMappingTaskObservability
