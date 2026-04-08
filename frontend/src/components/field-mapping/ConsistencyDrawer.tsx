import React from 'react'
import { Descriptions, Drawer, Space, Tag, Typography } from 'antd'
import type { AsyncTask } from '../../services/fieldMappingTask'

const { Paragraph, Text } = Typography

interface ConsistencyDrawerProps {
  open: boolean
  task: AsyncTask | null
  onClose: () => void
}

const ConsistencyDrawer: React.FC<ConsistencyDrawerProps> = ({ open, task, onClose }) => {
  const consistencyOk = task?.consistency_ok ?? task?.statistics?.consistency_ok
  const consistencyDiff = task?.consistency_diff ?? task?.statistics?.consistency_diff
  const resultTableMismatch = task?.result_table_mismatch ?? task?.statistics?.result_table_mismatch
  const resultTraceMismatch = task?.result_trace_mismatch ?? task?.statistics?.result_trace_mismatch
  const resultArtifactMismatch = task?.result_artifact_mismatch ?? task?.statistics?.result_artifact_mismatch

  return (
    <Drawer title="Consistency 摘要" placement="right" width={560} open={open} onClose={onClose}>
      <Descriptions size="small" column={1} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="总体状态">
          {consistencyOk === true ? <Tag color="success">OK</Tag> : consistencyOk === false ? <Tag color="error">Mismatch</Tag> : <Tag>Unknown</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="Diff 数量">{typeof consistencyDiff === 'number' ? consistencyDiff : '-'}</Descriptions.Item>
        <Descriptions.Item label="Table mismatch">{resultTableMismatch ? '是' : '否'}</Descriptions.Item>
        <Descriptions.Item label="Trace mismatch">{resultTraceMismatch ? '是' : '否'}</Descriptions.Item>
        <Descriptions.Item label="Artifact mismatch">{resultArtifactMismatch ? '是' : '否'}</Descriptions.Item>
      </Descriptions>

      <Paragraph strong>异常说明</Paragraph>
      <Space wrap style={{ marginBottom: 12 }}>
        {resultTableMismatch ? <Tag color="error">table mismatch</Tag> : null}
        {resultTraceMismatch ? <Tag color="error">trace mismatch</Tag> : null}
        {resultArtifactMismatch ? <Tag color="error">artifact mismatch</Tag> : null}
        {!resultTableMismatch && !resultTraceMismatch && !resultArtifactMismatch ? <Tag color="success">暂无不一致标记</Tag> : null}
      </Space>

      <Paragraph strong>恢复建议</Paragraph>
      <Text type="secondary">
        这一版先提供任务级 consistency 摘要。若出现 mismatch，优先查看阶段详情与 artifacts，确认差异发生在哪个阶段，再决定是重试阶段还是重置任务。
      </Text>
    </Drawer>
  )
}

export default ConsistencyDrawer
