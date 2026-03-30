import React from 'react'
import { Tabs } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'

import ExecutionCenter from './ExecutionCenter'
import ExecutionReports from './ExecutionReports'

const OperationsCenter: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const activeKey = location.pathname.startsWith('/operations/reports') ? 'reports' : 'executions'

  return (
    <Tabs
      activeKey={activeKey}
      onChange={(key) => navigate(key === 'reports' ? '/operations/reports' : '/operations/executions')}
      items={[
        {
          key: 'executions',
          label: '执行记录',
          children: <ExecutionCenter />,
        },
        {
          key: 'reports',
          label: '执行报表',
          children: <ExecutionReports />,
        },
      ]}
    />
  )
}

export default OperationsCenter
