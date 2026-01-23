import React, { useEffect, useState } from 'react'
import { Dropdown, Button, Space, message, Spin } from 'antd'
import { ProjectOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '../store/project'
import type { Project } from '../types'
import type { MenuProps } from 'antd'

const ProjectSelector: React.FC = () => {
  const navigate = useNavigate()
  const {
    currentProject,
    projects,
    loading,
    fetchProjects,
    setCurrentProject,
    setCurrentVersion
  } = useProjectStore()
  const [createModalVisible, setCreateModalVisible] = useState(false)

  useEffect(() => {
    fetchProjects()
  }, [])

  const handleSelectProject = async (project: Project) => {
    const token = localStorage.getItem('token')
    if (!token) {
      message.error('未登录')
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
          project_id: project.id,
          version_id: null, // 切换项目时清空版本
        }),
        signal: controller.signal,
      })
      
      clearTimeout(timeoutId)

      const result = await response.json()
      if (result.code === 0) {
        // 更新前端 store
        setCurrentProject(project)
        setCurrentVersion(null) // 清空当前版本
        message.success(`已切换到项目：${project.name}`)
        
        // 刷新页面以更新所有数据
        window.location.reload()
      } else {
        message.error(result.message || '切换项目失败')
      }
    } catch (error: any) {
      console.error('切换项目失败:', error)
      if (error.name === 'AbortError') {
        message.error('请求超时，请稍后重试')
      } else {
        message.error('切换项目失败，请稍后重试')
      }
    }
  }

  const handleCreateProject = () => {
    navigate('/projects')
  }

  const menuItems: MenuProps['items'] = projects.length > 0
    ? [
        ...projects.map(project => ({
          key: project.id,
          label: (
            <Space>
              {currentProject?.id === project.id && <span style={{ color: '#1890ff' }}>[当前]</span>}
              <span>{project.name}</span>
            </Space>
          ),
          onClick: () => handleSelectProject(project)
        })),
        {
          type: 'divider'
        },
        {
          key: 'create',
          label: (
            <Space>
              <PlusOutlined />
              <span>新建项目</span>
            </Space>
          ),
          onClick: handleCreateProject
        }
      ]
    : [
        {
          key: 'empty',
          label: (
            <div style={{ padding: '8px 0', color: '#999', textAlign: 'center' }}>
              暂无项目
            </div>
          ),
          disabled: true
        },
        {
          type: 'divider'
        },
        {
          key: 'create',
          label: (
            <Space>
              <PlusOutlined />
              <span>新建项目</span>
            </Space>
          ),
          onClick: handleCreateProject
        }
      ]

  return (
    <Dropdown menu={{ items: menuItems }} trigger={['click']}>
      <Button type="text">
        <Space size="small">
          <ProjectOutlined />
          <span style={{ fontWeight: 500 }}>
            {currentProject?.name || (projects.length === 0 ? '暂无项目' : '选择项目')}
          </span>
          {loading && <Spin size="small" />}
        </Space>
      </Button>
    </Dropdown>
  )
}

export default ProjectSelector