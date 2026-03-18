import React, { useMemo, useState } from 'react'
import { Button, Card, Descriptions, Input, List, Spin, Steps, Typography, message } from 'antd'
import {
  CheckCircleOutlined,
  LoadingOutlined,
  SendOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

import api from '../../services/api'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import { useProjectStore } from '../../store/project'
import type { ScenarioDraft } from '../../types/scenario'

import './IntentWorkbench.css'

const { TextArea } = Input
const { Paragraph, Text } = Typography

const IntentWorkbench: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject, currentVersion } = useProjectStore()
  const [intent, setIntent] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [generatedScenario, setGeneratedScenario] = useState<ScenarioDraft | null>(null)

  const scenarioMeta = generatedScenario?.scenario ?? {}
  const nodes = useMemo(() => generatedScenario?.nodes ?? [], [generatedScenario])

  const handleGenerate = async () => {
    if (!currentProject?.id) {
      message.error('请先选择项目')
      return
    }
    if (!currentVersion?.id) {
      message.error('请先选择版本')
      return
    }
    if (!intent.trim()) {
      return
    }

    setLoading(true)
    setCurrentStep(1)

    try {
      const response = await api.post('/intent-workbench/generate-scenario', {
        intent_text: intent.trim(),
        project_id: currentProject.id,
        version_id: currentVersion.id,
      })

      if (response.code !== 0 || !response.data?.draft) {
        message.error(response.message || '生成场景失败')
        setCurrentStep(0)
        return
      }

      setGeneratedScenario(response.data.draft)
      setCurrentStep(2)
    } catch (error: any) {
      message.error(error.message || '生成场景失败')
      setCurrentStep(0)
    } finally {
      setLoading(false)
    }
  }

  const triggerJITMapping = async (draft: ScenarioDraft, scenarioId: number) => {
    try {
      const definitionIds = draft.nodes
        .map((node) => node.ref_id)
        .filter((id): id is number => typeof id === 'number' && id > 0)

      if (definitionIds.length === 0) {
        return
      }

      const mappingResponse = await api.post('/field-mappings/suggest-task', {
        definition_ids: definitionIds,
        scenario_id: scenarioId,
        use_ai: true,
      })

      if (mappingResponse.code === 0) {
        message.info(`已启动字段映射任务，任务 ID: ${mappingResponse.data.task_id}`)
      }
    } catch (error) {
      console.error('启动字段映射失败:', error)
    }
  }

  const handleConfirm = async () => {
    if (!generatedScenario || !currentProject?.id) {
      return
    }

    try {
      const response = await api.post('/intent-workbench/confirm-scenario', {
        draft: generatedScenario,
        project_id: currentProject.id,
        version_id: currentVersion?.id ?? scenarioMeta.version_id ?? null,
      })

      if (response.code !== 0) {
        message.error(response.message || '保存场景失败')
        return
      }

      const scenarioId = response.data?.scenario_id
      if (!scenarioId) {
        message.error('保存场景失败：未返回场景 ID')
        return
      }

      await triggerJITMapping(generatedScenario, scenarioId)

      message.success('场景已保存')
      setCurrentStep(0)
      setIntent('')
      setGeneratedScenario(null)
      navigate(`/scenario/${scenarioId}`)
    } catch (error: any) {
      message.error(error.message || '保存场景失败')
    }
  }

  return (
    <div className="intent-workbench governance-stack">
      <WorkspaceModuleHero
        eyebrow="Scenario"
        title="意图工作台"
        description="输入自然语言意图，生成场景草稿并确认入库。"
        metrics={[
          { label: '当前步骤', value: currentStep + 1 },
          { label: '草稿节点数', value: nodes.length },
          { label: '当前版本', value: currentVersion?.version_number || '-' },
        ]}
      />
      <Card className="workbench-card workspace-table-card" bordered={false}>
        <Steps
          current={currentStep}
          style={{ marginBottom: 32 }}
          items={[
            { title: '输入意图', description: '描述测试场景' },
            { title: 'AI 生成', description: '编排场景草稿' },
            { title: '确认保存', description: '落库并继续执行' },
          ]}
        />

        {currentStep === 0 && (
          <div className="step-content">
            <TextArea
              value={intent}
              onChange={(event) => setIntent(event.target.value)}
              placeholder="例如：生成一个电商下单链路，包含创建用户、登录、浏览商品、下单、支付，并校验库存扣减。"
              rows={6}
              maxLength={500}
              showCount
            />
            <div className="step-actions">
              <Button
                type="primary"
                icon={loading ? <LoadingOutlined /> : <SendOutlined />}
                onClick={handleGenerate}
                loading={loading}
                disabled={!intent.trim()}
                size="large"
              >
                生成场景
              </Button>
            </div>
          </div>
        )}

        {currentStep === 1 && (
          <div className="step-content">
            <Spin tip="AI 正在生成场景..." spinning={loading}>
              <div style={{ minHeight: 200 }}>
                <p>正在分析意图...</p>
                <p>正在检索相关 API...</p>
                <p>正在生成场景编排...</p>
              </div>
            </Spin>
          </div>
        )}

        {currentStep === 2 && generatedScenario && (
          <div className="step-content">
            <Card title="生成的场景" size="small" style={{ marginBottom: 16 }}>
              <Descriptions size="small" column={2} bordered style={{ marginBottom: 16 }}>
                <Descriptions.Item label="名称">{scenarioMeta.name || '未命名场景'}</Descriptions.Item>
                <Descriptions.Item label="版本 ID">{scenarioMeta.version_id ?? currentVersion?.id ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="类型">{scenarioMeta.scenario_type || 'business_flow'}</Descriptions.Item>
                <Descriptions.Item label="执行模式">{scenarioMeta.execution_mode || 'dag'}</Descriptions.Item>
                <Descriptions.Item label="超时">{scenarioMeta.timeout_seconds ?? 600}s</Descriptions.Item>
                <Descriptions.Item label="节点数">{nodes.length}</Descriptions.Item>
              </Descriptions>

              <Paragraph>{scenarioMeta.description || '暂无描述'}</Paragraph>

              {generatedScenario.reasoning && (
                <Paragraph type="secondary">推理说明：{generatedScenario.reasoning}</Paragraph>
              )}

              <List
                header="场景节点"
                bordered
                dataSource={nodes}
                renderItem={(node, index) => (
                  <List.Item>
                    <div style={{ width: '100%' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
                        <Text strong>
                          {index + 1}. {node.node_name || node.node_key}
                        </Text>
                        <Text type="secondary">
                          {node.ref_type} #{node.ref_id}
                        </Text>
                      </div>
                      <div>
                        <Text type="secondary">{node.node_type}</Text>
                        {node.depends_on.length > 0 && (
                          <Text type="secondary">，依赖：{node.depends_on.join(', ')}</Text>
                        )}
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            </Card>

            <div className="step-actions">
              <Button onClick={() => setCurrentStep(0)}>重新生成</Button>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={handleConfirm}
              >
                确认保存
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

export default IntentWorkbench


