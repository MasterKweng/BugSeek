import React from 'react'
import { Button, Result, Space, Typography } from 'antd'
import { Link, Navigate } from 'react-router-dom'

const { Paragraph } = Typography

interface FieldMappingSuggestionsProps {
  fixedTaskId?: number | null
}

const FieldMappingSuggestions: React.FC<FieldMappingSuggestionsProps> = ({
  fixedTaskId = null,
}) => {
  if (fixedTaskId) {
    return <Navigate to={`/version-center/field-mapping/tasks/${fixedTaskId}`} replace />
  }

  return (
    <Result
      status="info"
      title="字段映射页面已拆分"
      subTitle="旧的 FieldMappingSuggestions 页面已经拆成总览页、任务详情页、治理页和字典页。请从新的页面入口继续使用。"
      extra={(
        <Space wrap>
          <Button type="primary">
            <Link to="/version-center/field-mapping">进入字段映射总览</Link>
          </Button>
          <Button>
            <Link to="/version-center/field-mapping/mappings">进入映射治理</Link>
          </Button>
        </Space>
      )}
    >
      <Paragraph type="secondary">
        这个兼容组件会暂时保留，用于避免旧引用直接失效；后续确认没有外部依赖后可以再删除。
      </Paragraph>
    </Result>
  )
}

export default FieldMappingSuggestions
