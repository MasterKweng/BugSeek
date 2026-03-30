import React, { useEffect, useMemo, useState } from 'react'
import { max, scaleBand, scaleLinear } from 'd3'
import {
  Card,
  Col,
  DatePicker,
  Empty,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Typography,
  message,
} from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import { getProjectEnvironments } from '../../services/environments'
import {
  getExecutionEnvironmentComparison,
  getExecutionReportFailures,
  getExecutionReportPerformance,
  getExecutionReportSummary,
  getExecutionReportTrends,
  getExecutionVersionComparison,
} from '../../services/executions'
import { useProjectStore } from '../../store/project'
import type {
  ExecutionComparisonResponse,
  ExecutionFailureResponse,
  ExecutionPerformanceResponse,
  ExecutionReportSummary as ExecutionReportSummaryType,
  ExecutionTrendResponse,
} from '../../types/execution'

const { RangePicker } = DatePicker
const { Text } = Typography

const palette = {
  green: '#2f7d32',
  blue: '#1677ff',
  orange: '#fa8c16',
  red: '#ff4d4f',
  ink: '#1f1f1f',
  grid: '#e5e7eb',
  fillBlue: 'rgba(22, 119, 255, 0.14)',
}

const barColor = (value: number) => {
  if (value >= 90) return palette.green
  if (value >= 75) return palette.blue
  if (value >= 60) return palette.orange
  return palette.red
}

