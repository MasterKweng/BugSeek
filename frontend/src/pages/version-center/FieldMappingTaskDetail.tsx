import React from 'react'
import { Button, Card, Collapse, Result, Space } from 'antd'
import { Link, useParams } from 'react-router-dom'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import TaskHeaderCard from '../../components/field-mapping/TaskHeaderCard'
import TaskStagesPanel from '../../components/field-mapping/TaskStagesPanel'
import SuggestionsToolbar from '../../components/field-mapping/SuggestionsToolbar'
import SuggestionsTable from '../../components/field-mapping/SuggestionsTable'
import SuggestionDetailDrawer from '../../components/field-mapping/SuggestionDetailDrawer'
import StageDetailDrawer from '../../components/field-mapping/StageDetailDrawer'
import ConsistencyDrawer from '../../components/field-mapping/ConsistencyDrawer'
import TaskHistoryDrawer from '../../components/field-mapping/TaskHistoryDrawer'
import TaskEvidencePanel from '../../components/field-mapping/TaskEvidencePanel'
import PartialSuccessRecoveryCard from '../../components/field-mapping/PartialSuccessRecoveryCard'
import useFieldMappingTaskDetail from '../../hooks/field-mapping/useFieldMappingTaskDetail'

const FieldMappingTaskDetail: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>()
  const parsedTaskId = Number(taskId)
  const {
    currentProject,
    currentVersion,
    loading,
    task,
    selectedRowKeys,
    selectedSuggestion,
    detailOpen,
    historyDrawerOpen,
    stageDetailOpen,
    consistencyDrawerOpen,
    selectedStageNum,
    actionLoading,
    retryingStageNum,
    replayLoading,
    suggestionPage,
    suggestionPageSize,
    suggestionTotal,
    searchKeyword,
    pathFilter,
    statusFilter,
    methodFilter,
    fieldTypeFilter,
    decisionSourceFilter,
    relationTypeFilter,
    visibleSuggestions,
    selectedSuggestions,
    metrics,
    evidenceLoading,
    evidenceContribution,
    setSelectedRowKeys,
    setSelectedSuggestion,
    setDetailOpen,
    setHistoryDrawerOpen,
    setStageDetailOpen,
    setConsistencyDrawerOpen,
    setSelectedStageNum,
    setSuggestionPage,
    setSuggestionPageSize,
    setSearchKeyword,
    setPathFilter,
    setStatusFilter,
    setMethodFilter,
    setFieldTypeFilter,
    setDecisionSourceFilter,
    setRelationTypeFilter,
    reloadTaskContext,
    loadSuggestions,
    handleConfirmSuggestions,
    handleRejectSuggestions,
    handleCancelTask,
    handleResumeTask,
    handleResetTask,
    handleRetryStage,
    handleReplaySuggestions,
  } = useFieldMappingTaskDetail(parsedTaskId)

  if (!parsedTaskId || Number.isNaN(parsedTaskId)) {
    return (
      <Result
        status="404"
        title="任务不存在"
        subTitle="当前路由没有提供有效的字段映射任务 ID。"
        extra={(
          <Button type="primary">
            <Link to="/version-center/field-mapping">返回字段映射总览</Link>
          </Button>
        )}
      />
    )
  }

  if (!currentProject || !currentVersion) {
    return (
      <Result
        status="warning"
        title="请先选择项目和版本"
        subTitle="字段映射任务详情依赖项目和版本上下文。"
      />
    )
  }

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow="Governance"
        title={`字段映射任务 #${parsedTaskId}`}
        description={`查看 ${currentProject.name} / ${currentVersion.version_number} 下任务 #${parsedTaskId} 的执行状态、阶段进度与建议结果。`}
        metrics={metrics}
        actions={(
          <Space wrap>
            <Button>
              <Link to="/version-center/field-mapping">返回总览</Link>
            </Button>
            <Button onClick={() => setHistoryDrawerOpen(true)}>
              任务历史
            </Button>
            <Button onClick={() => setConsistencyDrawerOpen(true)}>
              Consistency
            </Button>
            <Button onClick={() => void reloadTaskContext()}>
              刷新
            </Button>
          </Space>
        )}
      />

      <TaskHeaderCard
        task={task}
        actionLoading={actionLoading}
        onCancel={() => void handleCancelTask()}
        onResume={() => void handleResumeTask()}
        onReset={() => void handleResetTask()}
      />

      <Card className="workspace-table-card" bordered={false}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <SuggestionsToolbar
            searchKeyword={searchKeyword}
            onSearchKeywordChange={setSearchKeyword}
            pathFilter={pathFilter}
            onPathFilterChange={setPathFilter}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            methodFilter={methodFilter}
            onMethodFilterChange={setMethodFilter}
            fieldTypeFilter={fieldTypeFilter}
            onFieldTypeFilterChange={setFieldTypeFilter}
            decisionSourceFilter={decisionSourceFilter}
            onDecisionSourceFilterChange={setDecisionSourceFilter}
            relationTypeFilter={relationTypeFilter}
            onRelationTypeFilterChange={setRelationTypeFilter}
            selectedCount={selectedSuggestions.length}
            loading={loading}
            onConfirm={() => void handleConfirmSuggestions()}
            onReject={() => void handleRejectSuggestions()}
            onRefresh={() => void loadSuggestions()}
          />

          <SuggestionsTable
            loading={loading}
            suggestions={visibleSuggestions}
            selectedRowKeys={selectedRowKeys}
            onSelectedRowKeysChange={setSelectedRowKeys}
            onViewDetail={(suggestion) => {
              setSelectedSuggestion(suggestion)
              setDetailOpen(true)
            }}
            suggestionPage={suggestionPage}
            suggestionPageSize={suggestionPageSize}
            suggestionTotal={suggestionTotal}
            onPageChange={(page, pageSize) => {
              setSuggestionPage(page)
              setSuggestionPageSize(pageSize)
            }}
          />
        </Space>
      </Card>

      <Collapse
        className="workspace-table-card"
        bordered={false}
        defaultActiveKey={['task-assist']}
        items={[
          {
            key: 'task-assist',
            label: '任务辅助信息',
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <PartialSuccessRecoveryCard
                  task={task}
                  loading={replayLoading}
                  onReplay={() => void handleReplaySuggestions()}
                />
                <TaskStagesPanel
                  task={task}
                  retryingStageNum={retryingStageNum}
                  onViewStage={(stageNum) => {
                    setSelectedStageNum(stageNum)
                    setStageDetailOpen(true)
                  }}
                  onRetryStage={(stageNum) => void handleRetryStage(stageNum)}
                />
                <TaskEvidencePanel loading={evidenceLoading} contribution={evidenceContribution} />
              </Space>
            ),
          },
        ]}
      />

      <SuggestionDetailDrawer
        open={detailOpen}
        suggestion={selectedSuggestion}
        onClose={() => setDetailOpen(false)}
      />
      <StageDetailDrawer
        open={stageDetailOpen}
        taskId={parsedTaskId}
        stageNum={selectedStageNum}
        onClose={() => setStageDetailOpen(false)}
      />
      <ConsistencyDrawer
        open={consistencyDrawerOpen}
        task={task}
        onClose={() => setConsistencyDrawerOpen(false)}
      />
      <TaskHistoryDrawer
        open={historyDrawerOpen}
        currentTaskId={parsedTaskId}
        projectId={currentProject.id}
        versionId={currentVersion.id}
        onClose={() => setHistoryDrawerOpen(false)}
      />
    </div>
  )
}

export default FieldMappingTaskDetail
