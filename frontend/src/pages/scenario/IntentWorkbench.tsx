import React, { useState } from 'react'
import { ArrowLeftOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Input, Space, Steps, Typography, message } from 'antd'
import { useNavigate } from 'react-router-dom'

import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import { useProjectStore } from '../../store/project'
import './IntentWorkbench.css'

const { Paragraph, Text } = Typography
const { TextArea } = Input

const IntentWorkbench: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject, currentVersion } = useProjectStore()
  const [currentStep, setCurrentStep] = useState(0)
  const [intentText, setIntentText] = useState('')
  const [creating, setCreating] = useState(false)

  const handleCreatePlaceholder = async () => {
    if (!intentText.trim()) {
      message.warning('请先输入场景意图描述')
      return
    }

    setCreating(true)
    window.setTimeout(() => {
      setCreating(false)
      message.info('意图工作台当前先恢复为可访问入口，后续再接完整创建流程。')
    }, 400)
  }

  return (
    <div className="workspace-page intent-workbench">
      <WorkspaceModuleHero
        eyebrow="Scenario"
        title="意图工作台"
        description="从业务意图出发，整理场景目标、输入约束和预期结果。当前版本先恢复页面入口与基础工作台。"
        metrics={[
          { label: '当前项目', value: currentProject?.name || '-' },
          { label: '当前版本', value: currentVersion?.version_number || '-' },
          { label: '当前步骤', value: currentStep + 1 },
        ]}
        actions={(
          <Space wrap>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/scenario/list')}>
              返回场景列表
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => setIntentText('')}>
              清空输入
            </Button>
          </Space>
        )}
      />

      <Card className="workspace-table-card workbench-card" bordered={false}>
        <Steps
          current={currentStep}
          items={[
            { title: '描述意图', description: '输入业务目标和预期产出' },
            { title: '确认范围', description: '补充输入、约束和系统边界' },
            { title: '进入设计', description: '后续接入场景创建流程' },
          ]}
        />

        <div className="step-content" style={{ marginTop: 24 }}>
          {currentStep === 0 ? (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Paragraph style={{ marginBottom: 0 }}>
                输入一句或一段场景意图，用来描述你想要构建的业务流程。
              </Paragraph>
              <TextArea
                rows={8}
                value={intentText}
                onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setIntentText(event.target.value)}
                placeholder="例如：创建一个库存预警处理场景，当库存低于阈值时自动通知采购并生成补货建议。"
              />
              <Text type="secondary">
                这一版先作为工作台入口恢复，后续可以继续接入意图解析、模板推荐和场景创建。
              </Text>
            </Space>
          ) : (
            <Empty description="该步骤将在后续版本接入完整流程" />
          )}
        </div>

        <div className="step-actions">
          <Button disabled={currentStep === 0} onClick={() => setCurrentStep((prev) => Math.max(prev - 1, 0))}>
            上一步
          </Button>
          {currentStep < 2 ? (
            <Button
              type="primary"
              icon={currentStep === 0 ? <PlusOutlined /> : undefined}
              loading={creating}
              onClick={() => {
                if (currentStep === 0) {
                  void handleCreatePlaceholder()
                  return
                }
                setCurrentStep((prev) => Math.min(prev + 1, 2))
              }}
            >
              {currentStep === 0 ? '保存意图' : '下一步'}
            </Button>
          ) : (
            <Button type="primary" onClick={() => navigate('/scenario/list')}>
              返回场景列表
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}

export default IntentWorkbench
