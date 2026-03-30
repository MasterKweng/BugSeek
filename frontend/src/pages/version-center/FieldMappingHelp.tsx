import React from 'react'
import { Button, Card, Space, Typography } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import helpMarkdown from '../../content/field-mapping-help.md?raw'

const { Paragraph, Text, Title } = Typography

const markdownComponents = {
  h1: ({ children }: { children?: React.ReactNode }) => <Title level={2}>{children}</Title>,
  h2: ({ children }: { children?: React.ReactNode }) => <Title level={3}>{children}</Title>,
  h3: ({ children }: { children?: React.ReactNode }) => <Title level={4}>{children}</Title>,
  p: ({ children }: { children?: React.ReactNode }) => <Paragraph>{children}</Paragraph>,
  li: ({ children }: { children?: React.ReactNode }) => <li style={{ marginBottom: 8 }}><Text>{children}</Text></li>,
  strong: ({ children }: { children?: React.ReactNode }) => <Text strong>{children}</Text>,
  em: ({ children }: { children?: React.ReactNode }) => <Text italic>{children}</Text>,
  code: ({ children }: { children?: React.ReactNode }) => (
    <Text code>{children}</Text>
  ),
}

const FieldMappingHelp: React.FC = () => {
  return (
    <div className="governance-stack">
      <WorkspaceModuleHero
        eyebrow="Guides"
        title="字段映射功能说明"
        description="帮助用户理解字段映射各项参数的作用、适用场景，以及它们会如何影响最终结果。"
        metrics={[
          { label: '说明范围', value: '运行参数 + 项目配置 + 版本配置' },
          { label: '适用对象', value: '字段映射使用者' },
        ]}
        actions={(
          <Space wrap>
            <Button icon={<ArrowLeftOutlined />}>
              <Link to="/version-center/field-mapping">返回字段映射</Link>
            </Button>
          </Space>
        )}
      />

      <Card className="workspace-table-card" bordered={false}>
        <div style={{ maxWidth: 980, margin: '0 auto' }}>
          <ReactMarkdown components={markdownComponents}>
            {helpMarkdown}
          </ReactMarkdown>
        </div>
      </Card>
    </div>
  )
}

export default FieldMappingHelp
