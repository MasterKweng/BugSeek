import React, { useEffect, useMemo, useState } from 'react'
import { Button, Card, Result, Space, message } from 'antd'
import { Link } from 'react-router-dom'
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'
import DictionaryTable from '../../components/field-mapping/DictionaryTable'
import { useProjectStore } from '../../store/project'
import { getFieldDictionary, type ProjectFieldDictionary } from '../../services/fieldMappingGovernance'

const FieldMappingDictionary: React.FC = () => {
  const { currentProject, currentVersion } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<ProjectFieldDictionary[]>([])

  const contextParams = useMemo(() => ({
    project_id: currentProject?.id,
    version_id: currentVersion?.id,
  }), [currentProject?.id, currentVersion?.id])

  const metrics = useMemo(() => [
    { label: '词条数', value: items.length },
    { label: '项目', value: currentProject?.name || '-' },
    { label: '版本', value: currentVersion?.version_number || '-' },
  ], [currentProject?.name, currentVersion?.version_number, items.length])

  useEffect(() => {
    const load = async () => {
      if (!currentProject?.id || !currentVersion?.id) {
        setItems([])
        return
      }

      setLoading(true)
      try {
        const response = await getFieldDictionary(contextParams)
        setItems(response.data?.items || [])
      } catch (error: any) {
        message.error(error.message || '获取字段字典失败')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [currentProject?.id, currentVersion?.id])

  if (!currentProject || !currentVersion) {
    return (
      <Result
        status="warning"
        title="请先选择项目和版本"
        subTitle="字段字典页依赖项目和版本上下文。"
      />
    )
  }

  return (
    <div className="workspace-page">
      <WorkspaceModuleHero
        eyebrow="Dictionary"
        title="字段字典"
        description={`查看 ${currentProject.name} / ${currentVersion.version_number} 下沉淀的字段词典资产。`}
        metrics={metrics}
        actions={(
          <Space wrap>
            <Button>
              <Link to="/version-center/field-mapping">返回总览</Link>
            </Button>
            <Button>
              <Link to="/version-center/field-mapping/mappings">进入治理页</Link>
            </Button>
          </Space>
        )}
      />

      <Card className="workspace-table-card" bordered={false}>
        <DictionaryTable loading={loading} items={items} />
      </Card>
    </div>
  )
}

export default FieldMappingDictionary
