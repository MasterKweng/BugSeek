import React, { useMemo, useState } from 'react'
import { Alert, Button, Card, Col, Divider, Input, Row, Space, Switch, Table, Tag, Typography, message } from 'antd'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'

import { createUIExecution, getUIExecution, type UIExecutionSummary } from '../../services/uiAutomation'
import { useProjectStore } from '../../store/project'
import './UIAutomationWorkbench.css'

const { Paragraph, Text, Title } = Typography
const { TextArea } = Input

const defaultSteps = JSON.stringify([
  { name: 'Open login page', action: 'goto', value: 'https://example.com/login' },
  { name: 'Fill username', action: 'fill', selector: '#username', value: 'demo@example.com' },
  { name: 'Fill password', action: 'fill', selector: '#password', value: 'password123' },
  { name: 'Submit form', action: 'click', selector: 'button[type="submit"]' },
  { name: 'Assert url', action: 'assert_url', value: '/dashboard' },
], null, 2)

const UIAutomationWorkbench: React.FC = () => {
  const { currentProject } = useProjectStore()
  const [caseName, setCaseName] = useState('Smoke Login Flow')
  const [startUrl, setStartUrl] = useState('https://example.com/login')
  const [headless, setHeadless] = useState(true)
  const [stepsText, setStepsText] = useState(defaultSteps)
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
      message.error('请先选择项目')
      return
    }
    if (!parsedSteps || !Array.isArray(parsedSteps) || parsedSteps.length === 0) {
      message.error('步骤 JSON 无效')
      return
    }

    setLoading(true)
    try {
      const response = await createUIExecution(currentProject.id, {
        name: caseName,
        start_url: startUrl || undefined,
        steps: parsedSteps,
        headless,
      })
      setResult(response.data)
      setLastExecutionId(response.data.execution_id)
      message.success(`执行完成，记录 #${response.data.execution_id}`)
    } catch (error: any) {
      message.error(error?.message || 'UI 自动化执行失败')
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
      message.error(error?.message || '获取执行结果失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="ui-automation-page">
      <Card className="ui-automation-hero" bordered={false}>
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Tag color="cyan">UI Automation</Tag>
          <Title level={2} style={{ margin: 0 }}>Playwright Workbench</Title>
          <Paragraph className="ui-automation-copy">
            Run one Playwright case, inspect step logs, and persist the execution result into the unified execution ledger.
          </Paragraph>
          {!currentProject?.id && (
            <Alert type="warning" showIcon message="当前没有项目上下文，先在顶部选择项目后再执行。" />
          )}
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="Execution Input" className="ui-automation-card">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Input value={caseName} onChange={(event) => setCaseName(event.target.value)} placeholder="Case name" />
              <Input value={startUrl} onChange={(event) => setStartUrl(event.target.value)} placeholder="Start URL" />
              <div className="ui-automation-switch-row">
                <Text>Headless</Text>
                <Switch checked={headless} onChange={setHeadless} />
              </div>
              <TextArea
                value={stepsText}
                onChange={(event) => setStepsText(event.target.value)}
                autoSize={{ minRows: 14, maxRows: 22 }}
                placeholder="Playwright steps JSON"
              />
              <div className="ui-automation-actions">
                <Button type="primary" icon={<PlayCircleOutlined />} loading={loading} onClick={handleRun}>
                  Run Case
                </Button>
                <Button icon={<ReloadOutlined />} disabled={!lastExecutionId} loading={loading} onClick={handleReload}>
                  Reload Result
                </Button>
              </div>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={12}>
          <Card title="Execution Result" className="ui-automation-card">
            {result ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <div className="ui-automation-summary-grid">
                  <div>
                    <Text type="secondary">Execution ID</Text>
                    <Title level={4}>{result.execution_id}</Title>
                  </div>
                  <div>
                    <Text type="secondary">Status</Text>
                    <Title level={4}><Tag color={result.status === 'completed' ? 'success' : 'error'}>{result.status}</Tag></Title>
                  </div>
                  <div>
                    <Text type="secondary">Steps</Text>
                    <Title level={4}>{result.passed_steps}/{result.total_steps}</Title>
                  </div>
                  <div>
                    <Text type="secondary">Duration</Text>
                    <Title level={4}>{result.duration_ms} ms</Title>
                  </div>
                </div>
                <Divider style={{ margin: 0 }} />
                <Table
                  size="small"
                  pagination={false}
                  rowKey="index"
                  dataSource={result.steps}
                  columns={[
                    { title: '#', dataIndex: 'index', width: 60 },
                    { title: 'Name', dataIndex: 'name' },
                    { title: 'Action', dataIndex: 'action', width: 110 },
                    {
                      title: 'Status',
                      dataIndex: 'status',
                      width: 100,
                      render: (value: string) => <Tag color={value === 'passed' ? 'success' : 'error'}>{value}</Tag>,
                    },
                    { title: 'Message', dataIndex: 'message', ellipsis: true },
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
              <Alert type="info" showIcon message="执行后会在这里展示步骤日志和结果。" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default UIAutomationWorkbench
