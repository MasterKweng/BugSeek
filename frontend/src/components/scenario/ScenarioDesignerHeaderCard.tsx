import React from 'react'
import { Alert, Button, Card, Descriptions, Space, Tooltip } from 'antd'
import { EyeOutlined, QuestionCircleOutlined, RocketOutlined, SafetyOutlined } from '@ant-design/icons'

import type { ScenarioDetail, ScenarioRevision, ScenarioValidationResult } from '../../types/scenario'
import ScenarioStatusTag from './ScenarioStatusTag'

interface ScenarioDesignerHeaderCardProps {
  scenario: ScenarioDetail
  selectedRevision: ScenarioRevision | null
  validationResult: ScenarioValidationResult | null
  lintResult: { valid: boolean; errors: Array<Record<string, unknown>>; warnings: Array<Record<string, unknown>> } | null
  validating: boolean
  linting: boolean
  publishing: boolean
  saving: boolean
  hasRevisionGraph: boolean
  onOpenRevisions: () => void
  onOpenGraph: () => void
  onValidate: () => void
  onLint: () => void
  onPublish: () => void
  onSave: () => void
  onBack: () => void
}

const formatMessages = (items: Array<{ message?: string }>) =>
  items.map((item) => item.message).filter(Boolean).join('；') || '暂无额外提示'

const withHint = (label: string, hint: string) => (
  <Space size={4}>
    <span>{label}</span>
    <Tooltip title={hint}>
      <QuestionCircleOutlined />
    </Tooltip>
  </Space>
)

const ScenarioDesignerHeaderCard: React.FC<ScenarioDesignerHeaderCardProps> = ({
  scenario,
  selectedRevision,
  validationResult,
  lintResult,
  validating,
  linting,
  publishing,
  saving,
  hasRevisionGraph,
  onOpenRevisions,
  onOpenGraph,
  onValidate,
  onLint,
  onPublish,
  onSave,
  onBack,
}) => {
  const lifecycle = scenario.lifecycle_status ?? scenario.status

  return (
    <Card
      title="场景设计工作台"
      extra={(
        <Space wrap>
          <Button onClick={onBack}>返回</Button>
          <Button icon={<EyeOutlined />} onClick={onOpenRevisions}>版本快照</Button>
          <Button onClick={onOpenGraph} disabled={!hasRevisionGraph}>依赖图</Button>
          <Button icon={<SafetyOutlined />} onClick={onValidate} loading={validating}>校验</Button>
          <Button onClick={onLint} loading={linting}>规则检查</Button>
          <Button icon={<RocketOutlined />} onClick={onPublish} loading={publishing}>发布</Button>
          <Button type="primary" onClick={onSave} loading={saving}>保存场景</Button>
        </Space>
      )}
    >
      <Descriptions bordered column={2} size="small" style={{ marginBottom: 16 }}>
        <Descriptions.Item label="场景 ID">{scenario.id}</Descriptions.Item>
        <Descriptions.Item label="生命周期"><ScenarioStatusTag status={lifecycle} /></Descriptions.Item>
        <Descriptions.Item label={withHint('草稿版本', '设计态的版本快照，允许继续编辑。')}>
          {scenario.draft_revision_id ?? '-'}
        </Descriptions.Item>
        <Descriptions.Item label={withHint('发布版本', '已正式发布、可执行和可用于 CI 的版本快照。')}>
          {scenario.published_revision_id ?? '-'}
        </Descriptions.Item>
        <Descriptions.Item label={withHint('当前版本', '当前设计页加载并查看的版本快照。')}>
          {selectedRevision?.id ?? '-'}
        </Descriptions.Item>
        <Descriptions.Item label={withHint('最新版本号', '该场景已生成的最新版本序号。')}>
          {scenario.latest_revision_no ?? '-'}
        </Descriptions.Item>
      </Descriptions>

      {validationResult ? (
        <Alert
          style={{ marginBottom: 16 }}
          type={validationResult.readiness_valid ? 'success' : 'warning'}
          showIcon
          message={validationResult.readiness_valid ? '场景校验通过' : '结构通过，但执行准备未通过'}
          description={formatMessages([...validationResult.errors, ...validationResult.warnings])}
        />
      ) : null}

      {lintResult ? (
        <Alert
          style={{ marginBottom: 16 }}
          type={lintResult.valid ? 'success' : 'warning'}
          showIcon
          message={lintResult.valid ? '规则检查通过' : '规则检查发现问题'}
          description={formatMessages([
            ...lintResult.errors.map((item) => ({ message: String(item.message || JSON.stringify(item)) })),
            ...lintResult.warnings.map((item) => ({ message: String(item.message || JSON.stringify(item)) })),
          ])}
        />
      ) : null}
    </Card>
  )
}

export default ScenarioDesignerHeaderCard
