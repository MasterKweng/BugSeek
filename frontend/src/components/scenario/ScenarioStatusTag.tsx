import React from 'react'
import { Tag } from 'antd'

interface ScenarioStatusTagProps {
  status?: string | null
}

const statusColorMap: Record<string, string> = {
  published: 'success',
  validated: 'processing',
  draft: 'default',
  archived: 'default',
  active: 'success',
  completed: 'success',
  passed: 'success',
  running: 'processing',
  pending: 'processing',
  failed: 'error',
  rejected: 'error',
  paused: 'warning',
  accepted: 'processing',
  applied: 'success',
}

const statusLabelMap: Record<string, string> = {
  published: '已发布',
  validated: '已校验',
  draft: '草稿',
  archived: '已归档',
  active: '启用中',
  completed: '已完成',
  passed: '通过',
  running: '运行中',
  pending: '等待中',
  failed: '失败',
  rejected: '已拒绝',
  paused: '已暂停',
  accepted: '已接受',
  applied: '已应用',
}

const ScenarioStatusTag: React.FC<ScenarioStatusTagProps> = ({ status }) => (
  <Tag color={status ? statusColorMap[status] || 'default' : 'default'}>
    {status ? statusLabelMap[status] || status : '-'}
  </Tag>
)

export default ScenarioStatusTag