const TrendLineChart: React.FC<{
  items: ExecutionTrendResponse['items']
}> = ({ items }) => {
  if (!items.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无趋势数据" />
  }

  const width = 640
  const height = 260
  const margin = { top: 20, right: 24, bottom: 44, left: 40 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom
  const peak = max(items, (item) => item.total_results) || 1
  const xStep = items.length > 1 ? innerWidth / (items.length - 1) : innerWidth / 2
  const y = scaleLinear().domain([0, peak]).range([innerHeight, 0])

  const linePath = items
    .map((item, index) => {
      const x = margin.left + (items.length === 1 ? innerWidth / 2 : index * xStep)
      const pointY = margin.top + y(item.total_results)
      return `${index === 0 ? 'M' : 'L'} ${x} ${pointY}`
    })
    .join(' ')

  const areaPath = `${linePath} L ${margin.left + innerWidth} ${margin.top + innerHeight} L ${margin.left} ${
    margin.top + innerHeight
  } Z`

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 260 }}>
      {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
        const lineY = margin.top + innerHeight * tick
        return <line key={tick} x1={margin.left} x2={margin.left + innerWidth} y1={lineY} y2={lineY} stroke={palette.grid} />
      })}
      <path d={areaPath} fill={palette.fillBlue} />
      <path d={linePath} fill="none" stroke={palette.blue} strokeWidth={3} />
      {items.map((item, index) => {
        const x = margin.left + (items.length === 1 ? innerWidth / 2 : index * xStep)
        const pointY = margin.top + y(item.total_results)
        return (
          <g key={item.bucket}>
            <circle cx={x} cy={pointY} r={5} fill={barColor(item.pass_rate)} stroke="#fff" strokeWidth={2} />
            <text x={x} y={pointY - 12} textAnchor="middle" fontSize="11" fill={palette.ink}>
              {item.total_results}
            </text>
            <text x={x} y={height - 16} textAnchor="middle" fontSize="11" fill="#666">
              {item.bucket}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

const ComparisonBarChart: React.FC<{
  items: Array<{ label: string; passRate: number; total: number }>
  emptyText: string
}> = ({ items, emptyText }) => {
  if (!items.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
  }

  const width = 640
  const height = 280
  const margin = { top: 20, right: 24, bottom: 60, left: 40 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom
  const x = scaleBand<string>().domain(items.map((item) => item.label)).range([0, innerWidth]).padding(0.24)
  const y = scaleLinear().domain([0, 100]).range([innerHeight, 0])

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 280 }}>
      {[0, 25, 50, 75, 100].map((tick) => {
        const lineY = margin.top + y(tick)
        return (
          <g key={tick}>
            <line x1={margin.left} x2={margin.left + innerWidth} y1={lineY} y2={lineY} stroke={palette.grid} />
            <text x={margin.left - 10} y={lineY + 4} textAnchor="end" fontSize="11" fill="#666">
              {tick}
            </text>
          </g>
        )
      })}
      {items.map((item) => {
        const bandX = x(item.label) ?? 0
        const barHeight = innerHeight - y(item.passRate)
        const barY = margin.top + y(item.passRate)
        const barWidth = x.bandwidth()
        return (
          <g key={item.label}>
            <rect
              x={margin.left + bandX}
              y={barY}
              width={barWidth}
              height={barHeight}
              rx={8}
              fill={barColor(item.passRate)}
            />
            <text
              x={margin.left + bandX + barWidth / 2}
              y={barY - 8}
              textAnchor="middle"
              fontSize="11"
              fill={palette.ink}
            >
              {item.passRate.toFixed(1)}%
            </text>
            <text
              x={margin.left + bandX + barWidth / 2}
              y={height - 28}
              textAnchor="middle"
              fontSize="11"
              fill="#666"
            >
              {item.label}
            </text>
            <text
              x={margin.left + bandX + barWidth / 2}
              y={height - 12}
              textAnchor="middle"
              fontSize="10"
              fill="#999"
            >
              {item.total} 条
            </text>
          </g>
        )
      })}
    </svg>
  )
}

const ExecutionReports: React.FC = () => {
  const { currentProject, currentVersion } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [environmentOptions, setEnvironmentOptions] = useState<Array<{ label: string; value: number }>>([])
  const [filters, setFilters] = useState<{
    version_id?: number
    environment_id?: number
    dates?: [Dayjs, Dayjs] | null
    group_by: 'day' | 'week' | 'month'
  }>({
    version_id: currentVersion?.id,
    environment_id: undefined,
    dates: null,
    group_by: 'day',
  })
  const [summary, setSummary] = useState<ExecutionReportSummaryType | null>(null)
  const [trends, setTrends] = useState<ExecutionTrendResponse | null>(null)
  const [failures, setFailures] = useState<ExecutionFailureResponse | null>(null)
  const [performance, setPerformance] = useState<ExecutionPerformanceResponse | null>(null)
  const [environmentComparison, setEnvironmentComparison] = useState<ExecutionComparisonResponse | null>(null)
  const [versionComparison, setVersionComparison] = useState<ExecutionComparisonResponse | null>(null)

  useEffect(() => {
    setFilters((current) => ({ ...current, version_id: currentVersion?.id }))
  }, [currentVersion?.id])

  useEffect(() => {
    const loadEnvironments = async () => {
      if (!currentProject?.id) {
        setEnvironmentOptions([])
        return
      }
      try {
        const response = await getProjectEnvironments(currentProject.id, 1, 100)
        setEnvironmentOptions((response.items || []).map((item) => ({ label: item.name, value: item.id })))
      } catch (error) {
        console.error('加载环境失败', error)
      }
    }

    void loadEnvironments()
  }, [currentProject?.id])

  const buildParams = () => ({
    version_id: filters.version_id,
    environment_id: filters.environment_id,
    started_after: filters.dates?.[0] ? dayjs(filters.dates[0]).startOf('day').toISOString() : undefined,
    started_before: filters.dates?.[1] ? dayjs(filters.dates[1]).endOf('day').toISOString() : undefined,
  })

  const loadReports = async () => {
    setLoading(true)
    try {
      const params = buildParams()
      const [nextSummary, nextTrends, nextFailures, nextPerformance, nextEnvironmentComparison, nextVersionComparison] =
        await Promise.all([
          getExecutionReportSummary(params),
          getExecutionReportTrends({ ...params, group_by: filters.group_by }),
          getExecutionReportFailures(params),
          getExecutionReportPerformance(params),
          getExecutionEnvironmentComparison({
            version_id: params.version_id,
            started_after: params.started_after,
            started_before: params.started_before,
          }),
          getExecutionVersionComparison({
            environment_id: params.environment_id,
            started_after: params.started_after,
            started_before: params.started_before,
          }),
        ])

      setSummary(nextSummary)
      setTrends(nextTrends)
      setFailures(nextFailures)
      setPerformance(nextPerformance)
      setEnvironmentComparison(nextEnvironmentComparison)
      setVersionComparison(nextVersionComparison)
    } catch (error: any) {
      message.error(error.message || '加载执行报表失败')
      setSummary(null)
      setTrends(null)
      setFailures(null)
      setPerformance(null)
      setEnvironmentComparison(null)
      setVersionComparison(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadReports()
  }, [filters.version_id, filters.environment_id, filters.group_by, filters.dates?.[0]?.valueOf(), filters.dates?.[1]?.valueOf()])

  const environmentChartData = useMemo(
    () =>
      (environmentComparison?.items || []).map((item) => ({
        label: item.environment_name || `环境 ${item.environment_id || '-'}`,
        passRate: item.pass_rate,
        total: item.total_results,
      })),
    [environmentComparison],
  )

  const versionChartData = useMemo(
    () =>
      (versionComparison?.items || []).map((item) => ({
        label: item.version_number || `版本 ${item.version_id || '-'}`,
        passRate: item.pass_rate,
        total: item.total_results,
      })),
    [versionComparison],
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <WorkspaceModuleHero
        eyebrow="Operations"
        title="执行报表"
        description="统一查看执行质量、趋势、失败分布、性能排行，以及环境和版本对比。"
        metrics={[
          { label: '当前项目', value: currentProject?.name || '未选择' },
          { label: '当前版本', value: currentVersion?.version_number || '未选择' },
          { label: '环境数量', value: environmentOptions.length },
        ]}
      />

      <Card title="报表筛选">
        <Row gutter={[16, 16]}>
          <Col span={6}>
            <Select
              allowClear
              style={{ width: '100%' }}
              placeholder="环境"
              value={filters.environment_id}
              onChange={(value) => setFilters((current) => ({ ...current, environment_id: value }))}
              options={environmentOptions}
            />
          </Col>
          <Col span={6}>
            <Select
              style={{ width: '100%' }}
              placeholder="聚合粒度"
              value={filters.group_by}
              onChange={(value) => setFilters((current) => ({ ...current, group_by: value }))}
              options={[
                { label: '按天', value: 'day' },
                { label: '按周', value: 'week' },
                { label: '按月', value: 'month' },
              ]}
            />
          </Col>
          <Col span={12}>
            <RangePicker
              style={{ width: '100%' }}
              value={filters.dates || null}
              onChange={(values) => setFilters((current) => ({ ...current, dates: values as [Dayjs, Dayjs] | null }))}
            />
          </Col>
        </Row>
        <div style={{ marginTop: 12 }}>
          <Text type="secondary">
            当前项目：{currentProject?.name || '未选择'}，当前版本：{currentVersion?.version_number || '未选择'}
          </Text>
        </div>
      </Card>

      {!summary ? (
        <Empty description="暂无报表数据" />
      ) : (
        <>
          <Row gutter={16}>
            <Col span={4}><Card loading={loading}><Statistic title="执行次数" value={summary.total_executions} /></Card></Col>
            <Col span={4}><Card loading={loading}><Statistic title="执行结果数" value={summary.total_results} /></Card></Col>
            <Col span={4}><Card loading={loading}><Statistic title="通过率" value={summary.pass_rate} suffix="%" precision={2} /></Card></Col>
            <Col span={4}><Card loading={loading}><Statistic title="失败率" value={summary.fail_rate} suffix="%" precision={2} /></Card></Col>
            <Col span={4}><Card loading={loading}><Statistic title="错误数" value={summary.error_results} /></Card></Col>
            <Col span={4}><Card loading={loading}><Statistic title="平均耗时" value={summary.avg_response_time} suffix="ms" precision={2} /></Card></Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Card title="质量总览" loading={loading}>
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <div>
                    <Text>通过率</Text>
                    <Progress percent={summary.pass_rate} strokeColor={barColor(summary.pass_rate)} />
                  </div>
                  <div>
                    <Text>失败率</Text>
                    <Progress percent={summary.fail_rate} status="exception" />
                  </div>
                  <div>
                    <Text>错误占比</Text>
                    <Progress
                      percent={summary.total_results > 0 ? Number(((summary.error_results / summary.total_results) * 100).toFixed(2)) : 0}
                      strokeColor={palette.orange}
                    />
                  </div>
                </Space>
              </Card>
            </Col>
            <Col span={16}>
              <Card title="趋势折线图" loading={loading}>
                <TrendLineChart items={trends?.items || []} />
              </Card>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="环境通过率柱状图" loading={loading}>
                <ComparisonBarChart items={environmentChartData} emptyText="暂无环境对比数据" />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="版本通过率柱状图" loading={loading}>
                <ComparisonBarChart items={versionChartData} emptyText="暂无版本对比数据" />
              </Card>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="失败 Top" loading={loading}>
                <Table
                  size="small"
                  rowKey={(record) => `${record.definition_id || record.case_id || record.response_code || record.error_message}`}
                  pagination={false}
                  dataSource={failures?.by_definition || []}
                  columns={[
                    { title: '目标', dataIndex: 'target_name' },
                    { title: '定义 ID', dataIndex: 'definition_id' },
                    { title: '失败次数', dataIndex: 'failed_count' },
                  ]}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="性能排行" loading={loading}>
                <Table
                  size="small"
                  rowKey={(record) => `${record.case_id || record.definition_id}`}
                  pagination={false}
                  dataSource={performance?.slowest_cases || []}
                  columns={[
                    { title: '目标', dataIndex: 'target_name' },
                    { title: '平均耗时', dataIndex: 'avg_response_time', render: (value: number) => `${value} ms` },
                    { title: '最大耗时', dataIndex: 'max_response_time', render: (value: number) => `${value} ms` },
                  ]}
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </Space>
  )
}

export default ExecutionReports
