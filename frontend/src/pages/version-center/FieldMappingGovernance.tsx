import React from 'react'
import { Button, Card, Result, Space, Tabs } from 'antd'
import { Link } from 'react-router-dom'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import MappingStatsCard from '../../components/field-mapping/MappingStatsCard'
import MappingsTable from '../../components/field-mapping/MappingsTable'
import PendingMappingsTable from '../../components/field-mapping/PendingMappingsTable'
import CloneMappingsModal from '../../components/field-mapping/CloneMappingsModal'
import useFieldMappingGovernance from '../../hooks/field-mapping/useFieldMappingGovernance'

const FieldMappingGovernance: React.FC = () => {
  const {
    currentProject,
    currentVersion,
    versions,
    loading,
    mappingsLoading,
    pendingLoading,
    cloneModalOpen,
    mappingFilter,
    mappings,
    pendingMappings,
    stats,
    metrics,
    setCloneModalOpen,
    setMappingFilter,
    handleAutoApply,
    handleDeleteMapping,
    handlePendingStatusChange,
    handleCloneMappings,
  } = useFieldMappingGovernance()

  if (!currentProject || !currentVersion) {
    return (
      <Result
        status="warning"
        title="请先选择项目和版本"
        subTitle="字段映射治理页依赖项目和版本上下文。"
      />
    )
  }

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow="Governance"
        title="字段映射治理"
        description={`管理 ${currentProject.name} / ${currentVersion.version_number} 的映射资产，包括已生效映射、待处理映射与跨版本复用。`}
        metrics={metrics}
        actions={(
          <Space wrap>
            <Button>
              <Link to="/version-center/field-mapping">返回总览</Link>
            </Button>
            <Button>
              <Link to="/version-center/field-mapping/dictionary">字段字典</Link>
            </Button>
          </Space>
        )}
      />

      <MappingStatsCard
        stats={stats}
        fallbackTotal={mappings.length}
        loading={loading}
        onAutoApply={() => void handleAutoApply()}
        onOpenClone={() => setCloneModalOpen(true)}
      />

      <Card className="workspace-table-card" bordered={false}>
        <Tabs
          items={[
            {
              key: 'active',
              label: '已生效映射',
              children: (
                <MappingsTable
                  loading={mappingsLoading}
                  mappings={mappings}
                  mappingFilter={mappingFilter}
                  onMappingFilterChange={setMappingFilter}
                  onDelete={(mappingId) => void handleDeleteMapping(mappingId)}
                />
              ),
            },
            {
              key: 'pending',
              label: '待处理映射',
              children: (
                <PendingMappingsTable
                  loading={pendingLoading}
                  items={pendingMappings}
                  onStatusChange={(mappingId, status) => void handlePendingStatusChange(mappingId, status)}
                />
              ),
            },
          ]}
        />
      </Card>

      <CloneMappingsModal
        open={cloneModalOpen}
        versions={versions}
        currentVersionId={currentVersion.id}
        loading={loading}
        onClose={() => setCloneModalOpen(false)}
        onSubmit={handleCloneMappings}
      />
    </div>
  )
}

export default FieldMappingGovernance
