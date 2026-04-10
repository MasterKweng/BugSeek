import React, { useEffect, useState } from 'react'
import { Button, Card, Empty, Space, Table, Tag, Typography, message } from 'antd'
import { PlayCircleOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

import api from '../../services/api'
import { useProjectStore } from '../../store/project'
import type { ScenarioSummary } from '../../types/scenario'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import ScenarioStatusTag from '../../components/scenario/ScenarioStatusTag'

const { Text } = Typography

const sourceTypeLabelMap: Record<string, string> = {
  intent: 'AI 意图生成',
  manual: '手工创建',
  template: '模板实例化',
}

const scenarioTypeLabelMap: Record<string, string> = {
  business_flow: '业务流程',
  regression: '回归测试',
  smoke: '冒烟测试',
}

const ScenarioList: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])

  useEffect(() => {
    void loadScenarios()
  }, [currentProject?.id])

  const loadScenarios = async () => {
    if (!currentProject?.id) {
      setScenarios([])
      return
    }

    setLoading(true)
    try {
      const response = await api.get(`/scenarios?project_id=${currentProject.id}`)
      if (response.code === 0) {
        setScenarios(response.data.items || [])
      } else {
        message.error(response.message || '加载场景列表失败')
      }
    } catch (error: any) {
      message.error(error.message || '加载场景列表失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="workspace-page workspace-list-page">
      <WorkspaceModuleHero
        eyebrow="Scenario"
        title="场景管理"
        description="统一管理项目场景、编排入口与执行链路。"
        metrics={[
          { label: '场景数', value: scenarios.length },
          { label: '当前项目', value: currentProject?.name || '-' },
          { label: '加载状态', value: loading ? '加载中' : '就绪' },
        ]}
        actions={
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => void loadScenarios()} loading={loading}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/scenario/templates')}>
              从模板创建
            </Button>
          </Space>
        }
      />
      <Card className="workspace-table-card workspace-list-page__card" bordered={false}>
        {!currentProject?.id ? (
          <Empty description="请先选择项目" />
        ) : (
          <Table<ScenarioSummary>
            rowKey="id"
            loading={loading}
            dataSource={scenarios}
            scroll={{ y: 'calc(100vh - 420px)' }}
            pagination={{ pageSize: 10 }}
            columns={[
              {
                title: '场景名称',
                dataIndex: 'name',
                key: 'name',
                render: (_, record) => (
                  <Space direction="vertical" size={0}>
                    <Button type="link" style={{ padding: 0 }} onClick={() => navigate(`/scenario/${record.id}`)}>
                      {record.name}
                    </Button>
                    <Text type="secondary">{record.description || '暂无描述'}</Text>
                  </Space>
                ),
              },
              {
                title: '来源',
                dataIndex: 'source_type',
                key: 'source_type',
                render: (value: string) => (
                  <Tag color={value === 'intent' ? 'blue' : 'green'}>
                    {sourceTypeLabelMap[value] || value}
                  </Tag>
                ),
              },
              {
                title: '类型',
                dataIndex: 'scenario_type',
                key: 'scenario_type',
                render: (value: string) => scenarioTypeLabelMap[value] || value,
              },
              {
                title: '节点数量',
                dataIndex: 'node_count',
                key: 'node_count',
              },
              {
                title: '状态',
                dataIndex: 'lifecycle_status',
                key: 'status',
                render: (_: string, record) => <ScenarioStatusTag status={record.lifecycle_status || record.status} />,
              },
              {
                title: '版本摘要',
                key: 'revision',
                render: (_, record) => `草稿:${record.draft_revision_id ?? '-'} / 发布:${record.published_revision_id ?? '-'}`,
              },
              {
                title: '更新时间',
                dataIndex: 'updated_at',
                key: 'updated_at',
                render: (value: string) => value || '-',
              },
              {
                title: '操作',
                key: 'actions',
                render: (_, record) => (
                  <Space size="small">
                    <Button type="link" size="small" onClick={() => navigate(`/scenario/${record.id}`)}>
                      查看
                    </Button>
                    <Button type="link" size="small" onClick={() => navigate(`/scenario/${record.id}/design`)}>
                      编辑
                    </Button>
                    <Button
                      type="link"
                      size="small"
                      icon={<PlayCircleOutlined />}
                      onClick={() => navigate(`/scenario/${record.id}`)}
                    >
                      执行
                    </Button>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  )
}

export default ScenarioList

