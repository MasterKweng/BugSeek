import React, { useEffect, useState } from 'react'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Input, Modal, Space, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'

import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import ScenarioStatusTag from '../../components/scenario/ScenarioStatusTag'
import { useProjectStore } from '../../store/project'
import type { ScenarioTemplate } from '../../types/scenario'
import { createScenarioTemplate, instantiateScenarioTemplate, listScenarioTemplates } from '../../services/scenarioTemplates'

const { Paragraph, Text } = Typography

const ScenarioTemplates: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject, currentVersion } = useProjectStore()
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [createVisible, setCreateVisible] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [templateDescription, setTemplateDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const loadTemplates = async () => {
    if (!currentProject?.id) {
      setTemplates([])
      return
    }

    setLoading(true)
    try {
      const data = await listScenarioTemplates(currentProject.id)
      setTemplates(data.items || [])
    } catch (error: any) {
      message.error(error.message || '加载场景模板失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadTemplates()
  }, [currentProject?.id])

  const handleCreateTemplate = async () => {
    if (!currentProject?.id) {
      message.warning('请先选择项目')
      return
    }

    if (!templateName.trim()) {
      message.warning('请输入模板名称')
      return
    }

    setSaving(true)
    try {
      await createScenarioTemplate(
        {
          name: templateName.trim(),
          description: templateDescription.trim() || null,
          category: 'general',
          version_id: currentVersion?.id ?? null,
          environment_id: null,
          scenario_type: 'business_flow',
          execution_mode: 'dag',
          timeout_seconds: 600,
          retry_count: 0,
          continue_on_failure: false,
          context_init: {},
          nodes: [],
        },
        currentProject.id,
      )
      message.success('场景模板已创建')
      setCreateVisible(false)
      setTemplateName('')
      setTemplateDescription('')
      await loadTemplates()
    } catch (error: any) {
      message.error(error.message || '创建场景模板失败')
    } finally {
      setSaving(false)
    }
  }

  const handleInstantiate = async (record: ScenarioTemplate) => {
    if (!currentProject?.id) {
      message.warning('请先选择项目')
      return
    }

    try {
      const result = await instantiateScenarioTemplate(record.id, {}, currentProject.id)
      message.success('模板已实例化为场景草稿')
      navigate(`/scenario/${result.scenario_id}/design${result.draft_revision_id ? `?revisionId=${result.draft_revision_id}` : ''}`)
    } catch (error: any) {
      message.error(error.message || '实例化模板失败')
    }
  }

  const columns: ColumnsType<ScenarioTemplate> = [
    {
      title: '模板名称',
      dataIndex: 'name',
      key: 'name',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.name}</Text>
          <Text type="secondary">{record.description || '暂无描述'}</Text>
        </Space>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 140,
      render: (value?: string | null) => value || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (value: string) => <ScenarioStatusTag status={value} />,
    },
    {
      title: '节点数',
      dataIndex: 'node_count',
      key: 'node_count',
      width: 100,
      render: (value?: number | null) => value ?? '-',
    },
    {
      title: '最新版本号',
      dataIndex: 'latest_revision_no',
      key: 'latest_revision_no',
      width: 120,
      render: (value?: number | null) => value ?? '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => void handleInstantiate(record)}>
            实例化
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow="Scenario"
        title="场景模板"
        description="浏览和管理可复用的场景模板，用于快速生成场景草稿。"
        metrics={[
          { label: '模板数', value: templates.length },
          { label: '当前项目', value: currentProject?.name || '-' },
          { label: '当前版本', value: currentVersion?.version_number || '-' },
        ]}
        actions={(
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => void loadTemplates()} loading={loading}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
              新建模板
            </Button>
          </Space>
        )}
      />

      <Card className="workspace-table-card" bordered={false}>
        {!currentProject?.id ? (
          <Empty description="请先选择项目" />
        ) : (
          <Table<ScenarioTemplate>
            rowKey="id"
            loading={loading}
            dataSource={templates}
            columns={columns}
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: '暂无场景模板' }}
          />
        )}
      </Card>

      <Modal
        title="新建场景模板"
        open={createVisible}
        onOk={() => void handleCreateTemplate()}
        onCancel={() => setCreateVisible(false)}
        confirmLoading={saving}
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Input
            value={templateName}
            onChange={(event) => setTemplateName(event.target.value)}
            placeholder="请输入模板名称"
          />
          <Input.TextArea
            rows={4}
            value={templateDescription}
            onChange={(event) => setTemplateDescription(event.target.value)}
            placeholder="请输入模板描述"
          />
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            这里先保留最小可用的模板创建能力，后续可以继续扩展更多模板字段和节点编辑能力。
          </Paragraph>
        </Space>
      </Modal>
    </div>
  )
}

export default ScenarioTemplates
