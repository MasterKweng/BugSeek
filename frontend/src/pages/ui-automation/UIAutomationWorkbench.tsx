import React, { useMemo, useState } from 'react'
import { Alert, Button, Card, Col, Divider, Empty, Input, Row, Space, Switch, Table, Tag, Typography, message } from 'antd'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'

import { createUIExecution, getUIExecution, type UIExecutionSummary } from '../../services/uiAutomation'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import { useAppPreferences } from '../../preferences/AppPreferencesProvider'
import { useProjectStore } from '../../store/project'
import './UIAutomationWorkbench.css'

const { Paragraph, Text, Title } = Typography
const { TextArea } = Input

const UIAutomationWorkbench: React.FC = () => {
  const { t } = useAppPreferences()
  const { currentProject } = useProjectStore()
  const tm = (key: string, fallback: string, variables?: Record<string, string | number>) =>
    t(`uiAutomationWorkbench.${key}`, fallback, variables)

  const [caseName, setCaseName] = useState('')
  const [startUrl, setStartUrl] = useState('')
  const [headless, setHeadless] = useState(true)
  const [stepsText, setStepsText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UIExecutionSummary | null>(null)
  const [lastExecutionId, setLastExecutionId] = useState<number | null>(null)

  const parsedSteps = useMemo(() => {
    try {
      return JSON.parse(stepsText)
    } catch {
      return null
    }
  }, [stepsText])

  const handleRun = async () => {
    if (!currentProject?.id) {
      message.error(tm('messages.selectProjectFirst', 'Please select a project first'))
      return
    }
    if (!caseName.trim()) {
      message.error(tm('messages.enterExecutionName', 'Please enter an execution name'))
      return
    }
    if (!startUrl.trim()) {
      message.error(tm('messages.enterStartUrl', 'Please enter a start URL'))
      return
    }
    if (!parsedSteps || !Array.isArray(parsedSteps) || parsedSteps.length === 0) {
      message.error(tm('messages.invalidStepsJson', 'Invalid steps JSON'))
      return
    }

    setLoading(true)
    try {
      const response = await createUIExecution(currentProject.id, {
        name: caseName.trim(),
        start_url: startUrl.trim(),
        steps: parsedSteps,
        headless,
      })
      setResult(response.data)
      setLastExecutionId(response.data.execution_id)
      message.success(
        tm('messages.executionCompleted', 'Execution completed, record #{executionId}', {
          executionId: response.data.execution_id,
        }),
      )
    } catch (error: any) {
      message.error(error?.message || tm('messages.executionFailed', 'UI automation execution failed'))
    } finally {
      setLoading(false)
    }
  }

  const handleReload = async () => {
    if (!currentProject?.id || !lastExecutionId) {
      return
    }
    setLoading(true)
    try {
      const response = await getUIExecution(currentProject.id, lastExecutionId)
      setResult(response.data)
    } catch (error: any) {
      message.error(error?.message || tm('messages.loadExecutionResultFailed', 'Failed to load execution result'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="ui-automation-page governance-stack">
      <WorkspaceModuleHero
        eyebrow={tm('hero.eyebrow', 'Automation')}
        title={tm('hero.title', 'UI Execution Workbench')}
        description={tm('hero.description', 'Submit executions through the real UI Testing API and inspect the result stream.')}
        metrics={[
          { label: tm('metrics.latestExecution', 'Latest execution'), value: lastExecutionId || '-' },
          { label: tm('metrics.executionStatus', 'Execution status'), value: result?.status || '-' },
          { label: tm('metrics.stepsPassed', 'Steps passed'), value: result ? `${result.passed_steps}/${result.total_steps}` : '-' },
        ]}
      />
      <Card className="ui-automation-hero" bordered={false}>
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Tag color="cyan">{tm('hero.tag', 'UI Automation')}</Tag>
          <Title level={2} style={{ margin: 0 }}>
            {tm('hero.title', 'UI Execution Workbench')}
          </Title>
          <Paragraph className="ui-automation-copy">
            {tm('hero.note', 'This page only calls the real ui-testing execution endpoint. Fill in the execution name, start URL, and steps JSON, then submit the run.')}
          </Paragraph>
          {!currentProject?.id && <Alert type="warning" showIcon message={tm('messages.noProjectContext', 'No project context is selected. Choose a project from the top bar before running.')} />}
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title={tm('cards.executionInput', 'Execution Input')} className="ui-automation-card">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Input value={caseName} onChange={(event) => setCaseName(event.target.value)} placeholder={tm('placeholders.caseName', 'Case name')} />
              <Input value={startUrl} onChange={(event) => setStartUrl(event.target.value)} placeholder={tm('placeholders.startUrl', 'Start URL')} />
              <div className="ui-automation-switch-row">
                <Text>{tm('labels.headless', 'Headless')}</Text>
                <Switch checked={headless} onChange={setHeadless} />
              </div>
              <TextArea
                value={stepsText}
                onChange={(event) => setStepsText(event.target.value)}
                autoSize={{ minRows: 14, maxRows: 22 }}
                placeholder={tm('placeholders.stepsJson', '[{"name":"Open home","action":"goto","value":"https://your-app"}]')}
              />
              <div className="ui-automation-actions">
                <Button type="primary" icon={<PlayCircleOutlined />} loading={loading} onClick={handleRun} disabled={!currentProject?.id}>
                  {tm('actions.runTask', 'Run task')}
                </Button>
                <Button icon={<ReloadOutlined />} disabled={!lastExecutionId} loading={loading} onClick={handleReload}>
                  {tm('actions.refreshResult', 'Refresh result')}
                </Button>
              </div>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={12}>
          <Card title={tm('cards.executionResult', 'Execution Result')} className="ui-automation-card">
            {result ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <div className="ui-automation-summary-grid">
                  <div>
                    <Text type="secondary">{tm('labels.executionId', 'Execution ID')}</Text>
                    <Title level={4}>{result.execution_id}</Title>
                  </div>
                  <div>
                    <Text type="secondary">{tm('labels.status', 'Status')}</Text>
                    <Title level={4}>
                      <Tag color={result.status === 'completed' ? 'success' : 'error'}>{result.status}</Tag>
                    </Title>
                  </div>
                  <div>
                    <Text type="secondary">{tm('labels.steps', 'Steps')}</Text>
                    <Title level={4}>
                      {result.passed_steps}/{result.total_steps}
                    </Title>
                  </div>
                  <div>
                    <Text type="secondary">{tm('labels.duration', 'Duration')}</Text>
                    <Title level={4}>{result.duration_ms} ms</Title>
                  </div>
                </div>
                <Divider style={{ margin: 0 }} />
                <Table
                  size="small"
                  pagination={false}
                  rowKey="index"
                  dataSource={result.steps}
                  locale={{ emptyText: <Empty description={tm('empty.noSteps', 'No steps')} /> }}
                  columns={[
                    { title: '#', dataIndex: 'index', width: 60 },
                    { title: tm('table.name', 'Name'), dataIndex: 'name' },
                    { title: tm('table.action', 'Action'), dataIndex: 'action', width: 110 },
                    {
                      title: tm('table.status', 'Status'),
                      dataIndex: 'status',
                      width: 100,
                      render: (value: string) => <Tag color={value === 'passed' ? 'success' : 'error'}>{value}</Tag>,
                    },
                    { title: tm('table.message', 'Message'), dataIndex: 'message', ellipsis: true },
                  ]}
                  expandable={{
                    expandedRowRender: (row) => (
                      <Space direction="vertical" size={6}>
                        {row.selector && <Text code>{row.selector}</Text>}
                        {row.url && <Text>{row.url}</Text>}
                        {row.error_message && <Alert type="error" showIcon message={row.error_message} />}
                      </Space>
                    ),
                  }}
                />
              </Space>
            ) : (
              <div className="workspace-inline-note">{tm('empty.resultPlaceholder', 'Execution logs and results will appear here after a run.')}</div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default UIAutomationWorkbench
