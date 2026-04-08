import React, { useEffect, useState } from 'react'
import { Button, Drawer, Empty, List, Space, Tag, Typography, message } from 'antd'
import { Link } from 'react-router-dom'
import { listAsyncTasks, type AsyncTaskSummary } from '../../services/fieldMappingTask'

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
  if (status === 'failed') return 'error'
  if (status === 'partial_success') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'running') return 'processing'
  return 'default'
}

interface TaskHistoryDrawerProps {
  open: boolean
  currentTaskId: number
  projectId?: number
  versionId?: number
  onClose: () => void
}

const TaskHistoryDrawer: React.FC<TaskHistoryDrawerProps> = ({
  open,
  currentTaskId,
  projectId,
  versionId,
  onClose,
}) => {
  const [loading, setLoading] = useState(false)
  const [tasks, setTasks] = useState<AsyncTaskSummary[]>([])

  useEffect(() => {
    const load = async () => {
      if (!open || !projectId || !versionId) {
        return
      }

      setLoading(true)
      try {
        const response = await listAsyncTasks({
          project_id: projectId,
          version_id: versionId,
          task_type: 'field_mapping_suggest',
          limit: 10,
          offset: 0,
        })
        setTasks(response.data?.items || [])
      } catch (error: any) {
        setTasks([])
        message.error(error.message || '获取任务历史失败')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [open, projectId, versionId])

  return (
    <Drawer title="任务历史" placement="right" width={520} open={open} onClose={onClose}>
      {tasks.length ? (
        <List
          loading={loading}
          dataSource={tasks}
          renderItem={(item) => (
            <List.Item
              actions={[
                item.id === currentTaskId ? (
                  <Tag key={`current-${item.id}`} color="blue">当前任务</Tag>
                ) : (
                  <Button key={`view-${item.id}`} type="link" onClick={onClose}>
                    <Link to={`/version-center/field-mapping/tasks/${item.id}`}>查看任务</Link>
                  </Button>
                ),
              ]}
            >
              <List.Item.Meta
                title={(
                  <Space wrap>
                    <Text strong>任务 #{item.id}</Text>
                    <Tag color={getStatusColor(item.status)}>{item.status}</Tag>
                    <Text type="secondary">{item.progress}%</Text>
                  </Space>
                )}
                description={(
                  <Space direction="vertical" size={4}>
                    <Text type="secondary">创建时间：{formatDateTime(item.created_at)}</Text>
                    <Text type="secondary">结果数：{item.result_count ?? '-'}</Text>
                    {item.error_message ? <Text type="danger">{item.error_message}</Text> : null}
                  </Space>
                )}
              />
            </List.Item>
          )}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史任务" />
      )}
    </Drawer>
  )
}

export default TaskHistoryDrawer
