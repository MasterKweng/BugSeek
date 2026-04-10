import React from 'react'
import { RobotOutlined } from '@ant-design/icons'
import { Alert, Card, Empty, Space, Typography } from 'antd'

import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import { useProjectStore } from '../../store/project'

const { Paragraph, Text } = Typography

const ScenarioAISuggestions: React.FC = () => {
  const { currentProject, currentVersion } = useProjectStore()

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow="Scenario"
        title="AI 建议台【待完善】"
        description="这里预留给 AI 草稿、映射建议、断言建议和失败分析。当前版本仅恢复入口，完整工作流仍待完善。"
        metrics={[
          { label: '当前项目', value: currentProject?.name || '-' },
          { label: '当前版本', value: currentVersion?.version_number || '-' },
          { label: '模块状态', value: '待完善' },
        ]}
      />

      <Card className="workspace-table-card" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="AI 建议台仍在完善中"
            description="当前页面主要用于保留入口和说明状态，后续会逐步接回 AI 草稿生成、建议处理、映射建议和失败分析能力。"
          />

          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="当前版本暂未接入可直接操作的 AI 场景建议工作流"
          />

          <Space direction="vertical" size={8}>
            <Text strong>
              <RobotOutlined /> 后续可接入的能力
            </Text>
            <Paragraph style={{ marginBottom: 0 }}>
              1. 基于意图生成场景草稿
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }}>
              2. 对场景草稿应用或拒绝 AI 建议
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }}>
              3. 基于版本快照生成映射建议与断言建议
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }}>
              4. 对失败执行进行 AI 归因与修复建议
            </Paragraph>
          </Space>
        </Space>
      </Card>
    </div>
  )
}

export default ScenarioAISuggestions
