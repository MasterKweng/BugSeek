import React, { useEffect } from 'react'
import { Dropdown, Button, Space, message, Spin, Tag } from 'antd'
import { BranchesOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '../store/project'
import type { Version } from '../types'
import type { MenuProps } from 'antd'

const VersionSelector: React.FC = () => {
  const navigate = useNavigate()
  const {
    currentProject,
    currentVersion,
    versions,
    loading,
    setCurrentVersion
  } = useProjectStore()

  useEffect(() => {
    if (currentProject) {
      // 版本列表会在 setCurrentProject 时自动获取
    }
  }, [currentProject])

  const handleSelectVersion = async (version: Version) => {
    const token = localStorage.getItem('token')
    if (!token) {
      message.error('未登录')
      return
    }

    if (!currentProject) {
      message.warning('请先选择一个项目')
      return
    }

    try {
      // 调用后端上下文切换API，配置 10s 超时
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10000)
      
      const response = await fetch('/api/v1/context/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          project_id: currentProject.id,
          version_id: version.id,
        }),
        signal: controller.signal,
      })
      
      clearTimeout(timeoutId)

      const result = await response.json()
      if (result.code === 0) {
        // 更新前端 store
        setCurrentVersion(version)
        message.success(`已切换到版本：${version.version_number}`)
        
        // 刷新页面以更新所有数据
        window.location.reload()
      } else {
        message.error(result.message || '切换版本失败')
      }
    } catch (error: any) {
      console.error('切换版本失败:', error)
      if (error.name === 'AbortError') {
        message.error('请求超时，请稍后重试')
      } else {
        message.error('切换版本失败，请稍后重试')
      }
    }
  }

  const handleCreateVersion = () => {
    if (!currentProject) {
      message.warning('请先选择一个项目')
      return
    }
    navigate(`/projects/${currentProject.id}/versions`)
  }

  const getStatusColor = (status: string) => {
    const colorMap: Record<string, string> = {
      planning: 'default',
      developing: 'processing',
      testing: 'warning',
      released: 'success',
      locked: 'error'
    }
    return colorMap[status] || 'default'
  }

  const getStatusText = (status: string) => {
    const textMap: Record<string, string> = {
      planning: '规划中',
      developing: '开发中',
      testing: '测试中',
      released: '已发布',
      locked: '已锁定'
    }
    return textMap[status] || status
  }

  const menuItems: MenuProps['items'] = currentProject
    ? [
        ...versions.map(version => ({
          key: version.id,
          label: (
            <Space>
              {currentVersion?.id === version.id && <span style={{ color: '#1890ff' }}>[当前]</span>}
              <span>{version.version_number}</span>
              <Tag color={getStatusColor(version.status)} style={{ marginLeft: 4 }}>
                {getStatusText(version.status)}
              </Tag>
            </Space>
          ),
          onClick: () => handleSelectVersion(version)
        })),
        {
          type: 'divider'
        },
        {
          key: 'create',
          label: (
            <Space>
              <PlusOutlined />
              <span>新建版本</span>
            </Space>
          ),
          onClick: handleCreateVersion
        }
      ]
    : []

  if (!currentProject) {
    return (
      <Button type="text" disabled>
        <Space size="small">
          <BranchesOutlined />
          <span style={{ fontWeight: 500, color: 'var(--text-tertiary)' }}>
            请先选择项目
          </span>
        </Space>
      </Button>
    )
  }

  return (
    <Dropdown menu={{ items: menuItems }} trigger={['click']}>
      <Button type="text">
        <Space size="small">
          <BranchesOutlined />
          <span style={{ fontWeight: 500 }}>
            {currentVersion?.version_number || '选择版本'}
          </span>
          {currentVersion && (
            <Tag color={getStatusColor(currentVersion.status)} style={{ marginLeft: 4 }}>
              {getStatusText(currentVersion.status)}
            </Tag>
          )}
          {loading && <Spin size="small" />}
        </Space>
      </Button>
    </Dropdown>
  )
}

export default VersionSelector