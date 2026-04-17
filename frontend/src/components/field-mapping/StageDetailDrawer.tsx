import React, { useEffect, useState } from 'react'
import { Alert, Collapse, Descriptions, Drawer, Empty, Spin, Tag, Typography } from 'antd'
import { getStageResult } from '../../services/fieldMappingTask'

const { Paragraph, Text } = Typography

interface StageArtifact {
  id?: number
  artifact_type?: string
  artifact_key?: string
  payload_json?: unknown
  created_at?: string | null
}

interface StageChild {
  key?: string
  name?: string
  status?: string
  progress?: number
  message?: string
}

interface LineageFailureExample {
  error?: string
  message?: string
  target_field?: string
  source_field?: string
}

interface StageDetailData {
  stage_num?: number
  status?: string
  summary?: unknown
  data?: unknown
  children?: StageChild[]
  artifacts?: StageArtifact[]
}

interface StageDetailDrawerProps {
  open: boolean
  taskId: number
  stageNum: number | null
  onClose: () => void
}

const renderJson = (value: unknown) => {
  if (value == null) {
    return <Text type="secondary">暂无数据</Text>
  }

  return (
    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

const renderLineageSummary = (summary: unknown) => {
  if (!summary || typeof summary !== 'object') {
    return null
  }

  const lineage = (summary as any).lineage_rebuild
  if (!lineage || typeof lineage !== 'object') {
    return null
  }

  const skipped = Number(lineage.code_skipped_total || 0)
  const failed = Number(lineage.code_failed_total || 0)
  const examples = Array.isArray(lineage.failure_examples)
    ? (lineage.failure_examples as LineageFailureExample[])
    : []

  return (
    <div style={{ marginBottom: 16 }}>
      <Paragraph strong>Lineage rebuild summary</Paragraph>
      <Descriptions size="small" column={1} bordered style={{ marginBottom: 12 }}>
        <Descriptions.Item label="Definitions">{lineage.definitions_total ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="SQL edges">{lineage.sql_edges_total ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Code edges">{lineage.code_edges_total ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Attempted edges">{lineage.code_attempted_total ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Skipped edges">{lineage.code_skipped_total ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Failed edges">{lineage.code_failed_total ?? '-'}</Descriptions.Item>
      </Descriptions>

      {(skipped > 0 || failed > 0) ? (
        <Alert
          type={failed > 0 ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 12 }}
          message={`Code lineage persistence: skipped ${skipped}, failed ${failed}`}
        />
      ) : null}

      {examples.length ? (
        <Collapse
          size="small"
          items={[
            {
              key: 'lineage-failure-examples',
              label: `Failure examples (${examples.length})`,
              children: (
                <Descriptions size="small" column={1}>
                  {examples.map((example, index) => (
                    <Descriptions.Item key={`failure-${index}`} label={`Example ${index + 1}`}>
                      <div style={{ display: 'grid', gap: 6 }}>
                        <Text strong>{example.error || 'Unknown error'}</Text>
                        <Text type="secondary">{example.message || '-'}</Text>
                        <Text>Target field: {example.target_field || '-'}</Text>
                        <Text>Source field: {example.source_field || '-'}</Text>
                      </div>
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              ),
            },
          ]}
        />
      ) : null}
    </div>
  )
}

const StageDetailDrawer: React.FC<StageDetailDrawerProps> = ({ open, taskId, stageNum, onClose }) => {
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<StageDetailData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      if (!open || !taskId || !stageNum) {
        return
      }

      setLoading(true)
      setError('')
      try {
        const response = await getStageResult(taskId, stageNum)
        setDetail((response.data as StageDetailData) || null)
      } catch (err: any) {
        setError(err.message || '获取阶段详情失败')
        setDetail(null)
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [open, stageNum, taskId])

  return (
    <Drawer
      title={stageNum ? `阶段 ${stageNum} 详情` : '阶段详情'}
      placement="right"
      width={720}
      onClose={onClose}
      open={open}
    >
      {loading ? <Spin /> : null}
      {!loading && error ? <Alert type="error" showIcon message={error} /> : null}
      {!loading && !error && !detail ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无阶段数据" />
      ) : null}
      {!loading && !error && detail ? (
        <>
          <Descriptions size="small" column={1} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="阶段编号">{detail.stage_num ?? stageNum ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag>{detail.status || '-'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Artifacts">{detail.artifacts?.length ?? 0}</Descriptions.Item>
          </Descriptions>

          <Paragraph strong>阶段摘要</Paragraph>
          {renderLineageSummary(detail.summary ?? detail.data)}
          {renderJson(detail.summary ?? detail.data)}

          <Paragraph strong style={{ marginTop: 16 }}>子步骤进度</Paragraph>
          {detail.children?.length ? (
            <Collapse
              items={detail.children.map((child, index) => ({
                key: child.key || `child-${index}`,
                label: `${child.name || '子步骤'} / ${child.status || 'unknown'} / ${child.progress ?? 0}%`,
                children: (
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="名称">{child.name || '-'}</Descriptions.Item>
                    <Descriptions.Item label="状态">
                      <Tag>{child.status || '-'}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="进度">{child.progress ?? 0}%</Descriptions.Item>
                    <Descriptions.Item label="说明">{child.message || '-'}</Descriptions.Item>
                  </Descriptions>
                ),
              }))}
            />
          ) : (
            <Text type="secondary">当前阶段没有子步骤数据</Text>
          )}

          <Paragraph strong style={{ marginTop: 16 }}>Artifacts</Paragraph>
          {detail.artifacts?.length ? (
            <Collapse
              items={detail.artifacts.map((artifact, index) => ({
                key: String(artifact.id ?? index),
                label: `${artifact.artifact_type || 'artifact'} / ${artifact.artifact_key || '-'}`,
                children: (
                  <>
                    <Descriptions size="small" column={1} style={{ marginBottom: 12 }}>
                      <Descriptions.Item label="Artifact ID">{artifact.id ?? '-'}</Descriptions.Item>
                      <Descriptions.Item label="类型">{artifact.artifact_type || '-'}</Descriptions.Item>
                      <Descriptions.Item label="Key">{artifact.artifact_key || '-'}</Descriptions.Item>
                      <Descriptions.Item label="创建时间">{artifact.created_at || '-'}</Descriptions.Item>
                    </Descriptions>
                    {renderJson(artifact.payload_json)}
                  </>
                ),
              }))}
            />
          ) : (
            <Text type="secondary">当前阶段没有 artifacts</Text>
          )}
        </>
      ) : null}
    </Drawer>
  )
}

export default StageDetailDrawer
