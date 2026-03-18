import { useState } from 'react'
import { Form, Input, Button, Card, message } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { useAppPreferences } from '../preferences/AppPreferencesProvider'
import AuthPreferenceBar from '../components/AuthPreferenceBar'

interface RegisterFormValues {
  username: string
  email: string
  password: string
  confirmPassword: string
  nickname?: string
}

const Register: React.FC = () => {
  const navigate = useNavigate()
  const { register } = useAuthStore()
  const { t } = useAppPreferences()
  const [loading, setLoading] = useState(false)

  const onFinish = async (values: RegisterFormValues) => {
    setLoading(true)
    try {
      await register({
        username: values.username,
        email: values.email,
        password: values.password,
        nickname: values.nickname,
      })
      message.success(t('auth.registerSuccess'))
      navigate('/login')
    } catch (error) {
      const messageText = error instanceof Error ? error.message : t('auth.register')
      message.error(messageText)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <AuthPreferenceBar />
      <Card title="BugSeek" className="auth-card">
        <div className="auth-card__subtitle">{t('auth.registerTitle')}</div>
        <Form name="register" onFinish={onFinish} autoComplete="off" layout="vertical">
          <Form.Item
            name="username"
            rules={[
              { required: true, message: t('auth.requiredUsername') },
              { min: 3, max: 50, message: t('auth.usernameLength') },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder={t('auth.username')} />
          </Form.Item>

          <Form.Item
            name="email"
            rules={[
              { required: true, message: t('auth.requiredEmail') },
              { type: 'email', message: t('auth.invalidEmail') },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder={t('auth.email')} />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: t('auth.requiredPassword') },
              { min: 6, max: 20, message: t('auth.passwordLength') },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder={t('auth.password')} />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: t('auth.requiredConfirmPassword') },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve()
                  }

                  return Promise.reject(new Error(t('auth.passwordMismatch')))
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder={t('auth.confirmPassword')} />
          </Form.Item>

          <Form.Item name="nickname">
            <Input placeholder={t('auth.nickname')} />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              {t('auth.register')}
            </Button>
          </Form.Item>

          <div className="auth-card__footer">
            {t('auth.hasAccount')} <Link to="/login">{t('auth.goLogin')}</Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}

export default Register
