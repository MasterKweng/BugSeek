import React from 'react'
import { Alert, Card, Descriptions, Progress, Space, Tag, Typography } from 'antd'
import type { AsyncTask } from '../../services/fieldMappingTask'

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

interface TaskHeaderCardProps {
  task: AsyncTask | null
}

const TaskHeaderCard: React.FC<TaskHeaderCardProps> = ({ task }) => {
  if (!task) {
    return null
  }

  const artifactsSummary = task.artifacts_summary
  const consistencyOk = task.consistency_ok ?? task.statistics?.consistency_ok
  const consistencyDiff = task.consistency_diff ?? task.statistics?.consistency_diff
  const resultTableMismatch = task.result_table_mismatch ?? task.statistics?.result_table_mismatch
  const resultTraceMismatch = task.result_trace_mismatch ?? task.statistics?.result_trace_mismatch
  const resultArtifactMismatch = task.result_artifact_mismatch ?? task.statistics?.result_artifact_mismatch

  return (
    <Card className="workspace-table-card" bordered={false}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Descriptions size="small" column={1}>
          <Descriptions.Item label="任务 ID">#{task.id}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={getStatusColor(task.status)}>{task.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="进度">{task.progress}%</Descriptions.Item>
          <Descriptions.Item label="创建时间">{formatDateTime(task.created_at)}</Descriptions.Item>
          <Descriptions.Item label="开始时间">{formatDateTime(task.started_at)}</Descriptions.Item>
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
        {typeof consistencyDiff === 'number' ? (
          <Text type="secondary">consistency diff: {consistencyDiff}</Text>
        ) : null}
        {!consistencyOk && (resultTableMismatch || resultTraceMismatch || resultArtifactMismatch) ? (
          <Space wrap>
            {resultTableMismatch ? <Tag color="error">table mismatch</Tag> : null}
            {resultTraceMismatch ? <Tag color="error">trace mismatch</Tag> : null}
            {resultArtifactMismatch ? <Tag color="error">artifact mismatch</Tag> : null}
          </Space>
        ) : null}
        {task.progress_message ? <Text type="secondary">{task.progress_message}</Text> : null}
        {task.error_message ? <Alert type="error" showIcon message={task.error_message} /> : null}
      </Space>
    </Card>
  )
}

export default TaskHeaderCard
