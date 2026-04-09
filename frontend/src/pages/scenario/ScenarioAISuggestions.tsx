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
        title="AI 场景建议"
        description="集中查看和承接 AI 生成的场景草稿、映射建议、断言建议和失败分析能力。当前版本先恢复页面入口。"
        metrics={[
          { label: '当前项目', value: currentProject?.name || '-' },
          { label: '当前版本', value: currentVersion?.version_number || '-' },
          { label: '模块状态', value: '入口已恢复' },
        ]}
      />

      <Card className="workspace-table-card" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="AI 场景建议页面已恢复访问"
            description="为了先恢复路由和构建，这里保留为稳定入口页。后续可以再逐步接回 AI 草稿生成、建议处理、映射建议和失败分析能力。"
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
