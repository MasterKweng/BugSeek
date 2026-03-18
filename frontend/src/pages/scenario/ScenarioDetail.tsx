import React, { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Modal,
  Select,
  Space,
  Spin,
  Steps,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { ArrowLeftOutlined, PlayCircleOutlined, SettingOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import api from '../../services/api'
import { useProjectStore } from '../../store/project'
import type {
  Environment,
  ScenarioDetail as ScenarioDetailType,
  ScenarioExecutionDetail,
} from '../../types/scenario'

const { Paragraph, Text } = Typography

interface ScenarioExecutionListItem extends Pick<ScenarioExecutionDetail, 'id' | 'status' | 'environment_id' | 'started_at' | 'finished_at' | 'summary'> {}

const ScenarioDetail: React.FC = () => {
  const navigate = useNavigate()
  const { scenarioId } = useParams()
  const { currentProject } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [scenario, setScenario] = useState<ScenarioDetailType | null>(null)
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState<number | null>(null)
  const [executionModalVisible, setExecutionModalVisible] = useState(false)
  const [executions, setExecutions] = useState<ScenarioExecutionListItem[]>([])

  useEffect(() => {
    void loadScenario()
  }, [scenarioId])

  useEffect(() => {
    void loadEnvironments()
  }, [currentProject?.id])

  useEffect(() => {
    void loadExecutions()
  }, [scenarioId])

  const loadScenario = async () => {
    if (!scenarioId) {
      return
    }

    setLoading(true)
    try {
      const response = await api.get(`/scenarios/${scenarioId}`)
      if (response.code === 0) {
        setScenario(response.data)
        setSelectedEnvironmentId(response.data.environment_id ?? null)
      } else {
        message.error(response.message || '加载场景失败')
      }
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
        const envs = response.data.environments || []
        setEnvironments(envs)
      }
    } catch (error) {
      console.error('加载环境失败:', error)
    }
  }

  const loadExecutions = async () => {
    if (!scenarioId) {
      return
    }

    try {
      const response = await api.get(`/scenarios/${scenarioId}/executions?skip=0&limit=10`)
      if (response.code === 0) {
        setExecutions(response.data.items || [])
      }
    } catch (error) {
      console.error('加载执行历史失败:', error)
    }
  }

  const handleExecute = async () => {
    if (!scenarioId || !selectedEnvironmentId) {
      message.warning('请选择执行环境')
      return
    }

    setExecuting(true)
    try {
      const response = await api.post(`/scenarios/${scenarioId}/execute`, {
        environment_id: selectedEnvironmentId,
      })
      if (response.code !== 0) {
        message.error(response.message || '执行场景失败')
        return
      }

      message.success('场景执行完成')
      setExecutionModalVisible(false)
      await loadScenario()
      await loadExecutions()
      navigate(`/scenario/${scenarioId}/execution/${response.data.execution_id}`)
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
          编辑场景
        </Button>
        <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => setExecutionModalVisible(true)}>
          执行场景
        </Button>
      </Space>

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title="场景详情">
          <Descriptions bordered column={2}>
            <Descriptions.Item label="场景 ID">{scenario.id}</Descriptions.Item>
            <Descriptions.Item label="版本 ID">{scenario.version_id ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="场景名称">{scenario.name}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={scenario.status === 'active' ? 'success' : scenario.status === 'archived' ? 'default' : 'processing'}>
                {scenario.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="场景类型">{scenario.scenario_type}</Descriptions.Item>
            <Descriptions.Item label="来源">{scenario.source_type}</Descriptions.Item>
            <Descriptions.Item label="执行模式">{scenario.execution_mode}</Descriptions.Item>
            <Descriptions.Item label="默认环境">{scenario.environment_id ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="节点数量">{scenario.node_count}</Descriptions.Item>
            <Descriptions.Item label="超时">{scenario.timeout_seconds}s</Descriptions.Item>
          </Descriptions>

          <Paragraph style={{ marginTop: 16 }}>{scenario.description || '暂无描述'}</Paragraph>
        </Card>

        <Card title="场景节点">
          <Steps
            direction="vertical"
            current={-1}
            items={scenario.nodes.map((node) => ({
              title: `${node.node_name || node.node_key}`,
              description: (
                <Space direction="vertical" size={2}>
                  <Text type="secondary">
                    {node.node_type} / {node.ref_type} #{node.ref_id}
                  </Text>
                  {node.depends_on.length > 0 && <Text type="secondary">依赖：{node.depends_on.join(', ')}</Text>}
                  {node.input_mapping && Object.keys(node.input_mapping).length > 0 && (
                    <Text type="secondary">输入映射：{JSON.stringify(node.input_mapping)}</Text>
                  )}
                </Space>
              ),
            }))}
          />
        </Card>

        <Card title="最近执行">
          <Table<ScenarioExecutionListItem>
            rowKey="id"
            dataSource={executions}
            pagination={false}
            locale={{ emptyText: '暂无执行记录' }}
            columns={[
              { title: '执行 ID', dataIndex: 'id', key: 'id' },
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                render: (value: string) => <Tag color={value === 'completed' ? 'success' : 'error'}>{value}</Tag>,
              },
              { title: '环境', dataIndex: 'environment_id', key: 'environment_id' },
              {
                title: '汇总',
                dataIndex: 'summary',
                key: 'summary',
                render: (summary: ScenarioExecutionDetail['summary']) =>
                  summary ? `${summary.passed}/${summary.total} 通过，耗时 ${summary.duration_ms}ms` : '-',
              },
              { title: '开始时间', dataIndex: 'started_at', key: 'started_at' },
              {
                title: '操作',
                key: 'actions',
                render: (_, record) => (
                  <Button type="link" onClick={() => navigate(`/scenario/${scenario.id}/execution/${record.id}`)}>
                    查看执行
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      </Space>

      <Modal
        title="执行场景"
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
        </Space>
      </Modal>
    </div>
  )
}

export default ScenarioDetail



