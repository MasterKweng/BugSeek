import React from 'react'
import { Button, Card, Progress, Space, Steps, Tag, Typography } from 'antd'
import type { AsyncTask } from '../../services/fieldMappingTask'

const { Text } = Typography

const mapStageStatus = (status?: string): 'wait' | 'process' | 'finish' | 'error' => {
  if (status === 'running') return 'process'
  if (status === 'completed') return 'finish'
  if (status === 'failed' || status === 'cancelled') return 'error'
  return 'wait'
}

interface TaskStagesPanelProps {
  task: AsyncTask | null
  onViewStage?: (stageNum: number) => void
  onRetryStage?: (stageNum: number) => void
  retryingStageNum?: number | null
}

const TaskStagesPanel: React.FC<TaskStagesPanelProps> = ({
  task,
  onViewStage,
  onRetryStage,
  retryingStageNum = null,
}) => {
  if (!task?.stages?.length) {
    return null
  }

  return (
    <Card className="workspace-table-card" bordered={false} title="阶段进度">
      <Steps
        direction="vertical"
        size="small"
        current={Math.max(task.stages.findIndex((stage) => stage.status === 'running'), 0)}
        items={task.stages.map((stage, index) => ({
          key: `${stage.name}-${index}`,
          title: stage.name,
          description: (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {stage.description ? <Text type="secondary">{stage.description}</Text> : null}
              <Progress percent={stage.progress ?? 0} size="small" />
              <Space wrap>
                <Tag>{stage.status}</Tag>
                <Button size="small" onClick={() => onViewStage?.(index + 1)}>
                  查看详情
                </Button>
                {task.can_retry && task.retryable_stages?.includes(index + 1) ? (
                  <Button
                    size="small"
                    loading={retryingStageNum === index + 1}
                    onClick={() => onRetryStage?.(index + 1)}
                  >
                    重试此阶段
                  </Button>
                ) : null}
              </Space>
            </Space>
          ),
          status: mapStageStatus(stage.status),
        }))}
      />
    </Card>
  )
}

export default TaskStagesPanel
