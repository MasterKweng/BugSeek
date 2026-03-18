import { useState } from 'react'
import { Form, Input, Button, Card, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { useAppPreferences } from '../preferences/AppPreferencesProvider'
import AuthPreferenceBar from '../components/AuthPreferenceBar'

const Login: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuthStore()
  const { t } = useAppPreferences()
  const [loading, setLoading] = useState(false)

  const from = (location.state as { from?: { pathname?: string } } | undefined)?.from?.pathname || '/'

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success(t('auth.loginSuccess'))

      const token = localStorage.getItem('token')
      if (!token) {
        const authData = localStorage.getItem('auth-storage')

        if (authData) {
          try {
            const parsed = JSON.parse(authData) as { state?: { token?: string } }

            if (parsed.state?.token) {
              localStorage.setItem('token', parsed.state.token)
            }
          } catch (error) {
            console.error('Failed to parse auth storage:', error)
          }
        }
      }

      navigate(from, { replace: true })
    } catch (error) {
      const messageText = error instanceof Error ? error.message : t('auth.login')
      message.error(messageText)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <AuthPreferenceBar />
      <Card title="BugSeek" className="auth-card">
        <div className="auth-card__subtitle">{t('auth.loginTitle')}</div>
        <Form name="login" onFinish={onFinish} autoComplete="off" layout="vertical">
          <Form.Item
            name="username"
            rules={[{ required: true, message: t('auth.requiredUsername') }]}
          >
            <Input prefix={<UserOutlined />} placeholder={t('auth.username')} />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: t('auth.requiredPassword') }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder={t('auth.password')} />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              {t('auth.login')}
            </Button>
          </Form.Item>

          <div className="auth-card__footer">
            {t('auth.noAccount')} <Link to="/register">{t('auth.goRegister')}</Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}

export default Login
