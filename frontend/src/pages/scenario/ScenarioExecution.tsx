import React, { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Input,
  Modal,
  Space,
  Spin,
  Table,
  Tooltip,
  Typography,
  message,
} from 'antd'
import {
  ArrowLeftOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  QuestionCircleOutlined,
  RedoOutlined,
  RobotOutlined,
  SendOutlined,
} from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import './ScenarioExecution.css'
import { getScenario } from '../../services/scenario'
import {
  analyzeScenarioFailure,
  continueFromScenarioNode,
  createScenarioRun,
  getScenarioRun,
  getScenarioRunContext,
  getScenarioRunNodes,
  pauseScenarioRun,
  rerunScenarioNode,
  resumeScenarioRun,
  signalScenarioRun,
} from '../../services/scenarioRuns'
import type {
  ScenarioDetail,
  ScenarioFailureRcaResult,
  ScenarioNodeAttempt,
  ScenarioNodeRun,
  ScenarioRun,
  ScenarioRunContext,
} from '../../types/scenario'
import ScenarioStatusTag from '../../components/scenario/ScenarioStatusTag'

const { Text, Paragraph } = Typography
const { TextArea } = Input

const runtimeLabelMap: Record<string, string> = {
  local: '本地执行器',
  temporal: 'Temporal 持久化工作流',
}

const nodeTypeLabelMap: Record<string, string> = {
  api_call: 'API 调用',
  condition: '条件判断',
  wait: '等待/轮询',
  script: '脚本处理',
}

const hintLabel = (label: string, hint: string) => (
  <Space size={4}>
    <span>{label}</span>
    <Tooltip title={hint}>
      <QuestionCircleOutlined />
    </Tooltip>
  </Space>
)

const formatJson = (value: unknown) => JSON.stringify(value ?? {}, null, 2)

