import React, { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import { ArrowLeftOutlined, CopyOutlined, RedoOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import ExecutionResultDrawer from '../../components/ExecutionResultDrawer'
import { getProjectEnvironments } from '../../services/environments'
import {
  getExecutionChildren,
  getExecutionDetail,
  getExecutionResults,
  rerunExecution,
} from '../../services/executions'
import { useProjectStore } from '../../store/project'
import type {
  ExecutionDetail as ExecutionDetailType,
  ExecutionResultSummary,
  ExecutionSummary,
} from '../../types/execution'

const { Paragraph, Text } = Typography

const prettyJson = (value: unknown) => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return '{}'
  }
}

const statusColorMap: Record<string, string> = {
  completed: 'success',
  passed: 'success',
  failed: 'error',
  error: 'error',
  partial_failed: 'warning',
  running: 'processing',
  pending: 'default',
  skipped: 'default',
}

const copyText = async (value: string, label: string) => {
  try {
    await navigator.clipboard.writeText(value)
    message.success(`${label}已复制`)
  } catch {
    message.error(`${label}复制失败`)
  }
}

const ExecutionDetail: React.FC = () => {
  const navigate = useNavigate()
  const { executionId } = useParams()
  const { currentProject, currentVersion } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [rerunLoading, setRerunLoading] = useState(false)
  const [detail, setDetail] = useState<ExecutionDetailType | null>(null)
  const [children, setChildren] = useState<ExecutionSummary[]>([])
  const [results, setResults] = useState<ExecutionResultSummary[]>([])
  const [environmentOptions, setEnvironmentOptions] = useState<Array<{ label: string; value: number }>>([])
  const [selectedResultId, setSelectedResultId] = useState<number | null>(null)
  const [rerunOpen, setRerunOpen] = useState(false)
  const [resultStatusFilter, setResultStatusFilter] = useState<string | undefined>(undefined)
  const [resultKeyword, setResultKeyword] = useState('')
  const [rerunForm] = Form.useForm()

  const numericExecutionId = Number(executionId)

  useEffect(() => {
    const loadEnvironments = async () => {
      if (!currentProject?.id) {
        setEnvironmentOptions([])
        return
      }
      try {
        const response = await getProjectEnvironments(currentProject.id, 1, 100)
        setEnvironmentOptions((response.items || []).map((item) => ({ label: item.name, value: item.id })))
      } catch (error) {
        console.error('加载环境失败', error)
      }
    }

    void loadEnvironments()
  }, [currentProject?.id])

  const loadDetail = async () => {
    if (!numericExecutionId) {
      return
    }
    setLoading(true)
    try {
      const [executionDetail, childrenResponse, resultResponse] = await Promise.all([
        getExecutionDetail(numericExecutionId),
        getExecutionChildren(numericExecutionId, 1, 100),
        getExecutionResults(numericExecutionId, 1, 100, resultStatusFilter, resultKeyword || undefined),
      ])
      setDetail(executionDetail)
      setChildren(childrenResponse.items || [])
      setResults(resultResponse.items || [])
      rerunForm.setFieldsValue({
        environment_id: executionDetail.environment_id || undefined,
        version_id: executionDetail.version_id || currentVersion?.id || undefined,
        max_concurrent: 5,
        variables_json: '{}',
      })
    } catch (error: any) {
      message.error(error.message || '加载执行详情失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDetail()
  }, [numericExecutionId, resultStatusFilter, resultKeyword])

  const handleRerun = async () => {
    if (!numericExecutionId) {
      return
    }
    try {
      const values = await rerunForm.validateFields()
      let variables = {}
      if (values.variables_json?.trim()) {
        variables = JSON.parse(values.variables_json)
        if (!variables || typeof variables !== 'object' || Array.isArray(variables)) {
          throw new Error('运行变量必须是 JSON 对象')
        }
      }
      setRerunLoading(true)
      const response = await rerunExecution(numericExecutionId, {
        environment_id: values.environment_id,
        version_id: values.version_id,
        max_concurrent: values.max_concurrent,
        variables,
      })
      message.success('已触发重新执行')
      setRerunOpen(false)
      const nextExecutionId = Number((response as Record<string, unknown>).execution_id)
      if (nextExecutionId) {
        navigate(`/operations/executions/${nextExecutionId}`)
        return
      }
      await loadDetail()
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }
      message.error(error.message || '重新执行失败')
    } finally {
      setRerunLoading(false)
    }
  }

  if (loading && !detail) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!detail) {
    return <Empty description="未找到执行详情" />
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space wrap>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/operations/executions')}>
          返回执行列表
        </Button>
        {detail.parent_execution_id ? (
          <Button onClick={() => navigate(`/operations/executions/${detail.parent_execution_id}`)}>
            查看父执行
          </Button>
        ) : null}
        {detail.source_execution_id ? (
          <Button onClick={() => navigate(`/operations/executions/${detail.source_execution_id}`)}>
            查看来源执行
          </Button>
        ) : null}
        <Button icon={<CopyOutlined />} onClick={() => void copyText(String(detail.id), '执行 ID')}>
          复制执行 ID
        </Button>
        <Button type="primary" icon={<RedoOutlined />} onClick={() => setRerunOpen(true)}>
          重新执行
        </Button>
      </Space>

      <Card
        title={detail.title || `执行 #${detail.id}`}
        extra={<Tag color={statusColorMap[detail.status] || 'default'}>{detail.status}</Tag>}
      >
        <Descriptions bordered size="small" column={3}>
          <Descriptions.Item label="执行 ID">
            <Space size="small">
              <Text>{detail.id}</Text>
              <Tooltip title="复制执行 ID">
                <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => void copyText(String(detail.id), '执行 ID')}
                />
              </Tooltip>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="执行类型">{detail.execution_type}</Descriptions.Item>
          <Descriptions.Item label="结果状态">
            <Tag color={statusColorMap[detail.result_status || ''] || 'default'}>{detail.result_status || '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="环境">{detail.environment_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="版本">{detail.version_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="触发方式">{detail.triggered_by || '-'}</Descriptions.Item>
          <Descriptions.Item label="父执行">
            {detail.parent_execution_id ? (
              <Space size="small">
                <Text>{detail.parent_execution_id}</Text>
                <Button type="link" size="small" onClick={() => navigate(`/operations/executions/${detail.parent_execution_id}`)}>
                  跳转
                </Button>
                <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => void copyText(String(detail.parent_execution_id), '父执行 ID')}
                />
              </Space>
            ) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="来源执行">
            {detail.source_execution_id ? (
              <Space size="small">
                <Text>{detail.source_execution_id}</Text>
                <Button type="link" size="small" onClick={() => navigate(`/operations/executions/${detail.source_execution_id}`)}>
                  跳转
                </Button>
                <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => void copyText(String(detail.source_execution_id), '来源执行 ID')}
                />
              </Space>
            ) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="操作人">{detail.operator_user_id || '-'}</Descriptions.Item>
          <Descriptions.Item label="开始时间">{detail.started_at || '-'}</Descriptions.Item>
          <Descriptions.Item label="结束时间">{detail.finished_at || '-'}</Descriptions.Item>
          <Descriptions.Item label="耗时">{detail.duration ?? 0} ms</Descriptions.Item>
        </Descriptions>
        <div style={{ marginTop: 16 }}>
          <Text strong>摘要</Text>
          <Paragraph code style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
            {prettyJson(detail.summary)}
          </Paragraph>
        </div>
      </Card>

      <Card title="执行统计">
        <Space size="large" wrap>
          <Text>总数 {detail.stats.total}</Text>
          <Text>通过 {detail.stats.passed}</Text>
          <Text>失败 {detail.stats.failed}</Text>
          <Text>跳过 {detail.stats.skipped}</Text>
          <Text>子执行 {detail.children_count}</Text>
        </Space>
        <div style={{ marginTop: 16, maxWidth: 360 }}>
          <Progress
            percent={detail.stats.total > 0 ? Math.round((detail.stats.passed / detail.stats.total) * 100) : 0}
            status={detail.stats.failed > 0 ? 'exception' : 'success'}
            format={(percent) => `通过率 ${percent || 0}%`}
          />
        </div>
      </Card>

      {detail.source_execution_id ? (
        <Alert type="info" showIcon message={`本次执行来源于执行 #${detail.source_execution_id}`} />
      ) : null}

      {children.length > 0 ? (
        <Card title="子执行">
          <Table<ExecutionSummary>
            rowKey="id"
            pagination={false}
            dataSource={children}
            columns={[
              { title: 'ID', dataIndex: 'id', width: 80 },
              { title: '标题', dataIndex: 'title' },
              {
                title: '状态',
                dataIndex: 'status',
                render: (value: string) => <Tag color={statusColorMap[value] || 'default'}>{value}</Tag>,
              },
              {
                title: '结果',
                dataIndex: 'result_status',
                render: (value: string) => <Tag color={statusColorMap[value] || 'default'}>{value}</Tag>,
              },
              { title: '耗时', dataIndex: 'duration', render: (value: number | null) => `${value ?? 0} ms` },
              {
                title: '操作',
                render: (_, record) => (
                  <Space size="small">
                    <Button type="link" onClick={() => navigate(`/operations/executions/${record.id}`)}>
                      查看
                    </Button>
                    <Button
                      type="link"
                      icon={<CopyOutlined />}
                      onClick={() => void copyText(String(record.id), '子执行 ID')}
                    >
                      复制 ID
                    </Button>
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      ) : null}

      <Card title="执行结果">
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            allowClear
            style={{ width: 180 }}
            placeholder="结果状态筛选"
            value={resultStatusFilter}
            onChange={(value) => setResultStatusFilter(value)}
            options={[
              { label: '通过', value: 'passed' },
              { label: '失败', value: 'failed' },
              { label: '错误', value: 'error' },
              { label: '跳过', value: 'skipped' },
            ]}
          />
          <Input.Search
            allowClear
            placeholder="搜索目标名称"
            style={{ width: 260 }}
            value={resultKeyword}
            onChange={(event) => setResultKeyword(event.target.value)}
            onSearch={(value) => setResultKeyword(value)}
          />
        </Space>
        <Table<ExecutionResultSummary>
          rowKey="result_id"
          pagination={false}
          dataSource={results}
          columns={[
            { title: '结果 ID', dataIndex: 'result_id', width: 100 },
            { title: '目标名称', dataIndex: 'target_name' },
            {
              title: '状态',
              dataIndex: 'status',
              width: 100,
              render: (value: string) => <Tag color={statusColorMap[value] || 'default'}>{value}</Tag>,
            },
            { title: '响应码', dataIndex: 'response_code', width: 100 },
            { title: '耗时', dataIndex: 'response_time', width: 100, render: (value: number | null) => `${value ?? 0} ms` },
            {
              title: '断言',
              key: 'assertions',
              width: 120,
              render: (_, record) => `${record.assertion_passed_count}/${record.assertion_total_count}`,
            },
            {
              title: '操作',
              width: 180,
              render: (_, record) => (
                <Space size="small">
                  <Button type="link" onClick={() => setSelectedResultId(record.result_id)}>
                    查看
                  </Button>
                  <Button
                    type="link"
                    icon={<CopyOutlined />}
                    onClick={() => void copyText(String(record.result_id), '结果 ID')}
                  >
                    复制 ID
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <ExecutionResultDrawer
        open={selectedResultId !== null}
        resultId={selectedResultId}
        onClose={() => setSelectedResultId(null)}
      />

      <Modal
        title="重新执行"
        open={rerunOpen}
        onCancel={() => setRerunOpen(false)}
        onOk={() => void handleRerun()}
        confirmLoading={rerunLoading}
        destroyOnClose
      >
        <Form form={rerunForm} layout="vertical">
          <Form.Item name="environment_id" label="环境">
            <Select allowClear options={environmentOptions} placeholder="留空则使用原环境" />
          </Form.Item>
          <Form.Item name="version_id" label="版本">
            <InputNumber style={{ width: '100%' }} placeholder="留空则使用原版本" />
          </Form.Item>
          <Form.Item name="max_concurrent" label="批执行并发数">
            <InputNumber min={1} max={20} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="variables_json" label="运行变量 JSON">
            <Input.TextArea rows={6} placeholder='例如：{"token":"demo"}' />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}

export default ExecutionDetail
