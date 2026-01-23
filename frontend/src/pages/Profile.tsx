import { useState } from 'react'
import { Form, Input, Button, Card, Avatar, Upload, message, Modal } from 'antd'
import { UserOutlined, LockOutlined, UploadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import api from '../services/api'
import type { UploadChangeParam } from 'antd/es/upload'

const Profile: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout, updateUser } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [passwordModalVisible, setPasswordModalVisible] = useState(false)
  const [form] = Form.useForm()

  const handleUpdateProfile = async (values: any) => {
    setLoading(true)
    try {
      const result = await api.put('/auth/profile', values)
      if (result.code === 0) {
        updateUser(result.data)
        message.success('更新成功')
      }
    } catch (error: any) {
      message.error(error.message || '更新失败')
    } finally {
      setLoading(false)
    }
  }

  const handleChangePassword = async (values: any) => {
    setLoading(true)
    try {
      const result = await api.put('/auth/password', values)
      if (result.code === 0) {
        message.success('密码修改成功')
        setPasswordModalVisible(false)
        form.resetFields()
      }
    } catch (error: any) {
      message.error(error.message || '密码修改失败')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleAvatarChange = (info: UploadChangeParam) => {
    if (info.file.status === 'done') {
      const avatarUrl = info.file.response?.data?.url
      if (avatarUrl) {
        updateUser({ avatar: avatarUrl })
        message.success('头像上传成功')
      }
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      <Card title="个人信息">
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '24px' }}>
          <Avatar size={80} src={user?.avatar} icon={<UserOutlined />} />
          <Upload
            name="avatar"
            showUploadList={false}
            action="/api/v1/upload/avatar"
            onChange={handleAvatarChange}
            style={{ marginLeft: '16px' }}
          >
            <Button icon={<UploadOutlined />}>更换头像</Button>
          </Upload>
        </div>

        <Form
          form={form}
          layout="vertical"
          initialValues={user || {}}
          onFinish={handleUpdateProfile}
        >
          <Form.Item label="用户名" name="username">
            <Input disabled />
          </Form.Item>

          <Form.Item label="邮箱" name="email">
            <Input disabled />
          </Form.Item>

          <Form.Item label="昵称" name="nickname">
            <Input placeholder="请输入昵称" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              保存
            </Button>
            <Button
              style={{ marginLeft: '8px' }}
              onClick={() => setPasswordModalVisible(true)}
            >
              修改密码
            </Button>
            <Button
              danger
              style={{ marginLeft: '8px' }}
              onClick={handleLogout}
            >
              登出
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Modal
        title="修改密码"
        open={passwordModalVisible}
        onCancel={() => setPasswordModalVisible(false)}
        footer={null}
      >
        <Form onFinish={handleChangePassword}>
          <Form.Item
            name="old_password"
            rules={[{ required: true, message: '请输入旧密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="旧密码" />
          </Form.Item>

          <Form.Item
            name="new_password"
            rules={[{ required: true, message: '请输入新密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="新密码" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              确认修改
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default Profile