const ScenarioExecution: React.FC = () => {
  const navigate = useNavigate()
  const { scenarioId, executionId } = useParams()
  const runId = Number(executionId)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [run, setRun] = useState<ScenarioRun | null>(null)
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null)
  const [runContext, setRunContext] = useState<ScenarioRunContext | null>(null)
  const [nodeRuns, setNodeRuns] = useState<ScenarioNodeRun[]>([])
  const [failureRca, setFailureRca] = useState<ScenarioFailureRcaResult | null>(null)
  const [signalModalVisible, setSignalModalVisible] = useState(false)
  const [signalName, setSignalName] = useState('approve')
  const [signalPayload, setSignalPayload] = useState('{}')

  const loadScenario = useCallback(async () => {
    if (!scenarioId) return
    try {
      const detail = await getScenario(Number(scenarioId))
      setScenario(detail)
    } catch (error) {
      console.error('加载场景失败:', error)
    }
  }, [scenarioId])

  const loadRun = useCallback(async () => {
    if (Number.isNaN(runId)) return
    const detail = await getScenarioRun(runId)
    setRun(detail)
  }, [runId])

  const loadRunContext = useCallback(async () => {
    if (Number.isNaN(runId)) return
    try {
      const detail = await getScenarioRunContext(runId)
      setRunContext(detail)
    } catch (error) {
      console.error('加载运行上下文失败:', error)
      setRunContext(null)
    }
  }, [runId])

  const loadNodeRuns = useCallback(async () => {
    if (Number.isNaN(runId)) return
    try {
      const detail = await getScenarioRunNodes(runId)
      setNodeRuns(detail.items || [])
    } catch (error) {
      console.error('加载节点运行记录失败:', error)
      setNodeRuns([])
    }
  }, [runId])

  const loadAll = useCallback(async () => {
    if (Number.isNaN(runId)) return
    setLoading(true)
    try {
      await Promise.all([loadScenario(), loadRun(), loadRunContext(), loadNodeRuns()])
    } catch (error: any) {
      message.error(error.message || '加载运行详情失败')
    } finally {
      setLoading(false)
    }
  }, [loadNodeRuns, loadRun, loadRunContext, loadScenario, runId])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    if (!run || !['pending', 'running'].includes(run.status)) return undefined
    const timer = setInterval(() => {
      void loadRun()
      void loadNodeRuns()
    }, 3000)
    return () => clearInterval(timer)
  }, [loadNodeRuns, loadRun, run])

  const handleRerunWholeScenario = async () => {
    if (!scenarioId || !scenario?.environment_id) {
      message.warning('当前场景没有默认环境，暂时无法整次重跑')
      return
    }
    setActionLoading(true)
    try {
      const nextRun = await createScenarioRun({
        scenario_id: Number(scenarioId),
        revision_id: run?.revision_id ?? undefined,
        environment_id: scenario.environment_id,
      })
      message.success('已提交新的场景运行')
      navigate(`/scenario/${scenarioId}/execution/${nextRun.run_id}`)
    } catch (error: any) {
      message.error(error.message || '重新运行失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handleNodeAction = async (type: 'rerun' | 'continue', nodeKey: string) => {
    if (Number.isNaN(runId)) return
    setActionLoading(true)
    try {
      const action = type === 'rerun' ? rerunScenarioNode : continueFromScenarioNode
      const result = await action(runId, { node_key: nodeKey })
      message.success(type === 'rerun' ? '节点重跑已提交' : '续跑已提交')
      navigate(`/scenario/${scenarioId}/execution/${result.new_run_id}`)
    } catch (error: any) {
      message.error(error.message || '节点操作失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handlePause = async () => {
    if (Number.isNaN(runId)) return
    setActionLoading(true)
    try {
      await pauseScenarioRun(runId)
      message.success('运行已暂停')
      await loadRun()
    } catch (error: any) {
      message.error(error.message || '暂停运行失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handleResume = async () => {
    if (Number.isNaN(runId)) return
    setActionLoading(true)
    try {
      await resumeScenarioRun(runId)
      message.success('运行已恢复')
      await loadRun()
    } catch (error: any) {
      message.error(error.message || '恢复运行失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handleSignal = async () => {
    if (Number.isNaN(runId)) return
    setActionLoading(true)
    try {
      await signalScenarioRun(runId, {
        signal_name: signalName.trim(),
        payload: signalPayload.trim() ? JSON.parse(signalPayload) : {},
      })
      message.success('控制信号已发送')
      setSignalModalVisible(false)
    } catch (error: any) {
      message.error(error.message || '发送控制信号失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handleAnalyzeFailure = async () => {
    if (Number.isNaN(runId)) return
    setActionLoading(true)
    try {
      const result = await analyzeScenarioFailure(runId)
      setFailureRca(result)
      message.success('失败分析已完成')
    } catch (error: any) {
      message.error(error.message || '失败分析失败')
    } finally {
      setActionLoading(false)
    }
  }

  const isTemporal = run?.runtime_type === 'temporal'
  const runSummary = run?.summary || {}
  const nodeRunCount = nodeRuns.length
  const failedNodeCount = nodeRuns.filter((item) => item.status !== 'passed' && item.status !== 'completed').length

  if (loading && !run) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (!run || Number.isNaN(runId)) {
    return (
      <div style={{ padding: 24 }}>
        <Empty description="未找到运行记录" />
      </div>
    )
  }

  return (
    <div className="scenario-execution">
      <Space style={{ marginBottom: 24 }} wrap>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/scenario/${scenarioId}`)}>
          返回场景
        </Button>
        <Button icon={<RedoOutlined />} onClick={() => void handleRerunWholeScenario()} loading={actionLoading}>
          重新运行整次
        </Button>
        {isTemporal ? (
          <>
            <Button icon={<PauseCircleOutlined />} onClick={() => void handlePause()} loading={actionLoading}>
              暂停
            </Button>
            <Button icon={<PlayCircleOutlined />} onClick={() => void handleResume()} loading={actionLoading}>
              恢复
            </Button>
            <Button icon={<SendOutlined />} onClick={() => setSignalModalVisible(true)}>
              发送控制信号
            </Button>
          </>
        ) : null}
        <Button icon={<RobotOutlined />} onClick={() => void handleAnalyzeFailure()} loading={actionLoading}>
          AI 失败分析
        </Button>
      </Space>

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title="运行概览">
          <Descriptions bordered column={2}>
            <Descriptions.Item label="运行 ID">{run.run_id}</Descriptions.Item>
            <Descriptions.Item label="场景 ID">{run.scenario_id}</Descriptions.Item>
            <Descriptions.Item label="场景名称">{scenario?.name || '-'}</Descriptions.Item>
            <Descriptions.Item label={hintLabel('版本快照 ID', '本次运行绑定的版本快照。')}>{run.revision_id ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="运行状态"><ScenarioStatusTag status={run.status} /></Descriptions.Item>
            <Descriptions.Item label="结果状态"><ScenarioStatusTag status={run.result_status || '-'} /></Descriptions.Item>
            <Descriptions.Item label={hintLabel('运行时', '本地执行器用于快速执行，Temporal 用于持久化工作流运行。')}>
              {run.runtime_type ? runtimeLabelMap[run.runtime_type] || run.runtime_type : '-'}
            </Descriptions.Item>
            <Descriptions.Item label={hintLabel('工作流 ID', 'Temporal 运行时中的工作流标识。')}>
              {run.temporal_workflow_id || '-'}
            </Descriptions.Item>
            <Descriptions.Item label={hintLabel('运行实例 ID', 'Temporal 运行时中的本次执行实例标识。')}>
              {run.temporal_run_id || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="节点数">{nodeRunCount}</Descriptions.Item>
            <Descriptions.Item label="失败节点数">{failedNodeCount}</Descriptions.Item>
            <Descriptions.Item label="总耗时">{String(runSummary.duration_ms ?? '-')} ms</Descriptions.Item>
            <Descriptions.Item label="通过 / 失败">
              {String(runSummary.passed ?? 0)} / {String(runSummary.failed ?? 0)}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        <Card title={hintLabel('运行上下文', '展示本次运行的输入上下文和解析后的上下文。')}>
          {runContext ? (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <div>
                <Text strong>输入上下文</Text>
                <pre>{formatJson(runContext.input_context)}</pre>
              </div>
              <div>
                <Text strong>解析后上下文</Text>
                <pre>{formatJson(runContext.resolved_context)}</pre>
              </div>
            </Space>
          ) : (
            <Empty description="暂无运行上下文" />
          )}
        </Card>

        {failureRca ? (
          <Alert
            type="warning"
            showIcon
            message="AI 失败分析"
            description={(
              <Space direction="vertical" size={4}>
                <Text>失败类型：{failureRca.failure_type || '-'}</Text>
                <Paragraph style={{ marginBottom: 0 }}>根因：{failureRca.root_cause || '-'}</Paragraph>
                <Paragraph style={{ marginBottom: 0 }}>建议修复：{failureRca.suggested_fix || '-'}</Paragraph>
                <Text type="secondary">置信度：{failureRca.confidence ?? '-'}</Text>
              </Space>
            )}
          />
        ) : null}

        <Card title="节点运行记录">
          <Table<ScenarioNodeRun>
            rowKey="node_key"
            dataSource={nodeRuns}
            pagination={false}
            locale={{ emptyText: '暂无节点运行数据' }}
            expandable={{
              expandedRowRender: (record) => (
                <Table<ScenarioNodeAttempt>
                  rowKey={(attempt) => `${record.node_key}-${attempt.attempt}-${attempt.id ?? 'local'}`}
                  dataSource={record.attempts}
                  pagination={false}
                  size="small"
                  columns={[
                    {
                      title: hintLabel('尝试序号', '每一次重试都会形成一条独立的尝试记录。'),
                      dataIndex: 'attempt',
                      key: 'attempt',
                      width: 120,
                    },
                    {
                      title: '状态',
                      dataIndex: 'status',
                      key: 'status',
                      width: 110,
                      render: (value: string) => <ScenarioStatusTag status={value} />,
                    },
                    { title: '响应码', dataIndex: 'response_code', key: 'response_code', width: 100 },
                    { title: '耗时(ms)', dataIndex: 'response_time', key: 'response_time', width: 110 },
                    {
                      title: '错误信息',
                      dataIndex: 'error_message',
                      key: 'error_message',
                      render: (value?: string | null) => value || '-',
                    },
                  ]}
                  summary={() => (
                    <>
                      {record.attempts.map((attempt) => (
                        <tr key={`detail-${record.node_key}-${attempt.attempt}`}>
                          <td colSpan={5} style={{ padding: 12, background: '#fafafa' }}>
                            <Space direction="vertical" style={{ width: '100%' }} size="middle">
                              <div>
                                <Text strong>输入快照</Text>
                                <pre>{formatJson(attempt.input_snapshot)}</pre>
                              </div>
                              <div>
                                <Text strong>输出快照</Text>
                                <pre>{formatJson(attempt.output_snapshot)}</pre>
                              </div>
                              <div>
                                <Text strong>引用解析快照</Text>
                                <pre>{formatJson(attempt.resolved_ref_snapshot)}</pre>
                              </div>
                            </Space>
                          </td>
                        </tr>
                      ))}
                    </>
                  )}
                />
              ),
            }}
            columns={[
              { title: '节点标识', dataIndex: 'node_key', key: 'node_key' },
              {
                title: '节点类型',
                dataIndex: 'node_type',
                key: 'node_type',
                width: 120,
                render: (value: string) => nodeTypeLabelMap[value] || value,
              },
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                width: 120,
                render: (value: string) => <ScenarioStatusTag status={value} />,
              },
              {
                title: hintLabel('最终尝试', '该节点最终一次执行对应的重试序号。'),
                dataIndex: 'attempt',
                key: 'attempt',
                width: 120,
              },
              {
                title: '错误信息',
                dataIndex: 'error_message',
                key: 'error_message',
                render: (value?: string | null) => value || '-',
              },
              {
                title: '操作',
                key: 'actions',
                width: 220,
                render: (_, record) => (
                  <Space>
                    <Button size="small" onClick={() => void handleNodeAction('rerun', record.node_key)} loading={actionLoading}>
                      重跑节点
                    </Button>
                    <Button size="small" type="link" onClick={() => void handleNodeAction('continue', record.node_key)} loading={actionLoading}>
                      从此续跑
                    </Button>
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      </Space>

      <Modal
        title={hintLabel('发送控制信号', '向 Temporal 工作流发送外部控制事件，例如审批、放行或继续执行。')}
        open={signalModalVisible}
        onOk={() => void handleSignal()}
        onCancel={() => setSignalModalVisible(false)}
        confirmLoading={actionLoading}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input value={signalName} onChange={(event) => setSignalName(event.target.value)} placeholder="请输入信号名称" />
          <TextArea value={signalPayload} onChange={(event) => setSignalPayload(event.target.value)} rows={6} />
        </Space>
      </Modal>
    </div>
  )
}

export default ScenarioExecution
