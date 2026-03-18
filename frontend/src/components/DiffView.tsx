import React, { useEffect, useMemo, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Tag,
  Space,
  Typography,
} from 'antd'
import {
  PlusOutlined,
  MinusOutlined,
  SwapOutlined,
} from '@ant-design/icons'

const { Text } = Typography

interface DiffItem {
  type: 'added' | 'removed' | 'changed'
  field: string
  oldValue?: any
  newValue?: any
}

interface DiffViewProps {
  oldData: any
  newData: any
  title?: string
}

const codeBlockStyle: React.CSSProperties = {
  marginTop: 4,
  padding: 10,
  borderRadius: 8,
  background: 'var(--bg-tertiary)',
  fontSize: 12,
  fontFamily: 'var(--mono)',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  overflowX: 'auto',
}

const formatValue = (value: any): string => {
  if (value === null || value === undefined) {
    return 'null'
  }
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

const DiffView: React.FC<DiffViewProps> = ({ oldData, newData, title = '版本对比' }) => {
  const [diffs, setDiffs] = useState<DiffItem[]>([])

  useEffect(() => {
    const result: DiffItem[] = []

    const compare = (oldValue: any, nextValue: any, path = '') => {
      const keys = new Set([...Object.keys(oldValue || {}), ...Object.keys(nextValue || {})])

      keys.forEach((key) => {
        const currentPath = path ? `${path}.${key}` : key

        if (oldValue && key in oldValue && nextValue && key in nextValue) {
          if (JSON.stringify(oldValue[key]) !== JSON.stringify(nextValue[key])) {
            if (
              typeof oldValue[key] === 'object' &&
              oldValue[key] !== null &&
              typeof nextValue[key] === 'object' &&
              nextValue[key] !== null
            ) {
              compare(oldValue[key], nextValue[key], currentPath)
            } else {
              result.push({
                type: 'changed',
                field: currentPath,
                oldValue: oldValue[key],
                newValue: nextValue[key],
              })
            }
          }
        } else if (oldValue && key in oldValue && (!nextValue || !(key in nextValue))) {
          result.push({
            type: 'removed',
            field: currentPath,
            oldValue: oldValue[key],
          })
        } else if (nextValue && key in nextValue && (!oldValue || !(key in oldValue))) {
          result.push({
            type: 'added',
            field: currentPath,
            newValue: nextValue[key],
          })
        }
      })
    }

    compare(oldData, newData)
    setDiffs(result)
  }, [newData, oldData])

  const stats = useMemo(() => ({
    added: diffs.filter((item) => item.type === 'added').length,
    removed: diffs.filter((item) => item.type === 'removed').length,
    changed: diffs.filter((item) => item.type === 'changed').length,
  }), [diffs])

  const getDiffColor = (type: DiffItem['type']) => {
    if (type === 'added') return 'success'
    if (type === 'removed') return 'error'
    return 'warning'
  }

  const getDiffIcon = (type: DiffItem['type']) => {
    if (type === 'added') return <PlusOutlined />
    if (type === 'removed') return <MinusOutlined />
    return <SwapOutlined />
  }

  return (
    <Card
      title={(
        <Space>
          <Text strong>{title}</Text>
          <Tag color="success">新增: {stats.added}</Tag>
          <Tag color="error">删除: {stats.removed}</Tag>
          <Tag color="warning">修改: {stats.changed}</Tag>
        </Space>
      )}
    >
      {diffs.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-tertiary)' }}>
          没有检测到变更
        </div>
      ) : (
        <div style={{ maxHeight: 600, overflow: 'auto' }}>
          {diffs.map((diff, index) => (
            <Card
              key={`${diff.field}-${index}`}
              size="small"
              style={{
                marginBottom: 8,
                borderLeft: diff.type === 'removed' ? '3px solid #ff4d4f' : undefined,
              }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space>
                  <Tag color={getDiffColor(diff.type)} icon={getDiffIcon(diff.type)}>
                    {diff.type === 'added' ? '新增' : diff.type === 'removed' ? '删除' : '修改'}
                  </Tag>
                  <Text code>{diff.field}</Text>
                </Space>

                <Row gutter={16}>
                  <Col span={12}>
                    {diff.oldValue !== undefined ? (
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>旧值</Text>
                        <pre style={codeBlockStyle}>{formatValue(diff.oldValue)}</pre>
                      </div>
                    ) : null}
                  </Col>
                  <Col span={12}>
                    {diff.newValue !== undefined ? (
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>新值</Text>
                        <pre style={codeBlockStyle}>{formatValue(diff.newValue)}</pre>
                      </div>
                    ) : null}
                  </Col>
                </Row>
              </Space>
            </Card>
          ))}
        </div>
      )}
    </Card>
  )
}

export default DiffView
