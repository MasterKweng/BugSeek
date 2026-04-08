import React, { useMemo, useState } from 'react'
import { Input, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { ProjectFieldDictionary } from '../../services/fieldMappingGovernance'

interface DictionaryTableProps {
  loading?: boolean
  items: ProjectFieldDictionary[]
}

const DictionaryTable: React.FC<DictionaryTableProps> = ({ loading = false, items }) => {
  const [searchKeyword, setSearchKeyword] = useState('')

  const filteredItems = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase()
    if (!keyword) {
      return items
    }
    return items.filter((item) => (
      item.field_name.toLowerCase().includes(keyword)
      || item.db_table.toLowerCase().includes(keyword)
      || item.db_column.toLowerCase().includes(keyword)
    ))
  }, [items, searchKeyword])

  const columns: ColumnsType<ProjectFieldDictionary> = [
    { title: '字段名', dataIndex: 'field_name', key: 'field_name', width: 220 },
    { title: '表', dataIndex: 'db_table', key: 'db_table', width: 220 },
    { title: '列', dataIndex: 'db_column', key: 'db_column', width: 220 },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 120 },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Input.Search
        allowClear
        placeholder="搜索字段名、表名或列名"
        value={searchKeyword}
        onChange={(event) => setSearchKeyword(event.target.value)}
      />
      <Table
        rowKey={(record) => `${record.field_name}-${record.db_table}-${record.db_column}`}
        loading={loading}
        columns={columns}
        dataSource={filteredItems}
        pagination={{ pageSize: 20, hideOnSinglePage: true }}
      />
    </Space>
  )
}

export default DictionaryTable
