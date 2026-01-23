import { useState } from 'react'
import { Form, Input, Button, Card, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/auth'

const Login: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuthStore()
  const [loading, setLoading] = useState(false)

  const from = (location.state as any)?.from?.pathname || '/'

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      // 登录成功后，确保 token 也保存到 localStorage
      const token = localStorage.getItem('token')
      if (!token) {
        // 如果 Zustand persist 还没有保存到 localStorage，手动获取并保存
        const authData = localStorage.getItem('auth-storage')
        if (authData) {
          try {
            const parsed = JSON.parse(authData)
            if (parsed.state?.token) {
              localStorage.setItem('token', parsed.state.token)
            }
          } catch (e) {
            console.error('Failed to parse auth storage:', e)
          }
        }
      }
      navigate(from, { replace: true })
    } catch (error: any) {
      message.error(error.message || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f0f2f5' }}>
      <Card title="BugSeek" style={{ width: 400 }}>
        <Form name="login" onFinish={onFinish} autoComplete="off">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center' }}>
            还没有账号？ <a href="/register">立即注册</a>
          </div>
        </Form>
      </Card>
    </div>
  )
}

export default Login