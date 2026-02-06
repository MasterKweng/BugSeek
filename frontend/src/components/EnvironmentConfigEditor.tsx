/**
 * 环境差异化配置编辑器组件
 * 符合前端代码规范
 */

import React, { useState } from 'react';
import { 
  Card, 
  List, 
  Badge, 
  Tag, 
  Radio, 
  Alert, 
  Space, 
  Button, 
  Select, 
  message, 
  Typography,
  Modal
} from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  createEnvironmentAuthConfig, 
  updateEnvironmentAuthConfig,
  deleteEnvironmentAuthConfig
} from '../services/auth';
import AuthConfigForm from './AuthConfigForm';
import type { AuthConfig, ProjectAuthTemplate, AuthConfigCreate } from '../types/auth';

const { Text } = Typography;
const { Option } = Select;

interface Environment {
  id: number;
  name: string;
  base_url: string;
}

interface EnvironmentConfigEditorProps {
  projectId: number;
  environments: Environment[];
  selectedEnvironment: number | null;
  onSelectEnvironment: (envId: number) => void;
  config: AuthConfig | null;
  projectTemplate: ProjectAuthTemplate | null;
}

/**
 * 环境差异化配置编辑器
 * 用于管理不同环境的鉴权配置
 */
const EnvironmentConfigEditor: React.FC<EnvironmentConfigEditorProps> = ({
  projectId,
  environments,
  selectedEnvironment,
  onSelectEnvironment,
  config,
  projectTemplate
}) => {
  const [editing, setEditing] = useState(false);
  const [copiedConfig, setCopiedConfig] = useState<AuthConfig | null>(null);
  const queryClient = useQueryClient();
  
  /**
   * 创建环境配置
   */
  const createMutation = useMutation({
    mutationFn: (params: { environmentId: number; data: AuthConfigCreate; inherit: boolean }) =>
      createEnvironmentAuthConfig(
        projectId,
        params.environmentId,
        params.data,
        params.inherit
      ),
    onSuccess: () => {
      message.success('环境配置创建成功');
      setEditing(false);  // 重置编辑状态
      queryClient.invalidateQueries({ queryKey: ['authConfig', projectId, selectedEnvironment] });
    },
    onError: (error: any) => {
      message.error(`创建失败: ${error.message || '未知错误'}`);
    }
  });
  
  /**
   * 更新环境配置
   */
  const updateMutation = useMutation({
    mutationFn: (data: AuthConfigCreate) =>
      updateEnvironmentAuthConfig(projectId, selectedEnvironment!, data),
    onSuccess: () => {
      message.success('环境配置更新成功');
      queryClient.invalidateQueries({ queryKey: ['authConfig', projectId, selectedEnvironment] });
    },
    onError: (error: any) => {
      message.error(`更新失败: ${error.message || '未知错误'}`);
    }
  });
  
  /**
   * 删除环境配置
   */
  const deleteMutation = useMutation({
    mutationFn: () => deleteEnvironmentAuthConfig(projectId, selectedEnvironment!),
    onSuccess: () => {
      message.success('环境配置已删除，将使用项目模板');
      queryClient.invalidateQueries({ queryKey: ['authConfig', projectId, selectedEnvironment] });
    },
    onError: (error: any) => {
      message.error(`删除失败: ${error.message || '未知错误'}`);
    }
  });
  
  /**
   * 处理保存
   */
  const handleSave = (data: AuthConfigCreate) => {
    // 检查是否是项目模板（通过 _meta 字段判断）
    const isInheritedFromTemplate = config?._meta?.inherited_from === 'project_template';

    if (config && !isInheritedFromTemplate) {
      // 有真实的环境配置，调用更新接口
      updateMutation.mutate(data);
    } else {
      // 没有配置或只是项目模板，调用创建接口
      createMutation.mutate({
        environmentId: selectedEnvironment!,
        data,
        inherit: false  // 自定义配置，不继承
      });
    }
  };
  
  /**
   * 处理复制配置
   */
  const handleCopyConfig = () => {
    if (!config) return;
    setCopiedConfig(config);
    message.success('配置已复制，请选择目标环境');
  };
  
  /**
   * 处理粘贴配置
   */
  const handlePasteConfig = (targetEnvId: number) => {
    if (!copiedConfig) return;
    
    const data: AuthConfigCreate = {
      enabled: copiedConfig.enabled,
      auth_type: copiedConfig.auth_type,
      injection: copiedConfig.injection,
      source_mode: copiedConfig.source_mode,
      static_value: copiedConfig.static_value,
      login_api_id: copiedConfig.login_api_id,
      login_auth_type: copiedConfig.login_auth_type,
      input_mappings: copiedConfig.input_mappings,
      extract_rules: copiedConfig.extract_rules
    };
    
    createMutation.mutate({
      environmentId: targetEnvId,
      data,
      inherit: false
    });
  };
  
  const selectedEnv = environments.find(e => e.id === selectedEnvironment);
  
  return (
    <div className="environment-config" style={{ display: 'flex', gap: '24px' }}>
      {/* 左侧：环境列表 */}
      <Card 
        title="选择环境" 
        style={{ width: '300px', flexShrink: 0 }}
      >
        <List
          dataSource={environments}
          renderItem={(env) => {
            const envConfig = env.id === selectedEnvironment ? config : null;
            const isInherited = envConfig?._meta?.inherited_from === 'project_template';
            
            return (
              <List.Item
                style={{
                  cursor: 'pointer',
                  padding: '12px',
                  borderRadius: '8px',
                  backgroundColor: selectedEnvironment === env.id ? '#f0f5ff' : 'transparent',
                  border: selectedEnvironment === env.id ? '2px solid #1890ff' : '1px solid #f0f0f0'
                }}
                onClick={() => onSelectEnvironment(env.id)}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space>
                    <Badge 
                      status={env.name === 'Prod' ? 'error' : 'success'} 
                      text={env.name}
                    />
                    {envConfig && (
                      isInherited ? (
                        <Tag color="blue">继承模板</Tag>
                      ) : (
                        <Tag color="green">自定义</Tag>
                      )
                    )}
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {env.base_url}
                  </Text>
                </Space>
              </List.Item>
            );
          }}
        />
      </Card>
      
      {/* 右侧：配置编辑器 */}
      {selectedEnvironment && selectedEnv && (
        <Card 
          title={`${selectedEnv.name} 环境配置`}
          style={{ flex: 1 }}
          extra={
            config && config._meta?.inherited_from !== 'project_template' && (
              <Space>
                <Button 
                  icon={<CopyOutlined />}
                  onClick={handleCopyConfig}
                >
                  复制配置
                </Button>
                {copiedConfig && (
                  <Select
                    placeholder="选择目标环境"
                    style={{ width: 200 }}
                    onChange={(targetEnvId) => handlePasteConfig(targetEnvId)}
                  >
                    {environments
                      .filter(e => e.id !== selectedEnvironment)
                      .map(env => (
                        <Option key={env.id} value={env.id}>{env.name}</Option>
                      ))}
                  </Select>
                )}
              </Space>
            )
          }
        >
          {!config || config._meta?.inherited_from === 'project_template' ? (
            // 没有配置或使用项目模板时，显示提示和自定义按钮
            <div style={{ padding: '40px 0', textAlign: 'center' }}>
              <Space direction="vertical" size="large">
                <div>
                  <Text style={{ fontSize: 16, color: '#333' }}>当前默认使用项目鉴权配置</Text>
                </div>
                <Button 
                  type="primary"
                  size="large"
                  onClick={() => {
                    setEditing(true);
                  }}
                >
                  自定义
                </Button>
              </Space>
              
              {/* 点击自定义后显示创建表单 */}
              {editing && (
                <div style={{ marginTop: 24, textAlign: 'left' }}>
                  <Alert
                    message="创建自定义配置"
                    description="配置创建后将覆盖项目模板，如需恢复项目模板，可删除自定义配置"
                    type="info"
                    style={{ marginBottom: 24 }}
                  />
                  
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
            // 已有自定义配置时，显示表单和删除按钮
            <>
              <Alert
                message="自定义配置"
                description="当前环境使用自定义配置，可修改或删除以恢复项目模板"
                type="info"
                style={{ marginBottom: 24 }}
              />
              
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
                      onOk: () => deleteMutation.mutate()
                    });
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
  );
};

export default EnvironmentConfigEditor;