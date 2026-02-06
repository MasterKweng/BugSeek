/**
 * 鉴权配置页面组件
 * 符合前端代码规范
 */

import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card,
  Form,
  Switch,
  Select,
  Input,
  Button,
  Space,
  Divider,
  Alert,
  Spin,
  message
} from 'antd';
import { SaveOutlined, PlayCircleOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons';

import {
  AuthConfig,
  AuthTypeEnum,
  InjectionTargetEnum,
  SourceModeEnum,
  AuthTypeLabels,
  InjectionTargetLabels,
  SourceModeLabels
} from '../types/auth';
import {
  getAuthConfig,
  createAuthConfig,
  updateAuthConfig,
  deleteAuthConfig,
  testAcquisition
} from '../services/auth';
import InputMappingForm from '../components/InputMappingForm';
import ExtractRuleForm from '../components/ExtractRuleForm';
import TestLoginDrawer from '../components/TestLoginDrawer';

const { Option } = Select;
const { TextArea } = Input;

interface AuthConfigPageProps {
  projectId?: number;
}

const AuthConfigPage: React.FC<AuthConfigPageProps> = ({ projectId: propProjectId }) => {
  const { projectId: routeProjectId } = useParams<{ projectId: string }>();
  const projectId = propProjectId || parseInt(routeProjectId || '0');

  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [sourceMode, setSourceMode] = useState<SourceModeEnum>(SourceModeEnum.STATIC);
  const [testDrawerVisible, setTestDrawerVisible] = useState(false);

  // 加载配置
  useEffect(() => {
    loadConfig();
  }, [projectId]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await getAuthConfig(projectId);
      if (response.code === 0 && response.data) {
        const data = response.data;
        setConfig(data);
        setSourceMode(data.source_mode);
        form.setFieldsValue({
          enabled: data.enabled,
          auth_type: data.auth_type,
          injection_target: data.injection.target,
          injection_key: data.injection.key,
          injection_template: data.injection.value_template,
          source_mode: data.source_mode,
          static_value: data.static_value,
          login_api_id: data.login_api_id,
          input_mappings: data.input_mappings,
          extract_rules: data.extract_rules
        });
      }
    } catch (error) {
      message.error('加载鉴权配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const data = {
        enabled: values.enabled,
        auth_type: values.auth_type,
        injection: {
          target: values.injection_target,
          key: values.injection_key,
          value_template: values.injection_template
        },
        source_mode: values.source_mode,
        static_value: values.static_value,
        login_api_id: values.login_api_id,
        input_mappings: values.input_mappings || [],
        extract_rules: values.extract_rules || []
      };

      let response;
      if (config) {
        response = await updateAuthConfig(projectId, data);
      } else {
        response = await createAuthConfig(projectId, data);
      }

      if (response.code === 0) {
        message.success('保存成功');
        loadConfig();
      } else {
        message.error(response.message || '保存失败');
      }
    } catch (error) {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!config) return;

    const confirmed = window.confirm('确定要删除鉴权配置吗？');
    if (!confirmed) return;

    try {
      const response = await deleteAuthConfig(projectId);
      if (response.code === 0) {
        message.success('删除成功');
        setConfig(null);
        form.resetFields();
      } else {
        message.error(response.message || '删除失败');
      }
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleTest = () => {
    setTestDrawerVisible(true);
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <Card title="鉴权配置" extra={
        <Space>
          {config && (
            <Button danger onClick={handleDelete}>
              删除配置
            </Button>
          )}
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleTest}
            disabled={!config || !config.enabled}
          >
            测试登录
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saving}
          >
            保存
          </Button>
        </Space>
      }>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            enabled: false,
            auth_type: AuthTypeEnum.BEARER_TOKEN,
            injection_target: InjectionTargetEnum.HEADER,
            injection_template: '{{ACCESS_TOKEN}}',
            source_mode: SourceModeEnum.STATIC,
            input_mappings: [],
            extract_rules: []
          }}
        >
          <Form.Item label="启用鉴权" name="enabled" valuePropName="checked">
            <Switch />
          </Form.Item>

          <Divider>基本配置</Divider>

          <Form.Item
            label="鉴权类型"
            name="auth_type"
            rules={[{ required: true, message: '请选择鉴权类型' }]}
          >
            <Select>
              {Object.entries(AuthTypeLabels).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="注入位置"
            name="injection_target"
            rules={[{ required: true, message: '请选择注入位置' }]}
          >
            <Select>
              {Object.entries(InjectionTargetLabels).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="注入键名"
            name="injection_key"
            dependencies={['injection_target']}
            rules={[
              ({ getFieldValue }) => ({
                validator(_, value) {
                  const target = getFieldValue('injection_target');
                  if (target === InjectionTargetEnum.QUERY || target === InjectionTargetEnum.HEADER) {
                    if (!value) {
                      return Promise.reject('请输入注入键名');
                    }
                  }
                  return Promise.resolve();
                }
              })
            ]}
          >
            <Input placeholder="例如: Authorization" />
          </Form.Item>

          <Form.Item
            label="注入模板"
            name="injection_template"
            rules={[{ required: true, message: '请输入注入模板' }]}
            tooltip="使用 {{变量名}} 引用提取的变量"
          >
            <TextArea
              rows={2}
              placeholder="例如: Bearer {{ACCESS_TOKEN}}"
            />
          </Form.Item>

          <Divider>凭证来源</Divider>

          <Form.Item
            label="来源模式"
            name="source_mode"
            rules={[{ required: true, message: '请选择来源模式' }]}
          >
            <Select onChange={(value: SourceModeEnum) => setSourceMode(value)}>
              {Object.entries(SourceModeLabels).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          {sourceMode === SourceModeEnum.STATIC && (
            <Form.Item
              label="静态凭证值"
              name="static_value"
              rules={[{ required: true, message: '请输入静态凭证值' }]}
            >
              <TextArea rows={3} placeholder="例如: your_static_token_here" />
            </Form.Item>
          )}

          {sourceMode === SourceModeEnum.DYNAMIC && (
            <>
              <Form.Item
                label="登录接口 ID"
                name="login_api_id"
                rules={[{ required: true, message: '请输入登录接口 ID' }]}
                tooltip="从 API 资产库选择登录接口"
              >
                <Input type="number" placeholder="请输入 API ID" />
              </Form.Item>

              <Form.Item label="参数映射" name="input_mappings">
                <InputMappingForm />
              </Form.Item>

              <Form.Item label="提取规则" name="extract_rules">
                <ExtractRuleForm />
              </Form.Item>
            </>
          )}
        </Form>

        {sourceMode === SourceModeEnum.DYNAMIC && (
          <Alert
            message="提示"
            description="参数映射用于将提取的变量映射到登录接口的参数，提取规则用于从登录响应中提取凭证变量。"
            type="info"
            showIcon
            style={{ marginTop: '16px' }}
          />
        )}
      </Card>

      <TestLoginDrawer
        visible={testDrawerVisible}
        onClose={() => setTestDrawerVisible(false)}
        projectId={projectId}
      />
    </div>
  );
};

export default AuthConfigPage;