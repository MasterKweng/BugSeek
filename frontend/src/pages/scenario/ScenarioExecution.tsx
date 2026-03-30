import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Progress, Space, Spin, Steps, Tag, Timeline, Typography, message } from 'antd'
import { ArrowLeftOutlined, RedoOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import api from '../../services/api'
import { getTaskStatus, isTerminalTaskStatus, type UnifiedTaskStatus } from '../../services/taskStatus'
import type {
  ScenarioDetail,
  ScenarioExecutionDetail,
  ScenarioExecutionNodeResult,
} from '../../types/scenario'
import './ScenarioExecution.css'

const { Text } = Typography

const ScenarioExecution: React.FC = () => {
  const navigate = useNavigate()
  const { scenarioId, executionId } = useParams()
  const [loading, setLoading] = useState(false)
  const [execution, setExecution] = useState<ScenarioExecutionDetail | null>(null)
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null)
  const [taskStatus, setTaskStatus] = useState<UnifiedTaskStatus<ScenarioExecutionDetail> | null>(null)

  const loadExecution = useCallback(async () => {
    if (!scenarioId || !executionId) {
      return
    }

    setLoading(true)
    try {
      const response = await api.get(`/scenarios/${scenarioId}/executions/${executionId}`)
      if (response.code === 0) {
        setExecution(response.data)
      } else {
        message.error(response.message || '加载执行详情失败')
      }
    } catch (error: any) {
      message.error(error.message || '加载执行详情失败')
    } finally {
      setLoading(false)
    }
  }, [executionId, scenarioId])

  const loadScenario = useCallback(async () => {
    if (!scenarioId) {
      return
    }

    try {
      const response = await api.get(`/scenarios/${scenarioId}`)
      if (response.code === 0) {
        setScenario(response.data)
      }
    } catch (error) {
      console.error('加载场景失败:', error)
    }
  }, [scenarioId])

  const loadTaskStatus = useCallback(async () => {
    if (!executionId) {
      return null
    }

    const numericExecutionId = Number(executionId)
    if (Number.isNaN(numericExecutionId)) {
      return null
    }

    try {
      const response = await getTaskStatus<ScenarioExecutionDetail>('scenario-execution', numericExecutionId)
      if (response.code === 0) {
        setTaskStatus(response.data)
        return response.data
      }
    } catch (error) {
      console.error('加载任务状态失败:', error)
    }

    return null
  }, [executionId])

  useEffect(() => {
    void loadExecution()
    void loadScenario()
  }, [loadExecution, loadScenario])

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null
    let disposed = false

    const poll = async () => {
      const status = await loadTaskStatus()
      if (!status || disposed) {
        return
      }

      if (isTerminalTaskStatus(status.status)) {
        if (intervalId) {
          clearInterval(intervalId)
        }
        if (!execution || execution.status !== status.status) {
          await loadExecution()
        }
      }
    }

    void poll()
    if (!isTerminalTaskStatus(execution?.status)) {
      intervalId = setInterval(() => {
        void poll()
      }, 3000)
    }

    return () => {
      disposed = true
      if (intervalId) {
        clearInterval(intervalId)
      }
    }
  }, [execution, loadExecution, loadTaskStatus])

  const handleRetry = async () => {
    const environmentId = scenario?.environment_id
    if (!scenarioId || !environmentId) {
      message.warning('请先为场景选择环境')
      return
    }

    setLoading(true)
    try {
      const response = await api.post(`/scenarios/${scenarioId}/execute`, {
        environment_id: environmentId,
      })
      if (response.code === 0) {
        message.success('场景已重新执行')
        navigate(`/scenario/${scenarioId}/execution/${response.data.execution_id}`)
      } else {
        message.error(response.message || '重新执行失败')
      }
    } catch (error: any) {
      message.error(error.message || '重新执行失败')
    } finally {
      setLoading(false)
    }
  }

  const results = useMemo(() => execution?.node_results || [], [execution])
  const displayStatus = taskStatus?.status || execution?.status || '-'
  const isRunning = displayStatus === 'pending' || displayStatus === 'running'
  const successCount = results.filter((item) => item.status === 'passed').length
  const failedCount = results.filter((item) => item.status !== 'passed').length
  const totalCount = results.length
  const passRate = totalCount > 0 ? (successCount / totalCount) * 100 : 0
  const progressPercent = isRunning ? taskStatus?.progress || 0 : Math.round(passRate)

  const mapStepStatus = (stageStatus: string): 'wait' | 'process' | 'finish' | 'error' => {
    if (stageStatus === 'running') {
      return 'process'
    }
    if (stageStatus === 'completed') {
      return 'finish'
    }
    if (stageStatus === 'failed' || stageStatus === 'cancelled') {
      return 'error'
    }
    return 'wait'
  }

  if (loading && !execution) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  const renderNodeTitle = (result: ScenarioExecutionNodeResult) => {
    const node = scenario?.nodes?.find((item) => item.id === result.target_id)
    return node?.node_name || node?.node_key || `Node ${result.target_id ?? '-'}`
  }

  return (
    <div className="scenario-execution">
      <Space style={{ marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/scenario/${scenarioId}`)}>
          返回场景
        </Button>
        <Button icon={<RedoOutlined />} onClick={() => void handleRetry()} loading={loading}>
          重新执行
        </Button>
        {!Number.isNaN(Number(executionId)) ? (
          <Button onClick={() => navigate(`/operations/executions/${executionId}`)}>
            查看执行中心记录
          </Button>
        ) : null}
      </Space>

      <Card title="场景执行详情">
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <h3>执行概览</h3>
            <Space size="large" wrap>
              <span>场景: {scenario?.name || '-'}</span>
              <span>执行 ID: {executionId}</span>
              <Tag color={displayStatus === 'completed' ? 'success' : isRunning ? 'processing' : 'error'}>
                {displayStatus}
              </Tag>
            </Space>
            <div style={{ marginTop: 16 }}>
              <Progress
                percent={progressPercent}
                status={isRunning ? 'active' : failedCount > 0 ? 'exception' : 'success'}
                format={() => (isRunning ? `${progressPercent}%` : `${successCount}/${totalCount} 通过`)}
              />
            </div>
            {isRunning && taskStatus?.progress_message && (
              <Text type="secondary">{taskStatus.progress_message}</Text>
            )}
            {execution?.summary && (
              <div style={{ marginTop: 8 }}>
                <Space>
                  <span>总耗时: {execution.summary.duration_ms}ms</span>
                  <span>成功: {execution.summary.passed}</span>
                  <span>失败: {execution.summary.failed}</span>
                  <span>跳过: {execution.summary.skipped}</span>
                </Space>
              </div>
            )}
            {isRunning && taskStatus?.stages && taskStatus.stages.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <Steps
                  direction="vertical"
                  size="small"
                  current={Math.max(taskStatus.stages.findIndex((stage) => stage.status === 'running'), 0)}
                  items={taskStatus.stages.map((stage) => ({
                    key: stage.key,
                    title: stage.name,
                    description: stage.description || undefined,
                    status: mapStepStatus(stage.status),
                  }))}
                />
              </div>
            )}
            {execution?.error_message && (
              <Alert style={{ marginTop: 12 }} type="error" showIcon message="执行失败" description={execution.error_message} />
            )}
          </div>

          <div>
            <h3>执行时间线</h3>
            {results.length > 0 ? (
              <Timeline
                items={results.map((result) => ({
                  color: result.status === 'passed' ? 'green' : 'red',
                  children: (
                    <div className="execution-item">
                      <div className="execution-item-header">
                        <Space>
                          <Tag color={result.status === 'passed' ? 'success' : 'error'}>{result.status}</Tag>
                          <strong>{renderNodeTitle(result)}</strong>
                        </Space>
                        <Text type="secondary">耗时: {result.response_time ?? 0}ms</Text>
                      </div>
                      <div className="execution-item-details">
                        {result.request_body !== undefined && result.request_body !== null && (
                          <div>
                            <strong>请求:</strong>
                            <pre>{JSON.stringify(result.request_body, null, 2)}</pre>
                          </div>
                        )}
                        {result.response_body !== undefined && result.response_body !== null && (
                          <div>
                            <strong>响应:</strong>
                            <pre>{JSON.stringify(result.response_body, null, 2)}</pre>
                          </div>
                        )}
                        {result.assertion_results !== undefined && result.assertion_results !== null && (
                          <div>
                            <strong>断言:</strong>
                            <pre>{JSON.stringify(result.assertion_results, null, 2)}</pre>
                          </div>
                        )}
                        {result.extracted_variables && Object.keys(result.extracted_variables).length > 0 && (
                          <div>
                            <strong>提取变量:</strong>
                            <pre>{JSON.stringify(result.extracted_variables, null, 2)}</pre>
                          </div>
                        )}
                        {result.error_message && (
                          <Alert
                            message="错误信息"
                            description={result.error_message}
                            type="error"
                            showIcon
                            style={{ marginTop: 8 }}
                          />
                        )}
                      </div>
                    </div>
                  ),
                }))}
              />
            ) : (
              <div className="workspace-inline-note">
                {isRunning ? '执行中，等待节点结果回传。' : '暂无节点执行结果。'}
              </div>
            )}
          </div>
        </Space>
      </Card>
    </div>
  )
}

export default ScenarioExecution

