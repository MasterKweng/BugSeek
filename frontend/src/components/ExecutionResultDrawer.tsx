import React, { useEffect, useState } from 'react'
import { Button, Descriptions, Drawer, Empty, Space, Spin, Tag, Typography, message } from 'antd'
import { CopyOutlined } from '@ant-design/icons'

import { getExecutionResultDetail } from '../services/executions'
import type { ExecutionResultDetail } from '../types/execution'

const { Paragraph, Text } = Typography

interface ExecutionResultDrawerProps {
  open: boolean
  resultId: number | null
  onClose: () => void
}

const prettyJson = (value: unknown) => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return '{}'
  }
}

const copyText = async (value: string, label: string) => {
  try {
    await navigator.clipboard.writeText(value)
    message.success(`${label}已复制`)
  } catch {
    message.error(`${label}复制失败`)
  }
}

const CopyBlock: React.FC<{
  title: string
  value: string
}> = ({ title, value }) => (
  <div>
    <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 8 }}>
      <Text strong>{title}</Text>
      <Button type="link" icon={<CopyOutlined />} onClick={() => void copyText(value, title)}>
        复制
      </Button>
    </Space>
    <Paragraph code style={{ marginTop: 0, whiteSpace: 'pre-wrap' }}>
      {value}
    </Paragraph>
  </div>
)

const ExecutionResultDrawer: React.FC<ExecutionResultDrawerProps> = ({ open, resultId, onClose }) => {
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<ExecutionResultDetail | null>(null)

  useEffect(() => {
    if (!open || !resultId) {
      setDetail(null)
      return
    }

    const loadDetail = async () => {
      setLoading(true)
      try {
        const response = await getExecutionResultDetail(resultId)
        setDetail(response)
      } catch (error: any) {
        message.error(error.message || '加载执行结果详情失败')
      } finally {
        setLoading(false)
      }
    }

    void loadDetail()
  }, [open, resultId])

  return (
    <Drawer
      title={detail?.target_name || `执行结果 #${resultId ?? '-'}`}
      open={open}
      onClose={onClose}
      width={720}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <Spin size="large" />
        </div>
      ) : !detail ? (
        <Empty description="暂无执行结果详情" />
      ) : (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Descriptions bordered size="small" column={2}>
            <Descriptions.Item label="状态">
              <Tag color={detail.status === 'passed' ? 'success' : detail.status === 'failed' ? 'error' : 'processing'}>
                {detail.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="响应码">{detail.response_code ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="耗时">{detail.response_time ?? 0} ms</Descriptions.Item>
            <Descriptions.Item label="断言">{detail.assertions.passed}/{detail.assertions.total}</Descriptions.Item>
            <Descriptions.Item label="用例 ID">{detail.case_id ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="接口定义 ID">{detail.definition_id ?? '-'}</Descriptions.Item>
          </Descriptions>

          {detail.error_message ? (
            <CopyBlock title="错误信息" value={detail.error_message} />
          ) : null}

          <div>
            <Text strong>请求</Text>
            <Descriptions bordered size="small" column={1} style={{ marginTop: 8 }}>
              <Descriptions.Item label="展示类型">{detail.request.display_type || '-'}</Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 12 }}>
              <CopyBlock title="请求头" value={prettyJson(detail.request.headers)} />
              <CopyBlock title="请求体" value={detail.request.raw || prettyJson(detail.request.json)} />
            </div>
          </div>

          <div>
            <Text strong>响应</Text>
            <Descriptions bordered size="small" column={1} style={{ marginTop: 8 }}>
              <Descriptions.Item label="展示类型">{detail.response.display_type || '-'}</Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 12 }}>
              <CopyBlock title="响应头" value={prettyJson(detail.response.headers)} />
              <CopyBlock title="响应体" value={detail.response.raw || prettyJson(detail.response.json)} />
            </div>
          </div>

          <CopyBlock title="断言结果" value={prettyJson(detail.assertions.items)} />
          <CopyBlock title="提取变量" value={prettyJson(detail.extracted_variables)} />
        </Space>
      )}
    </Drawer>
  )
}

export default ExecutionResultDrawer
