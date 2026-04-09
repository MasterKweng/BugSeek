import React from 'react'
import { Button, Card, Drawer, Table } from 'antd'

import type { ScenarioRevision, ScenarioRevisionListItem } from '../../types/scenario'
import ScenarioStatusTag from './ScenarioStatusTag'

interface ScenarioRevisionDrawerProps {
  open: boolean
  revisions: ScenarioRevisionListItem[]
  selectedRevision: ScenarioRevision | null
  onClose: () => void
  onSelectRevision: (revisionId: number) => void
}

const ScenarioRevisionDrawer: React.FC<ScenarioRevisionDrawerProps> = ({
  open,
  revisions,
  selectedRevision,
  onClose,
  onSelectRevision,
}) => (
  <Drawer title="版本快照列表" open={open} onClose={onClose} width={520}>
    <Table<ScenarioRevisionListItem>
      rowKey="id"
      dataSource={revisions}
      pagination={false}
      columns={[
        { title: 'ID', dataIndex: 'id', key: 'id', width: 90 },
        { title: '版本号', dataIndex: 'revision_no', key: 'revision_no', width: 90 },
        {
          title: '状态',
          dataIndex: 'status',
          key: 'status',
          render: (value: string) => <ScenarioStatusTag status={value} />,
        },
        {
          title: '发布时间',
          dataIndex: 'published_at',
          key: 'published_at',
          render: (value?: string | null) => value || '-',
        },
        {
          title: '操作',
          key: 'actions',
          render: (_, record) => <Button type="link" onClick={() => onSelectRevision(record.id)}>加载</Button>,
        },
      ]}
    />
    {selectedRevision ? (
      <Card size="small" title={`当前版本快照 #${selectedRevision.revision_no}`} style={{ marginTop: 16 }}>
        <pre className="scenario-json-preview">{JSON.stringify(selectedRevision.snapshot, null, 2)}</pre>
      </Card>
    ) : null}
  </Drawer>
)

export default ScenarioRevisionDrawer
