import React, { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { EyeOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'

import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import { getProjectEnvironments } from '../../services/environments'
import { getExecutions } from '../../services/executions'
import { useProjectStore } from '../../store/project'
import type { ExecutionSummary } from '../../types/execution'

const { Search } = Input
const { Text } = Typography

const statusColorMap: Record<string, string> = {
  completed: 'success',
  passed: 'success',
  failed: 'error',
  error: 'error',
  partial_failed: 'warning',
  running: 'processing',
  pending: 'default',
  skipped: 'default',
}

const formatDateTime = (value: string | null) => {
  if (!value) {
    return '-'
  }
  return new Date(value).toLocaleString()
}

const ExecutionCenter: React.FC = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { currentProject, currentVersion } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [executions, setExecutions] = useState<ExecutionSummary[]>([])
  const [total, setTotal] = useState(0)
  const [environmentOptions, setEnvironmentOptions] = useState<Array<{ id: number; name: string }>>([])
  const [filters, setFilters] = useState({
    page: 1,
    page_size: 20,
    execution_type: undefined as string | undefined,
    status: undefined as string | undefined,
    result_status: undefined as string | undefined,
    environment_id: undefined as number | undefined,
    version_id: currentVersion?.id,
    case_id: searchParams.get('case_id') ? Number(searchParams.get('case_id')) : undefined,
    definition_id: searchParams.get('definition_id') ? Number(searchParams.get('definition_id')) : undefined,
    keyword: searchParams.get('keyword') || '',
  })

  useEffect(() => {
    setFilters((current) => ({
      ...current,
      version_id: currentVersion?.id,
      page: 1,
    }))
  }, [currentVersion?.id])

  useEffect(() => {
    const loadEnvironments = async () => {
      if (!currentProject?.id) {
        setEnvironmentOptions([])
        return
      }
      try {
        const response = await getProjectEnvironments(currentProject.id, 1, 100)
        setEnvironmentOptions((response.items || []).map((item) => ({ id: item.id, name: item.name })))
      } catch (error) {
        console.error('加载环境列表失败', error)
      }
    }

    void loadEnvironments()
  }, [currentProject?.id])

  const loadExecutions = async () => {
    setLoading(true)
    try {
      const response = await getExecutions(filters)
      setExecutions(response.items || [])
      setTotal(response.total || 0)
    } catch (error: any) {
      message.error(error.message || '加载执行记录失败')
      setExecutions([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadExecutions()
  }, [
    filters.page,
    filters.page_size,
    filters.execution_type,
    filters.status,
    filters.result_status,
    filters.environment_id,
    filters.version_id,
    filters.case_id,
    filters.definition_id,
    filters.keyword,
  ])

  const summary = useMemo(() => {
    return executions.reduce(
      (acc, item) => {
        acc.total += 1
        acc.passed += item.result_status === 'passed' ? 1 : 0
        acc.failed += item.result_status === 'failed' || item.result_status === 'partial_failed' ? 1 : 0
        acc.running += item.status === 'running' || item.status === 'pending' ? 1 : 0
        return acc
      },
      { total: 0, passed: 0, failed: 0, running: 0 },
    )
  }, [executions])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <WorkspaceModuleHero
        eyebrow="Operations"
        title="执行中心"
        description="统一查看执行记录、版本与环境筛选，以及执行详情和联调入口。"
        metrics={[
          { label: '当前项目', value: currentProject?.name || '未选择' },
          { label: '当前版本', value: currentVersion?.version_number || '未选择' },
          { label: '记录总数', value: total },
        ]}
      />

      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title="当前页记录数" value={summary.total} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="通过" value={summary.passed} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="失败" value={summary.failed} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="运行中" value={summary.running} />
          </Card>
        </Col>
      </Row>

      <Card title="筛选条件" extra={<Button icon={<ReloadOutlined />} onClick={() => void loadExecutions()}>刷新</Button>}>
        <Row gutter={[16, 16]}>
          <Col span={8}>
            <Search
              allowClear
              placeholder="搜索标题或触发方式"
              value={filters.keyword}
              onSearch={(value) => setFilters((current) => ({ ...current, keyword: value, page: 1 }))}
              onChange={(event) => setFilters((current) => ({ ...current, keyword: event.target.value }))}
            />
          </Col>
          <Col span={4}>
            <Select
              allowClear
              style={{ width: '100%' }}
              placeholder="执行类型"
              value={filters.execution_type}
              onChange={(value) => setFilters((current) => ({ ...current, execution_type: value, page: 1 }))}
              options={[
                { label: '单执行', value: 'single' },
                { label: '批执行', value: 'batch' },
                { label: '场景执行', value: 'scenario' },
                { label: '套件执行', value: 'suite' },
              ]}
            />
          </Col>
          <Col span={4}>
            <Select
              allowClear
              style={{ width: '100%' }}
              placeholder="执行状态"
              value={filters.status}
              onChange={(value) => setFilters((current) => ({ ...current, status: value, page: 1 }))}
              options={[
                { label: '待执行', value: 'pending' },
                { label: '执行中', value: 'running' },
                { label: '已完成', value: 'completed' },
                { label: '失败', value: 'failed' },
              ]}
            />
          </Col>
          <Col span={4}>
            <Select
              allowClear
              style={{ width: '100%' }}
              placeholder="结果状态"
              value={filters.result_status}
              onChange={(value) => setFilters((current) => ({ ...current, result_status: value, page: 1 }))}
              options={[
                { label: '通过', value: 'passed' },
                { label: '失败', value: 'failed' },
                { label: '部分失败', value: 'partial_failed' },
                { label: '跳过', value: 'skipped' },
              ]}
            />
          </Col>
          <Col span={4}>
            <Select
              allowClear
              style={{ width: '100%' }}
              placeholder="环境"
              value={filters.environment_id}
              onChange={(value) => setFilters((current) => ({ ...current, environment_id: value, page: 1 }))}
              options={environmentOptions.map((item) => ({ label: item.name, value: item.id }))}
            />
          </Col>
        </Row>
        <div style={{ marginTop: 12 }}>
          <Text type="secondary">
            当前项目：{currentProject?.name || '未选择'}，当前版本：{currentVersion?.version_number || '未选择'}
          </Text>
          {filters.case_id || filters.definition_id ? (
            <div>
              <Text type="secondary">
                精准筛选：用例 {filters.case_id || '-'} / 接口 {filters.definition_id || '-'}
              </Text>
            </div>
          ) : null}
        </div>
      </Card>

      <Card title="执行记录">
        <Table<ExecutionSummary>
          rowKey="id"
          loading={loading}
          dataSource={executions}
          locale={{ emptyText: <Empty description="暂无执行记录" /> }}
          pagination={{
            current: filters.page,
            pageSize: filters.page_size,
            total,
            onChange: (page, pageSize) => {
              setFilters((current) => ({ ...current, page, page_size: pageSize }))
            },
          }}
          columns={[
            {
              title: '标题',
              dataIndex: 'title',
              render: (_, record) => (
                <Space direction="vertical" size={2}>
                  <Text strong>{record.title || `执行 #${record.id}`}</Text>
                  <Text type="secondary">ID: {record.id}</Text>
                </Space>
              ),
            },
            {
              title: '类型',
              dataIndex: 'execution_type',
              width: 110,
              render: (value: string) => <Tag>{value}</Tag>,
            },
            {
              title: '执行状态',
              dataIndex: 'status',
              width: 110,
              render: (value: string) => <Tag color={statusColorMap[value] || 'default'}>{value}</Tag>,
            },
            {
              title: '结果状态',
              dataIndex: 'result_status',
              width: 120,
              render: (value: string | null) => <Tag color={statusColorMap[value || ''] || 'default'}>{value || '-'}</Tag>,
            },
            {
              title: '环境/版本',
              key: 'env_version',
              width: 220,
              render: (_, record) => (
                <Space direction="vertical" size={2}>
                  <Text>{record.environment_name || '未指定环境'}</Text>
                  <Text type="secondary">{record.version_name || '未指定版本'}</Text>
                </Space>
              ),
            },
            {
              title: '统计',
              key: 'stats',
              width: 180,
              render: (_, record) => (
                <Space direction="vertical" size={2}>
                  <Text>总数 {record.total}</Text>
                  <Text type="secondary">通过 {record.passed} / 失败 {record.failed}</Text>
                </Space>
              ),
            },
            {
              title: '来源关系',
              key: 'relations',
              width: 180,
              render: (_, record) => (
                <Space direction="vertical" size={2}>
                  <Text type="secondary">父执行：{record.parent_execution_id || '-'}</Text>
                  <Text type="secondary">来源执行：{record.source_execution_id || '-'}</Text>
                </Space>
              ),
            },
            {
              title: '触发方式',
              dataIndex: 'triggered_by',
              width: 120,
              render: (value: string | null) => value || '-',
            },
            {
              title: '开始时间',
              dataIndex: 'started_at',
              width: 180,
              render: (value: string | null) => formatDateTime(value),
            },
            {
              title: '耗时',
              dataIndex: 'duration',
              width: 100,
              render: (value: number | null) => `${value ?? 0} ms`,
            },
            {
              title: '操作',
              key: 'action',
              width: 260,
              fixed: 'right',
              render: (_, record) => (
                <Space size="small" wrap>
                  <Button
                    type="link"
                    icon={<EyeOutlined />}
                    onClick={() => navigate(`/operations/executions/${record.id}`)}
                  >
                    详情
                  </Button>
                  {record.parent_execution_id ? (
                    <Button
                      type="link"
                      onClick={() => navigate(`/operations/executions/${record.parent_execution_id}`)}
                    >
                      父执行
                    </Button>
                  ) : null}
                  {record.source_execution_id ? (
                    <Button
                      type="link"
                      onClick={() => navigate(`/operations/executions/${record.source_execution_id}`)}
                    >
                      来源执行
                    </Button>
                  ) : null}
                </Space>
              ),
            },
          ]}
          scroll={{ x: 1500 }}
        />
      </Card>
    </Space>
  )
}

export default ExecutionCenter
