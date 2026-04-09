import React, { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tooltip,
  Typography,
  message,
} from 'antd'
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  QuestionCircleOutlined,
  RocketOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import { useProjectStore } from '../../store/project'
import {
  type ScenarioDetail as ScenarioDetailType,
  type ScenarioExecutionSummary,
  type ScenarioRevisionListItem,
  type ScenarioValidationResult,
  type Environment,
} from '../../types/scenario'
import { createScenarioRun } from '../../services/scenarioRuns'
import {
  getScenario,
  getScenarioRevisions,
  listScenarioExecutionsLegacy,
  publishScenario,
  validateScenario,
  type ScenarioExecutionListItem,
} from '../../services/scenario'
import api from '../../services/api'
import ScenarioStatusTag from '../../components/scenario/ScenarioStatusTag'

const { Paragraph, Text } = Typography

const labelWithHint = (label: string, hint: string) => (
  <Space size={4}>
    <span>{label}</span>
    <Tooltip title={hint}>
      <QuestionCircleOutlined />
    </Tooltip>
  </Space>
)

const ScenarioDetail: React.FC = () => {
  const navigate = useNavigate()
  const { scenarioId } = useParams()
  const { currentProject } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [validating, setValidating] = useState(false)
  const [scenario, setScenario] = useState<ScenarioDetailType | null>(null)
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState<number | null>(null)
  const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(null)
  const [executionModalVisible, setExecutionModalVisible] = useState(false)
  const [executions, setExecutions] = useState<ScenarioExecutionListItem[]>([])
  const [revisions, setRevisions] = useState<ScenarioRevisionListItem[]>([])
  const [validationResult, setValidationResult] = useState<ScenarioValidationResult | null>(null)

  const resolvedLifecycleStatus = scenario?.lifecycle_status || scenario?.status || '-'
  const defaultRevisionId = useMemo(() => {
    if (!scenario) return null
    return scenario.published_revision_id ?? scenario.draft_revision_id ?? null
  }, [scenario])

  useEffect(() => {
    void loadScenario()
  }, [scenarioId])

  useEffect(() => {
    void loadEnvironments()
  }, [currentProject?.id])

  useEffect(() => {
    void loadExecutions()
    void loadRevisions()
  }, [scenarioId])

  useEffect(() => {
    if (!selectedRevisionId) {
      setSelectedRevisionId(defaultRevisionId)
    }
  }, [defaultRevisionId, selectedRevisionId])

  const loadScenario = async () => {
    if (!scenarioId) return
    setLoading(true)
    try {
      const detail = await getScenario(Number(scenarioId))
      setScenario(detail)
      setSelectedEnvironmentId(detail.environment_id ?? null)
    } catch (error: any) {
      message.error(error.message || '加载场景失败')
    } finally {
      setLoading(false)
    }
  }

  const loadEnvironments = async () => {
    if (!currentProject?.id) {
      setEnvironments([])
      return
    }
    try {
      const response = await api.get(`/environments?project_id=${currentProject.id}`)
      if (response.code === 0) {
        setEnvironments(response.data.environments || [])
      }
    } catch (error) {
      console.error('加载环境失败:', error)
    }
  }

  const loadExecutions = async () => {
    if (!scenarioId) return
    try {
      const data = await listScenarioExecutionsLegacy(Number(scenarioId), { skip: 0, limit: 10 })
      setExecutions(data.items || [])
    } catch (error) {
      console.error('加载执行历史失败:', error)
    }
  }

  const loadRevisions = async () => {
    if (!scenarioId) return
    try {
      const data = await getScenarioRevisions(Number(scenarioId))
      setRevisions(data.items || [])
    } catch (error) {
      console.error('加载版本快照失败:', error)
    }
  }

  const handleValidate = async () => {
    if (!scenarioId) return
    setValidating(true)
    try {
      const result = await validateScenario(Number(scenarioId), {
        environment_id: selectedEnvironmentId,
      })
      setValidationResult(result)
      if (result.readiness_valid) {
        message.success('场景校验通过')
      } else {
        message.warning('结构有效，但发布前检查未通过')
      }
    } catch (error: any) {
      message.error(error.message || '场景校验失败')
    } finally {
      setValidating(false)
    }
  }

  const handlePublish = async () => {
    if (!scenarioId) return
    setPublishing(true)
    try {
      const result = await publishScenario(Number(scenarioId), { publish_note: 'published from scenario detail' })
      message.success(`场景已发布为版本 #${result.revision_no}`)
      await loadScenario()
      await loadRevisions()
    } catch (error: any) {
      message.error(error.message || '发布场景失败')
    } finally {
      setPublishing(false)
    }
  }

  const handleExecute = async () => {
    if (!scenarioId || !selectedEnvironmentId) {
      message.warning('请选择执行环境')
      return
    }
    setExecuting(true)
    try {
      const run = await createScenarioRun({
        scenario_id: Number(scenarioId),
        revision_id: selectedRevisionId ?? undefined,
        environment_id: selectedEnvironmentId,
      })
      message.success('场景运行已提交')
      setExecutionModalVisible(false)
      await loadExecutions()
      navigate(`/scenario/${scenarioId}/execution/${run.run_id}`)
    } catch (error: any) {
      message.error(error.message || '执行场景失败')
    } finally {
      setExecuting(false)
    }
  }

  if (loading && !scenario) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (!scenario) {
    return (
      <div style={{ padding: 24 }}>
        <Empty description="未找到场景" />
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 24 }} wrap>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/scenario/list')}>
          返回列表
        </Button>
        <Button icon={<SettingOutlined />} onClick={() => navigate(`/scenario/${scenario.id}/design`)}>
          进入设计页
        </Button>
        <Button icon={<CheckCircleOutlined />} onClick={() => void handleValidate()} loading={validating}>
          校验场景
        </Button>
        <Button icon={<RocketOutlined />} onClick={() => void handlePublish()} loading={publishing}>
          发布场景
        </Button>
        <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => setExecutionModalVisible(true)}>
          创建运行
        </Button>
      </Space>

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title="场景详情">
          <Descriptions bordered column={2}>
            <Descriptions.Item label="场景 ID">{scenario.id}</Descriptions.Item>
            <Descriptions.Item label="项目 ID">{scenario.project_id}</Descriptions.Item>
            <Descriptions.Item label="场景名称">{scenario.name}</Descriptions.Item>
            <Descriptions.Item label="生命周期">
              <ScenarioStatusTag status={resolvedLifecycleStatus} />
            </Descriptions.Item>
            <Descriptions.Item label="场景类型">{scenario.scenario_type}</Descriptions.Item>
            <Descriptions.Item label="来源">{scenario.source_type}</Descriptions.Item>
            <Descriptions.Item label="执行模式">{scenario.execution_mode}</Descriptions.Item>
            <Descriptions.Item label="默认环境">{scenario.environment_id ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="节点数量">{scenario.node_count}</Descriptions.Item>
            <Descriptions.Item label="超时">{scenario.timeout_seconds}s</Descriptions.Item>
            <Descriptions.Item label={labelWithHint('草稿版本', '设计态的版本快照，可继续编辑。')}>
              {scenario.draft_revision_id ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label={labelWithHint('发布版本', '正式发布后可执行的版本快照。')}>
              {scenario.published_revision_id ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label={labelWithHint('最新版本号', '该场景当前已生成的最新版本序号。')}>
              {scenario.latest_revision_no ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="版本 ID">{scenario.version_id ?? '-'}</Descriptions.Item>
          </Descriptions>

          <Paragraph style={{ marginTop: 16 }}>{scenario.description || '暂无描述'}</Paragraph>
        </Card>

        {validationResult ? (
          <Alert
            type={validationResult.readiness_valid ? 'success' : 'warning'}
            showIcon
            message={validationResult.readiness_valid ? '场景已通过校验' : '场景结构通过，但 readiness 未通过'}
            description={(
              <Space direction="vertical" size={4}>
                <Text>结构校验：{validationResult.structural_valid ? '通过' : '失败'}</Text>
                <Text>执行前检查：{validationResult.readiness_valid ? '通过' : '未通过'}</Text>
                {validationResult.errors.length > 0 ? (
                  <Text type="danger">问题：{validationResult.errors.map((item) => item.message).join('；')}</Text>
                ) : null}
                {validationResult.warnings.length > 0 ? (
                  <Text type="secondary">提示：{validationResult.warnings.map((item) => item.message).join('；')}</Text>
                ) : null}
              </Space>
            )}
          />
        ) : null}

        <Card title="版本快照列表">
          <Table<ScenarioRevisionListItem>
            rowKey="id"
            dataSource={revisions}
            pagination={false}
            locale={{ emptyText: '暂无版本快照' }}
            columns={[
              { title: '版本快照 ID', dataIndex: 'id', key: 'id' },
              { title: '版本号', dataIndex: 'revision_no', key: 'revision_no' },
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                render: (value: string) => <ScenarioStatusTag status={value} />,
              },
              { title: '发布时间', dataIndex: 'published_at', key: 'published_at', render: (value?: string | null) => value || '-' },
              {
                title: '操作',
                key: 'actions',
                render: (_, record) => (
                  <Button type="link" onClick={() => navigate(`/scenario/${scenario.id}/design?revisionId=${record.id}`)}>
                    查看设计
                  </Button>
                ),
              },
            ]}
          />
        </Card>

        <Card title="场景节点">
          <Table
            rowKey={(node) => node.id ?? node.node_key}
            dataSource={scenario.nodes}
            pagination={false}
            columns={[
              { title: '节点名称', key: 'name', render: (_, node) => node.node_name || node.node_key },
              { title: '节点标识', dataIndex: 'node_key', key: 'node_key' },
              { title: '节点类型', dataIndex: 'node_type', key: 'node_type' },
              {
                title: '引用',
                key: 'ref',
                render: (_, node) => (node.ref_type ? `${node.ref_type} #${node.ref_id ?? '-'}` : '-'),
              },
              {
                title: '依赖',
                dataIndex: 'depends_on',
                key: 'depends_on',
                render: (value: string[]) => (value?.length ? value.join(', ') : '-'),
              },
            ]}
          />
        </Card>

        <Card title="最近运行 / 执行记录">
          <Table<ScenarioExecutionListItem>
            rowKey="id"
            dataSource={executions}
            pagination={false}
            locale={{ emptyText: '暂无执行记录' }}
            columns={[
              { title: '运行 ID', dataIndex: 'id', key: 'id' },
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                render: (value: string) => <ScenarioStatusTag status={value} />,
              },
              { title: '环境', dataIndex: 'environment_id', key: 'environment_id' },
              {
                title: '摘要',
                dataIndex: 'summary',
                key: 'summary',
                render: (summary?: ScenarioExecutionSummary | Record<string, unknown>) => {
                  const runSummary = summary as ScenarioExecutionSummary | undefined
                  if (!runSummary?.total) return '-'
                  return `${runSummary.passed}/${runSummary.total} 通过，耗时 ${runSummary.duration_ms}ms`
                },
              },
              { title: '开始时间', dataIndex: 'started_at', key: 'started_at' },
              {
                title: '操作',
                key: 'actions',
                render: (_, record) => (
                  <Button type="link" onClick={() => navigate(`/scenario/${scenario.id}/execution/${record.id}`)}>
                    查看运行
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      </Space>

      <Modal
        title="创建场景运行"
        open={executionModalVisible}
        onOk={() => void handleExecute()}
        confirmLoading={executing}
        onCancel={() => setExecutionModalVisible(false)}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select<number>
            placeholder="请选择执行环境"
            value={selectedEnvironmentId ?? undefined}
            onChange={(value) => setSelectedEnvironmentId(value)}
            options={environments.map((item) => ({
              label: `${item.name} (${item.base_url})`,
              value: item.id,
            }))}
          />
          <Select<number>
            allowClear
            placeholder="可选：指定版本快照运行"
            value={selectedRevisionId ?? undefined}
            onChange={(value) => setSelectedRevisionId(value ?? null)}
            options={revisions.map((revision) => ({
              label: `#${revision.revision_no}（${revision.status}）`,
              value: revision.id,
            }))}
          />
          <Text type="secondary">未指定版本快照时，后端会默认运行已发布的版本。</Text>
        </Space>
      </Modal>
    </div>
  )
}

export default ScenarioDetail
