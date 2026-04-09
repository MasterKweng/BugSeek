import React, { useEffect, useMemo, useState } from 'react'
import { Button, Card, Result, Space, Typography, message } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import SuggestionsTable from '../../components/field-mapping/SuggestionsTable'
import SuggestionDetailDrawer from '../../components/field-mapping/SuggestionDetailDrawer'
import TaskHeaderCard from '../../components/field-mapping/TaskHeaderCard'
import api from '../../services/api'
import { batchRejectSuggestions, type FieldMappingSuggestion } from '../../services/fieldMappingSuggestion'
import { getAsyncTask, type AsyncTask } from '../../services/fieldMappingTask'
import './ScenarioFieldMapping.css'

const { Paragraph } = Typography

interface ScenarioNode {
  ref_id: number
  input_mapping?: Record<string, string>
}

interface ScenarioDetail {
  name: string
  description?: string
  nodes?: ScenarioNode[]
}

interface AcceptedMapping {
  suggestion_id: number
  definition_id: number
  api_field_path: string
  db_table?: string
  db_column?: string
}

const ScenarioFieldMapping: React.FC = () => {
  const navigate = useNavigate()
  const { scenarioId } = useParams()
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null)
  const [task, setTask] = useState<AsyncTask | null>(null)
  const [suggestions, setSuggestions] = useState<FieldMappingSuggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [selectedSuggestion, setSelectedSuggestion] = useState<FieldMappingSuggestion | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [suggestionPage, setSuggestionPage] = useState(1)
  const [suggestionPageSize, setSuggestionPageSize] = useState(20)

  const taskId = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    const raw = params.get('task_id')
    const parsed = Number(raw)
    return Number.isNaN(parsed) ? null : parsed
  }, [])

  useEffect(() => {
    void loadScenario()
    void loadSuggestions()
    void loadTask()
  }, [scenarioId])

  const loadScenario = async () => {
    if (!scenarioId) return
    try {
      const response = await api.get(`/scenarios/${scenarioId}`)
      if (response.code === 0) {
        setScenario(response.data)
      }
    } catch (error) {
      console.error('加载场景失败:', error)
    }
  }

  const loadSuggestions = async () => {
    if (!taskId) {
      message.warning('未找到映射任务 ID')
      return
    }
    setLoading(true)
    try {
      const response = await api.get(`/field-mappings/suggestions?task_id=${taskId}`)
      if (response.code === 0) {
        setSuggestions(response.data.items || [])
      }
    } catch (error: any) {
      console.error('加载映射建议失败:', error)
      message.error(error.message || '加载映射建议失败')
    } finally {
      setLoading(false)
    }
  }

  const loadTask = async () => {
    if (!taskId) return
    try {
      const response = await getAsyncTask(taskId)
      setTask(response.data || null)
    } catch (error) {
      console.error('加载任务摘要失败:', error)
      setTask(null)
    }
  }

  const applyMappingToScenario = async (items: AcceptedMapping[]) => {
    if (!scenario || !scenarioId) return
    try {
      const updatedNodes = (scenario.nodes || []).map((node) => {
        const nodeMappings = items.filter((item) => item.definition_id === node.ref_id)
        if (nodeMappings.length === 0) return node

        const inputMapping = { ...(node.input_mapping || {}) }
        nodeMappings.forEach((mapping) => {
          if (!mapping.db_table || !mapping.db_column) return
          const fieldPath = mapping.api_field_path.replace(/^body\./, '')
          inputMapping[fieldPath] = `{{${mapping.db_table}_${mapping.db_column}}}`
        })

        return { ...node, input_mapping: inputMapping }
      })

      const response = await api.put(`/scenarios/${scenarioId}`, {
        name: scenario.name,
        description: scenario.description,
        nodes: updatedNodes,
      })

      if (response.code === 0) {
        message.success('映射已应用到场景节点')
        setScenario({ ...scenario, nodes: updatedNodes })
      }
    } catch (error) {
      console.error('应用映射到场景失败:', error)
      message.warning('映射已确认，但应用到场景失败，请手动配置')
    }
  }

  const handleConfirm = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请至少选择一个映射建议')
      return
    }

    setConfirming(true)
    try {
      const items: AcceptedMapping[] = selectedRowKeys
        .map((key) => suggestions.find((item) => item.id === key))
        .filter((item): item is FieldMappingSuggestion => Boolean(item))
        .map((item) => ({
          suggestion_id: item.id!,
          definition_id: item.definition_id,
          api_field_path: item.api_field_path,
          db_table: item.top_candidate?.db_table || item.candidates?.[0]?.db_table,
          db_column: item.top_candidate?.db_column || item.candidates?.[0]?.db_column,
        }))

      const response = await api.post('/field-mappings/suggestions/accept', { items })
      if (response.code === 0) {
        message.success(`成功确认 ${items.length} 个映射建议`)
        await applyMappingToScenario(items)
      } else {
        message.error(response.message || '确认映射失败')
      }
    } catch (error: any) {
      console.error('确认映射失败:', error)
      message.error(error.message || '确认映射失败')
    } finally {
      setConfirming(false)
    }
  }

  const handleReject = async () => {
    const suggestionIds = selectedRowKeys
      .map((key) => suggestions.find((item) => item.id === key)?.id)
      .filter((id): id is number => typeof id === 'number')

    if (suggestionIds.length === 0) {
      message.warning('请至少选择一个映射建议')
      return
    }

    setRejecting(true)
    try {
      await batchRejectSuggestions({ suggestion_ids: suggestionIds })
      message.success(`成功拒绝 ${suggestionIds.length} 个映射建议`)
      setSelectedRowKeys([])
      await loadSuggestions()
      await loadTask()
    } catch (error: any) {
      console.error('拒绝映射失败:', error)
      message.error(error.message || '拒绝映射失败')
    } finally {
      setRejecting(false)
    }
  }

  if (!scenarioId) {
    return (
      <Result
        status="404"
        title="场景不存在"
        subTitle="当前路由没有提供有效的场景 ID。"
      />
    )
  }

  return (
    <div className="scenario-field-mapping">
      <Card
        title="场景字段映射确认"
        extra={(
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/scenario/${scenarioId}`)}>
              返回场景
            </Button>
            <Button
              type="primary"
              onClick={() => void handleConfirm()}
              loading={confirming}
              disabled={selectedRowKeys.length === 0}
            >
              确认并应用 ({selectedRowKeys.length})
            </Button>
          </Space>
        )}
      >
        {task ? <TaskHeaderCard task={task} /> : null}

        {scenario ? (
          <div className="workspace-inline-note">
            {`场景：${scenario.name}，包含 ${scenario.nodes?.length || 0} 个节点和 ${suggestions.length} 个字段映射建议。`}
          </div>
        ) : null}

        {!taskId ? (
          <Paragraph type="secondary" style={{ marginTop: 12 }}>
            当前没有 task_id，无法加载字段映射建议。请从字段映射任务结果页进入场景应用。
          </Paragraph>
        ) : null}

        <div style={{ marginTop: 16, marginBottom: 16 }}>
          <Space wrap>
            <Button
              type="primary"
              onClick={() => void handleConfirm()}
              loading={confirming}
              disabled={selectedRowKeys.length === 0}
            >
              确认并应用 ({selectedRowKeys.length})
            </Button>
            <Button
              danger
              onClick={() => void handleReject()}
              loading={rejecting}
              disabled={selectedRowKeys.length === 0}
            >
              批量拒绝 ({selectedRowKeys.length})
            </Button>
          </Space>
        </div>

        <SuggestionsTable
          loading={loading}
          suggestions={suggestions}
          selectedRowKeys={selectedRowKeys}
          onSelectedRowKeysChange={setSelectedRowKeys}
          onViewDetail={(suggestion) => {
            setSelectedSuggestion(suggestion)
            setDetailOpen(true)
          }}
          suggestionPage={suggestionPage}
          suggestionPageSize={suggestionPageSize}
          suggestionTotal={suggestions.length}
          onPageChange={(page, pageSize) => {
            setSuggestionPage(page)
            setSuggestionPageSize(pageSize)
          }}
        />
      </Card>

      <SuggestionDetailDrawer
        open={detailOpen}
        suggestion={selectedSuggestion}
        onClose={() => setDetailOpen(false)}
      />
    </div>
  )
}

export default ScenarioFieldMapping
