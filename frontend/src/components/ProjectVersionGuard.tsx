import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '../store/project'
import { Modal, Button } from 'antd'
import { ProjectOutlined } from '@ant-design/icons'

interface ProjectVersionGuardProps {
  children: React.ReactNode
}

const ProjectVersionGuard: React.FC<ProjectVersionGuardProps> = ({ children }) => {
  const navigate = useNavigate()
  const { currentProject } = useProjectStore()
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    // 如果未选择项目，显示友好提示
    if (!currentProject) {
      setShowModal(true)
    }
  }, [currentProject])

  const handleGoToProjects = () => {
    setShowModal(false)
    navigate('/projects')
  }

  const handleCancel = () => {
    setShowModal(false)
    // 返回上一页或首页
    navigate('/')
  }

  // 如果未选择项目，显示友好提示
  if (!currentProject) {
    return (
      <Modal
        title="提示"
        open={showModal}
        onCancel={handleCancel}
        footer={[
          <Button key="cancel" onClick={handleCancel}>
            返回首页
          </Button>,
          <Button key="confirm" type="primary" icon={<ProjectOutlined />} onClick={handleGoToProjects}>
            前往项目管理
          </Button>
        ]}
        centered
      >
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <ProjectOutlined style={{ fontSize: '48px', color: '#1890ff', marginBottom: '16px' }} />
          <p style={{ fontSize: '16px', marginBottom: '8px' }}>请先选择一个项目</p>
          <p style={{ color: 'var(--text-tertiary)' }}>您需要先创建或选择一个项目，才能使用此功能</p>
        </div>
      </Modal>
    )
  }

  // 如果未选择版本，可以选择显示提示或允许访问
  // 这里我们允许访问，某些页面可能不需要版本

  return <>{children}</>
}

export default ProjectVersionGuard
