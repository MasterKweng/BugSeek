/**
 * 环境差异化配置编辑器组件
 * 符合前端代码规范
 */

import React, { useState } from 'react'
import {
  Badge,
  Button,
  Card,
  List,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  createEnvironmentAuthConfig,
  deleteEnvironmentAuthConfig,
  updateEnvironmentAuthConfig,
} from '../services/auth'
import AuthConfigForm from './AuthConfigForm'
import type { AuthConfig, AuthConfigCreate, ProjectAuthTemplate } from '../types/auth'

const { Option } = Select
const { Text } = Typography

interface Environment {
  id: number
  name: string
  base_url: string
}

interface EnvironmentConfigEditorProps {
  projectId: number
  environments: Environment[]
  selectedEnvironment: number | null
  onSelectEnvironment: (envId: number) => void
  config: AuthConfig | null
  projectTemplate: ProjectAuthTemplate | null
}

const EnvironmentConfigEditor: React.FC<EnvironmentConfigEditorProps> = ({
  projectId,
  environments,
  selectedEnvironment,
  onSelectEnvironment,
  config,
  projectTemplate,
}) => {
  const [editing, setEditing] = useState(false)
  const [copiedConfig, setCopiedConfig] = useState<AuthConfig | null>(null)
  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: (params: { environmentId: number; data: AuthConfigCreate; inherit: boolean }) =>
      createEnvironmentAuthConfig(projectId, params.environmentId, params.data, params.inherit),
    onSuccess: () => {
      message.success('环境配置创建成功')
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['authConfig', projectId, selectedEnvironment] })
    },
    onError: (error: any) => {
      message.error(`创建失败: ${error.message || '未知错误'}`)
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: AuthConfigCreate) =>
      updateEnvironmentAuthConfig(projectId, selectedEnvironment!, data),
    onSuccess: () => {
      message.success('环境配置更新成功')
      queryClient.invalidateQueries({ queryKey: ['authConfig', projectId, selectedEnvironment] })
    },
    onError: (error: any) => {
      message.error(`更新失败: ${error.message || '未知错误'}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteEnvironmentAuthConfig(projectId, selectedEnvironment!),
    onSuccess: () => {
      message.success('环境配置已删除，将使用项目模板')
      queryClient.invalidateQueries({ queryKey: ['authConfig', projectId, selectedEnvironment] })
    },
    onError: (error: any) => {
      message.error(`删除失败: ${error.message || '未知错误'}`)
    },
  })

  const handleSave = (data: AuthConfigCreate) => {
    const isInheritedFromTemplate = config?._meta?.inherited_from === 'project_template'

    if (config && !isInheritedFromTemplate) {
      updateMutation.mutate(data)
      return
    }

    createMutation.mutate({
      environmentId: selectedEnvironment!,
      data,
      inherit: false,
    })
  }

  const handleCopyConfig = () => {
    if (!config) return
    setCopiedConfig(config)
    message.success('配置已复制，请选择目标环境')
  }

  const handlePasteConfig = (targetEnvId: number) => {
    if (!copiedConfig) return

    const data: AuthConfigCreate = {
      enabled: copiedConfig.enabled,
      auth_type: copiedConfig.auth_type,
      injection: copiedConfig.injection,
      source_mode: copiedConfig.source_mode,
      static_value: copiedConfig.static_value,
      login_api_id: copiedConfig.login_api_id,
      login_auth_type: copiedConfig.login_auth_type,
      input_mappings: copiedConfig.input_mappings,
      extract_rules: copiedConfig.extract_rules,
    }

    createMutation.mutate({
      environmentId: targetEnvId,
      data,
      inherit: false,
    })
  }

  const selectedEnv = environments.find((item) => item.id === selectedEnvironment)

  return (
    <div className="environment-config" style={{ display: 'flex', gap: 24 }}>
      <Card title="选择环境" style={{ width: 300, flexShrink: 0 }}>
        <List
          dataSource={environments}
          renderItem={(env) => {
            const envConfig = env.id === selectedEnvironment ? config : null
            const isInherited = envConfig?._meta?.inherited_from === 'project_template'

            return (
              <List.Item
                style={{
                  cursor: 'pointer',
                  padding: 12,
                  borderRadius: 8,
                  backgroundColor: selectedEnvironment === env.id ? '#f0f5ff' : 'transparent',
                  border: selectedEnvironment === env.id ? '2px solid #1890ff' : '1px solid #f0f0f0',
                }}
                onClick={() => onSelectEnvironment(env.id)}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space>
                    <Badge status={env.name === 'Prod' ? 'error' : 'success'} text={env.name} />
                    {envConfig &&
                      (isInherited ? <Tag color="blue">继承模板</Tag> : <Tag color="green">自定义</Tag>)}
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {env.base_url}
                  </Text>
                </Space>
              </List.Item>
            )
          }}
        />
      </Card>

      {selectedEnvironment && selectedEnv && (
        <Card
          title={`${selectedEnv.name} 环境配置`}
          style={{ flex: 1 }}
          extra={
            config && config._meta?.inherited_from !== 'project_template' ? (
              <Space>
                <Button icon={<CopyOutlined />} onClick={handleCopyConfig}>
                  复制配置
                </Button>
                {copiedConfig && (
                  <Select
                    placeholder="选择目标环境"
                    style={{ width: 200 }}
                    onChange={(targetEnvId) => handlePasteConfig(targetEnvId)}
                  >
                    {environments
                      .filter((item) => item.id !== selectedEnvironment)
                      .map((item) => (
                        <Option key={item.id} value={item.id}>
                          {item.name}
                        </Option>
                      ))}
                  </Select>
                )}
              </Space>
            ) : null
          }
        >
          {!config || config._meta?.inherited_from === 'project_template' ? (
            <div style={{ padding: '40px 0', textAlign: 'center' }}>
              <Space direction="vertical" size="large">
                <Text style={{ fontSize: 16, color: 'var(--text-primary)' }}>当前默认使用项目鉴权配置</Text>
                <Button type="primary" size="large" onClick={() => setEditing(true)}>
                  自定义
                </Button>
              </Space>

              {editing && (
                <div style={{ marginTop: 24, textAlign: 'left' }}>
                  <AuthConfigForm
                    mode="environment"
                    initialValues={projectTemplate}
                    projectTemplate={projectTemplate}
                    onSave={handleSave}
                    loading={createMutation.isPending}
                  />
                </div>
              )}
            </div>
          ) : (
            <>
              <AuthConfigForm
                mode="environment"
                initialValues={config}
                projectTemplate={projectTemplate}
                onSave={handleSave}
                loading={createMutation.isPending || updateMutation.isPending}
              />

              <div style={{ marginTop: 24, textAlign: 'center' }}>
                <Button
                  danger
                  onClick={() => {
                    Modal.confirm({
                      title: '删除自定义配置',
                      content: '删除后将使用项目设置，是否确定删除？',
                      onOk: () => deleteMutation.mutate(),
                    })
                  }}
                  loading={deleteMutation.isPending}
                >
                  删除自定义配置
                </Button>
              </div>
            </>
          )}
        </Card>
      )}
    </div>
  )
}

export default EnvironmentConfigEditor
