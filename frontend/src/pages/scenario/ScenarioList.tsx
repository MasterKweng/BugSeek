import React, { useEffect, useState } from 'react'
import { Button, Card, Empty, Space, Table, Tag, Typography, message } from 'antd'
import { PlayCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

import api from '../../services/api'
import { useProjectStore } from '../../store/project'
import type { ScenarioSummary } from '../../types/scenario'

const { Text } = Typography

const statusColorMap: Record<string, string> = {
  active: 'success',
  archived: 'default',
  draft: 'processing',
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
    <div style={{ padding: 24 }}>
      <Card
        title="场景管理"
        extra={
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/scenario/intent-workbench')}>
              创建场景
            </Button>
          </Space>
        }
      >
        {!currentProject?.id ? (
          <Empty description="请先选择项目" />
        ) : (
          <Table<ScenarioSummary>
            rowKey="id"
            loading={loading}
            dataSource={scenarios}
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
                render: (value: string) => <Tag color={value === 'intent' ? 'blue' : 'green'}>{value}</Tag>,
              },
              {
                title: '类型',
                dataIndex: 'scenario_type',
                key: 'scenario_type',
              },
              {
                title: '节点数量',
                dataIndex: 'node_count',
                key: 'node_count',
              },
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                render: (value: string) => <Tag color={statusColorMap[value] || 'default'}>{value}</Tag>,
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

