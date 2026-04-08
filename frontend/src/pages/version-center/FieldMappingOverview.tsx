import React from 'react'
import {
  Button,
  Card,
  Empty,
  List,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd'
import { Link } from 'react-router-dom'
import {
  QuestionCircleOutlined,
  ReloadOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import useFieldMappingOverview from '../../hooks/field-mapping/useFieldMappingOverview'

const { Paragraph, Text, Title } = Typography

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN')
}

const getStatusColor = (status?: string) => {
  if (status === 'failed') return 'error'
  if (status === 'partial_success') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'running') return 'processing'
  return 'default'
}

const FieldMappingOverview: React.FC = () => {
  const {
    currentProject,
    currentVersion,
    loading,
    historyLoading,
    schemaCount,
    recentTasks,
    includePaths,
    includeQuery,
    includeBody,
    useAi,
    useSqlLineage,
    useCodeLineage,
    useRuntimeVerification,
    evidenceMode,
    rebuildLineageBeforeRun,
    highPriorityEnabled,
    mediumPriorityEnabled,
    lowPriorityEnabled,
    metrics,
    setIncludePaths,
    setIncludeQuery,
    setIncludeBody,
    setUseAi,
    setUseSqlLineage,
    setUseCodeLineage,
    setUseRuntimeVerification,
    setEvidenceMode,
    setRebuildLineageBeforeRun,
    setHighPriorityEnabled,
    setMediumPriorityEnabled,
    setLowPriorityEnabled,
    loadSchemaCount,
    loadTaskHistory,
    handleCreateTask,
  } = useFieldMappingOverview()

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow="Governance"
        title="字段映射总览"
        description={`在 ${currentProject?.name || '-'} / ${currentVersion?.version_number || '-'} 下发起字段映射任务，并快速进入任务详情、治理页和字段字典。`}
        metrics={metrics}
        actions={(
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => { void loadSchemaCount(); void loadTaskHistory() }}>
              刷新
            </Button>
            <Button icon={<QuestionCircleOutlined />}>
              <Link to="/version-center/field-mapping/help">查看帮助</Link>
            </Button>
            <Button>
              <Link to="/version-center/field-mapping/mappings">映射治理</Link>
            </Button>
            <Button>
              <Link to="/version-center/field-mapping/dictionary">字段字典</Link>
            </Button>
          </Space>
        )}
      />

      <Card className="workspace-table-card" bordered={false}>
        <div className="governance-filter-grid">
          <div className="governance-note-card">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div>
                <Title level={5} style={{ marginBottom: 4 }}>生成配置</Title>
                <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  在总览页配置本次字段映射任务的基础参数，然后直接发起并跳转到任务详情。
                </Paragraph>
              </div>
              <Space wrap>
                <Text type="secondary">Schema 数量</Text>
                <Tag color={schemaCount > 0 ? 'blue' : 'default'}>{schemaCount}</Tag>
              </Space>
              <div className="governance-switch-list">
                <span><Text>Path 参数</Text><Switch checked={includePaths} onChange={setIncludePaths} /></span>
                <span><Text>Query 参数</Text><Switch checked={includeQuery} onChange={setIncludeQuery} /></span>
                <span><Text>Body 参数</Text><Switch checked={includeBody} onChange={setIncludeBody} /></span>
                <span><Text>启用 AI</Text><Switch checked={useAi} onChange={setUseAi} /></span>
                <span><Text>SQL Lineage</Text><Switch checked={useSqlLineage} onChange={setUseSqlLineage} /></span>
                <span><Text>Code Lineage</Text><Switch checked={useCodeLineage} onChange={setUseCodeLineage} /></span>
                <span><Text>Runtime Verification</Text><Switch checked={useRuntimeVerification} onChange={setUseRuntimeVerification} /></span>
                <span><Text>运行前重建 Lineage</Text><Switch checked={rebuildLineageBeforeRun} onChange={setRebuildLineageBeforeRun} /></span>
                <span><Text>高优先级</Text><Switch checked={highPriorityEnabled} onChange={setHighPriorityEnabled} disabled={!useAi} /></span>
                <span><Text>中优先级</Text><Switch checked={mediumPriorityEnabled} onChange={setMediumPriorityEnabled} disabled={!useAi} /></span>
                <span><Text>低优先级</Text><Switch checked={lowPriorityEnabled} onChange={setLowPriorityEnabled} disabled={!useAi} /></span>
              </div>
              <Space wrap>
                <Text type="secondary">证据模式</Text>
                <Select value={evidenceMode} onChange={(value) => setEvidenceMode(value as typeof evidenceMode)} style={{ width: 180 }}>
                  <Select.Option value="balanced">balanced</Select.Option>
                  <Select.Option value="conservative">conservative</Select.Option>
                  <Select.Option value="aggressive">aggressive</Select.Option>
                </Select>
              </Space>
              <Button type="primary" icon={<RocketOutlined />} loading={loading} onClick={() => void handleCreateTask()}>
                生成新任务
              </Button>
            </Space>
          </div>

          <div className="governance-note-card">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div>
                <Title level={5} style={{ marginBottom: 4 }}>最近任务</Title>
                <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  这里只展示最近几条任务摘要。进入详情页后再查看阶段、建议结果和任务操作。
                </Paragraph>
              </div>
              {recentTasks.length ? (
                <List
                  loading={historyLoading}
                  dataSource={recentTasks}
                  renderItem={(item) => (
                    <List.Item
                      actions={[
                        <Button key={`view-${item.id}`} type="link">
                          <Link to={`/version-center/field-mapping/tasks/${item.id}`}>进入任务详情</Link>
                        </Button>,
                      ]}
                    >
                      <List.Item.Meta
                        title={(
                          <Space wrap>
                            <Text strong>任务 #{item.id}</Text>
                            <Tag color={getStatusColor(item.status)}>{item.status}</Tag>
                            <Text type="secondary">{item.progress}%</Text>
                          </Space>
                        )}
                        description={(
                          <Space direction="vertical" size={4}>
                            <Text type="secondary">创建时间：{formatDateTime(item.created_at)}</Text>
                            <Text type="secondary">结果数：{item.result_count ?? '-'}</Text>
                            {item.error_message ? <Text type="danger">{item.error_message}</Text> : null}
                          </Space>
                        )}
                      />
                    </List.Item>
                  )}
                />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有字段映射任务" />
              )}
            </Space>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default FieldMappingOverview
