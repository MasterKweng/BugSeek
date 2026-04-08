import React from 'react'
import { Alert, Button, Card, Descriptions, Space, Tag, Typography } from 'antd'
import type { AsyncTask } from '../../services/fieldMappingTask'

const { Text } = Typography

interface PartialSuccessRecoveryCardProps {
  task: AsyncTask | null
  loading?: boolean
  onReplay: () => void
}

const PartialSuccessRecoveryCard: React.FC<PartialSuccessRecoveryCardProps> = ({
  task,
  loading = false,
  onReplay,
}) => {
  if (!task || task.status !== 'partial_success') {
    return null
  }

  return (
    <Card className="workspace-table-card" bordered={false} title="Recovery">
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Alert
          type="warning"
          showIcon
          message="This task partially succeeded"
          description="The task completed with recoverable issues. You can replay suggestions back into the suggestions table without rerunning the whole task."
        />

        <Descriptions size="small" column={1}>
          <Descriptions.Item label="Task status">
            <Tag color="warning">{task.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Error message">
            <Text type="secondary">{task.error_message || '-'}</Text>
          </Descriptions.Item>
        </Descriptions>

        <Button type="primary" loading={loading} onClick={onReplay}>
          Replay Suggestions
        </Button>
      </Space>
    </Card>
  )
}

export default PartialSuccessRecoveryCard
