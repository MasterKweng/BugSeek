import React from 'react'
import { Button, Card, Space } from 'antd'
import type { AsyncTask } from '../../services/fieldMappingTask'

interface TaskActionBarProps {
  task: AsyncTask | null
  actionLoading?: 'cancel' | 'resume' | 'reset' | null
  onCancel: () => void
  onResume: () => void
  onReset: () => void
}

const TaskActionBar: React.FC<TaskActionBarProps> = ({
  task,
  actionLoading = null,
  onCancel,
  onResume,
  onReset,
}) => {
  if (!task) {
    return null
  }

  const showCancel = task.status === 'pending' || task.status === 'running'
  const showRecovery = task.status === 'failed' || task.status === 'partial_success' || task.status === 'cancelled'

  if (!showCancel && !showRecovery) {
    return null
  }

  return (
    <Card className="workspace-table-card" bordered={false} title="任务操作">
      <Space wrap>
        {showCancel ? (
          <Button danger loading={actionLoading === 'cancel'} onClick={onCancel}>
            取消任务
          </Button>
        ) : null}
        {showRecovery ? (
          <Button type="primary" loading={actionLoading === 'resume'} onClick={onResume}>
            继续执行
          </Button>
        ) : null}
        {showRecovery ? (
          <Button loading={actionLoading === 'reset'} onClick={onReset}>
            重置任务
          </Button>
        ) : null}
      </Space>
    </Card>
  )
}

export default TaskActionBar
