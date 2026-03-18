import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  Select,
  Space,
  Switch,
  Tabs,
  Typography,
  message,
} from 'antd'
import { DownloadOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import { useProjectStore } from '../../store/project'
import { useAuthStore } from '../../store/auth'
import {
  analyzeAiFailure,
  generateAiAssertions,
  generateAiScenarioDraft,
  generateAiTest,
  getExecutionRca,
  getExecutionReportSummary,
  getProjectScenarios,
  getScenarioExecutions,
  getTriggerResult,
  mapAiVariables,
  optimizeAiTests,
  runAiFullFlow,
  triggerScenario,
  type ScenarioExecutionSummary,
  type ScenarioSummary,
} from '../../services/operations'
import { getProjectEnvironments } from '../../services/environments'

const { TextArea } = Input
const { Text } = Typography

const prettyJson = (value: unknown) => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return '{}'
  }
}

const parseJsonObject = (value: string) => {
  if (!value.trim()) {
    return {}
  }

  const parsed = JSON.parse(value)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('JSON payload must be an object')
  }

  return parsed as Record<string, any>
}

const downloadBlob = (content: Blob, filename: string) => {
  const url = window.URL.createObjectURL(content)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

const OperationsCenter = () => {
  const { currentProject } = useProjectStore()
  const authState = useAuthStore()
  const projectId = currentProject?.id

  const [scenarioList, setScenarioList] = useState<ScenarioSummary[]>([])
  const [environmentList, setEnvironmentList] = useState<any[]>([])
  const [scenarioLoading, setScenarioLoading] = useState(false)
  const [selectedScenarioId, setSelectedScenarioId] = useState<number | null>(null)
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState<number | null>(null)
  const [executionList, setExecutionList] = useState<ScenarioExecutionSummary[]>([])
  const [selectedExecutionId, setSelectedExecutionId] = useState<number | null>(null)
  const [reportSummary, setReportSummary] = useState<Record<string, any> | null>(null)
  const [reportRca, setReportRca] = useState<Record<string, any> | null>(null)
  const [triggerResult, setTriggerResult] = useState<Record<string, any> | null>(null)
  const [aiResult, setAiResult] = useState<Record<string, any> | null>(null)
  const [loadingState, setLoadingState] = useState<'trigger' | 'report' | 'ai' | null>(null)

  const [triggerForm] = Form.useForm()
  const [reportForm] = Form.useForm()
  const [aiForm] = Form.useForm()

  const selectedScenario = useMemo(
    () => scenarioList.find((item) => item.id === selectedScenarioId) || null,
    [scenarioList, selectedScenarioId],
  )
  const selectedExecution = useMemo(
    () => executionList.find((item) => item.id === selectedExecutionId) || null,
    [executionList, selectedExecutionId],
  )
  const selectedEnvironment = useMemo(
    () => environmentList.find((item) => item.id === selectedEnvironmentId) || null,
    [environmentList, selectedEnvironmentId],
  )

  const loadProjectData = async () => {
    if (!projectId) {
      setScenarioList([])
      setEnvironmentList([])
      setSelectedScenarioId(null)
      setSelectedEnvironmentId(null)
      return
    }

    setScenarioLoading(true)
    try {
      const [scenarioResponse, environmentResponse] = await Promise.all([
        getProjectScenarios(projectId, 200),
        getProjectEnvironments(projectId, 1, 100),
      ])

      const scenarios = scenarioResponse.items || []
      const environments = environmentResponse.items || []

      setScenarioList(scenarios)
      setEnvironmentList(environments)

      setSelectedScenarioId((current) => {
        if (current && scenarios.some((item) => item.id === current)) {
          return current
        }
        return scenarios[0]?.id ?? null
      })

      setSelectedEnvironmentId((current) => {
        if (current && environments.some((item) => item.id === current)) {
          return current
        }
        const defaultEnv = environments.find((item) => item.is_default) || environments[0]
        return defaultEnv?.id ?? null
      })
    } catch (error: any) {
      message.error(error.message || 'Failed to load operations data')
      setScenarioList([])
      setEnvironmentList([])
    } finally {
      setScenarioLoading(false)
    }
  }

  const loadExecutions = async (scenarioId: number | null) => {
    if (!scenarioId) {
      setExecutionList([])
      setSelectedExecutionId(null)
      setReportSummary(null)
      setReportRca(null)
      return
    }

    try {
      const response = await getScenarioExecutions(scenarioId, undefined, 50)
      const items = response.items || []
      setExecutionList(items)
      setSelectedExecutionId((current) => {
        if (current && items.some((item) => item.id === current)) {
          return current
        }
        return items[0]?.id ?? null
      })
    } catch (error: any) {
      message.error(error.message || 'Failed to load executions')
      setExecutionList([])
      setSelectedExecutionId(null)
    }
  }

  const loadReportContext = async (scenarioId: number | null, executionId: number | null) => {
    if (!scenarioId || !executionId) {
      setReportSummary(null)
      setReportRca(null)
      return
    }

    try {
      setLoadingState('report')
      const [summary, rca] = await Promise.all([
        getExecutionReportSummary(scenarioId, executionId),
        getExecutionRca(scenarioId, executionId),
      ])
      setReportSummary(summary || null)
      setReportRca(rca || null)
    } catch (error: any) {
      message.error(error.message || 'Failed to load report summary')
      setReportSummary(null)
      setReportRca(null)
    } finally {
      setLoadingState(null)
    }
  }

  useEffect(() => {
    void loadProjectData()
  }, [projectId])

  useEffect(() => {
    void loadExecutions(selectedScenarioId)
  }, [selectedScenarioId])

  useEffect(() => {
    void loadReportContext(selectedScenarioId, selectedExecutionId)
  }, [selectedScenarioId, selectedExecutionId])

  const handleTriggerScenario = async () => {
    if (!selectedScenarioId || !selectedEnvironmentId) {
      message.warning('Select a scenario and environment first')
      return
    }

    try {
      const values = await triggerForm.validateFields()
      setLoadingState('trigger')
      const response = await triggerScenario(selectedScenarioId, {
        environment_id: selectedEnvironmentId,
        async_mode: !!values.async_mode,
        callback_url: values.callback_url || null,
      })
      setTriggerResult(response.data || null)
      if (response.data?.execution_id) {
        setSelectedExecutionId(response.data.execution_id)
      }
      message.success(response.message || 'Scenario triggered')
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }
      message.error(error.message || 'Failed to trigger scenario')
    } finally {
      setLoadingState(null)
    }
  }

  const refreshTriggerResult = async () => {
    if (!selectedScenarioId || !selectedExecutionId) {
      return
    }

    try {
      setLoadingState('trigger')
      const response = await getTriggerResult(selectedScenarioId, selectedExecutionId)
      setTriggerResult(response.data || null)
    } catch (error: any) {
      message.error(error.message || 'Failed to load trigger result')
    } finally {
      setLoadingState(null)
    }
  }

  const downloadReport = async (format: 'html' | 'pdf') => {
    if (!selectedScenarioId || !selectedExecutionId) {
      message.warning('Select a scenario execution first')
      return
    }

    try {
      const token = authState.token || localStorage.getItem('token')
      const includeRca = reportForm.getFieldValue('include_rca')
      const response = await fetch(
        `/api/v1/scenarios/${selectedScenarioId}/executions/${selectedExecutionId}/report?format=${format}&include_rca=${includeRca !== false}`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        },
      )
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const blob = await response.blob()
      downloadBlob(blob, `scenario_${selectedScenarioId}_execution_${selectedExecutionId}.${format}`)
    } catch (error: any) {
      message.error(error.message || 'Failed to download report')
    }
  }

  const runAiAction = async (action: string, executor: () => Promise<any>) => {
    try {
      setLoadingState('ai')
      const response = await executor()
      setAiResult({
        action,
        response: response?.data ?? response,
      })
      message.success(`${action} completed`)
    } catch (error: any) {
      message.error(error.message || `${action} failed`)
    } finally {
      setLoadingState(null)
    }
  }

  const onGenerateScenario = async () => {
    const values = await aiForm.validateFields()
    await runAiAction('Generate scenario', () =>
      generateAiScenarioDraft(projectId!, values.intent_text, !!values.save_draft),
    )
  }

  const onGenerateTest = async () => {
    const values = await aiForm.validateFields()
    const inputData = parseJsonObject(values.json_payload)
    await runAiAction('Generate test', () => generateAiTest(projectId!, inputData))
  }

  const onAnalyzeFailure = async () => {
    const values = await aiForm.validateFields()
    const inputData = parseJsonObject(values.json_payload)
    await runAiAction('Analyze failure', () => analyzeAiFailure(projectId!, inputData))
  }

  const onGenerateAssertions = async () => {
    const values = await aiForm.validateFields()
    const inputData = parseJsonObject(values.json_payload)
    await runAiAction('Generate assertions', () => generateAiAssertions(projectId!, inputData))
  }

  const onMapVariables = async () => {
    const values = await aiForm.validateFields()
    const inputData = parseJsonObject(values.json_payload)
    await runAiAction('Map variables', () => mapAiVariables(projectId!, inputData))
  }

  const onRunFull = async () => {
    const values = await aiForm.validateFields()
    await runAiAction('Run full flow', () =>
      runAiFullFlow(projectId!, values.intent_text, values.environment_id || null, !!values.auto_fix),
    )
  }

  const onOptimize = async () => {
    const values = await aiForm.validateFields()
    const inputData = parseJsonObject(values.json_payload)
    await runAiAction('Optimize tests', () => optimizeAiTests(inputData))
  }

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow="Operations"
        title="Report, Trigger, and AI Testing"
        description="Operate the real scenario report, execution trigger, and AI testing endpoints from one workspace."
        metrics={[
          { label: 'Scenarios', value: scenarioList.length },
          { label: 'Environments', value: environmentList.length },
          { label: 'Selected scenario', value: selectedScenario?.name || '-' },
          { label: 'Selected environment', value: selectedEnvironment?.name || '-' },
          { label: 'Selected execution', value: selectedExecution?.id || '-' },
        ]}
        actions={
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => void loadProjectData()} loading={scenarioLoading}>
              Refresh
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => void handleTriggerScenario()}
              loading={loadingState === 'trigger'}
              disabled={!selectedScenarioId || !selectedEnvironmentId}
            >
              Trigger
            </Button>
          </Space>
        }
      />

      {!projectId ? <Alert type="warning" showIcon message="Select a project first" /> : null}

      <Card>
        <Tabs
          items={[
            {
              key: 'trigger',
              label: 'Trigger',
              children: (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <Descriptions column={1} bordered size="small">
                    <Descriptions.Item label="Scenario">
                      <Select
                        style={{ width: 360 }}
                        loading={scenarioLoading}
                        value={selectedScenarioId ?? undefined}
                        onChange={(value) => setSelectedScenarioId(value)}
                        options={scenarioList.map((item) => ({
                          value: item.id,
                          label: `${item.name} #${item.id}`,
                        }))}
                        placeholder="Select scenario"
                      />
                    </Descriptions.Item>
                    <Descriptions.Item label="Environment">
                      <Select
                        style={{ width: 360 }}
                        value={selectedEnvironmentId ?? undefined}
                        onChange={(value) => setSelectedEnvironmentId(value)}
                        options={environmentList.map((item) => ({
                          value: item.id,
                          label: item.is_default ? `${item.name} (default)` : item.name,
                        }))}
                        placeholder="Select environment"
                      />
                    </Descriptions.Item>
                  </Descriptions>
                  <Form form={triggerForm} layout="vertical">
                    <Form.Item name="async_mode" label="Async mode" valuePropName="checked" initialValue={false}>
                      <Switch />
                    </Form.Item>
                    <Form.Item name="callback_url" label="Callback URL">
                      <Input placeholder="https://callback.example.com" />
                    </Form.Item>
                  </Form>

                  <Card size="small" title="Latest trigger result" extra={<Button onClick={() => void refreshTriggerResult()}>Refresh result</Button>}>
                    {triggerResult ? <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{prettyJson(triggerResult)}</pre> : <Empty description="No trigger result yet" />}
                  </Card>
                </Space>
              ),
            },
            {
              key: 'report',
              label: 'Reports',
              children: (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <Descriptions column={1} bordered size="small">
                    <Descriptions.Item label="Scenario">
                      <Select
                        style={{ width: 360 }}
                        value={selectedScenarioId ?? undefined}
                        onChange={(value) => setSelectedScenarioId(value)}
                        options={scenarioList.map((item) => ({
                          value: item.id,
                          label: `${item.name} #${item.id}`,
                        }))}
                        placeholder="Select scenario"
                      />
                    </Descriptions.Item>
                    <Descriptions.Item label="Execution">
                      <Select
                        style={{ width: 360 }}
                        value={selectedExecutionId ?? undefined}
                        onChange={(value) => setSelectedExecutionId(value)}
                        options={executionList.map((item) => ({
                          value: item.id,
                          label: `${item.id} - ${item.status}`,
                        }))}
                        placeholder="Select execution"
                      />
                    </Descriptions.Item>
                  </Descriptions>

                  <Form form={reportForm} layout="inline">
                    <Form.Item name="include_rca" valuePropName="checked" initialValue={true} label="Include RCA">
                      <Switch />
                    </Form.Item>
                  </Form>

                  <Space wrap>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={() => void loadReportContext(selectedScenarioId, selectedExecutionId)}
                      loading={loadingState === 'report'}
                    >
                      Refresh summary
                    </Button>
                    <Button icon={<DownloadOutlined />} onClick={() => void downloadReport('html')}>
                      Download HTML
                    </Button>
                    <Button icon={<DownloadOutlined />} onClick={() => void downloadReport('pdf')}>
                      Download PDF
                    </Button>
                  </Space>

                  <Card size="small" title="Summary">
                    {reportSummary ? <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{prettyJson(reportSummary)}</pre> : <Empty description="No summary" />}
                  </Card>
                  <Card size="small" title="RCA">
                    {reportRca ? <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{prettyJson(reportRca)}</pre> : <Empty description="No RCA result" />}
                  </Card>
                </Space>
              ),
            },
            {
              key: 'ai',
              label: 'AI Testing',
              children: (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <Form form={aiForm} layout="vertical" initialValues={{ save_draft: false, auto_fix: false }}>
                    <Form.Item name="intent_text" label="Intent text">
                      <TextArea rows={3} />
                    </Form.Item>
                    <Form.Item name="json_payload" label="JSON payload">
                      <TextArea rows={10} spellCheck={false} />
                    </Form.Item>
                    <Space wrap>
                      <Form.Item name="save_draft" valuePropName="checked" style={{ marginBottom: 0 }}>
                        <Switch />
                      </Form.Item>
                      <Text>Save draft</Text>
                      <Form.Item name="auto_fix" valuePropName="checked" style={{ marginBottom: 0, marginLeft: 16 }}>
                        <Switch />
                      </Form.Item>
                      <Text>Auto fix</Text>
                      <Form.Item name="environment_id" label="Environment" style={{ minWidth: 280, marginBottom: 0, marginLeft: 16 }}>
                        <Select
                          style={{ minWidth: 280 }}
                          allowClear
                          placeholder="Optional environment"
                          options={environmentList.map((item) => ({
                            value: item.id,
                            label: item.is_default ? `${item.name} (default)` : item.name,
                          }))}
                        />
                      </Form.Item>
                    </Space>
                  </Form>

                  <Space wrap>
                    <Button loading={loadingState === 'ai'} onClick={() => void onGenerateScenario()}>
                      Generate scenario
                    </Button>
                    <Button loading={loadingState === 'ai'} onClick={() => void onGenerateTest()}>
                      Generate test
                    </Button>
                    <Button loading={loadingState === 'ai'} onClick={() => void onAnalyzeFailure()}>
                      Analyze failure
                    </Button>
                    <Button loading={loadingState === 'ai'} onClick={() => void onGenerateAssertions()}>
                      Generate assertions
                    </Button>
                    <Button loading={loadingState === 'ai'} onClick={() => void onMapVariables()}>
                      Map variables
                    </Button>
                    <Button loading={loadingState === 'ai'} onClick={() => void onRunFull()}>
                      Run full
                    </Button>
                    <Button loading={loadingState === 'ai'} onClick={() => void onOptimize()}>
                      Optimize
                    </Button>
                  </Space>

                  <Card size="small" title="Latest AI response">
                    {aiResult ? <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{prettyJson(aiResult)}</pre> : <Empty description="No AI response yet" />}
                  </Card>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}

export default OperationsCenter
