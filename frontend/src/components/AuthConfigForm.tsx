/**
 * 鉴权配置表单组件
 * 符合前端代码规范
 */

import React, { useEffect } from 'react';
import { 
  Form, 
  Switch, 
  Select, 
  Input, 
  Space, 
  Button, 
  Card, 
  Divider,
  message
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { 
  AuthTypeEnum, 
  InjectionTargetEnum, 
  SourceModeEnum,
  MappingLocationEnum,
  AuthTypeLabels,
  InjectionTargetLabels,
  SourceModeLabels,
  type AuthConfigCreate,
  type ProjectAuthTemplate
} from '../types/auth';
import InputMappingForm from './InputMappingForm';
import ExtractRuleForm from './ExtractRuleForm';

const { Option } = Select;

interface AuthConfigFormProps {
  mode: 'template' | 'environment';
  initialValues?: ProjectAuthTemplate | null;
  projectTemplate?: ProjectAuthTemplate | null;
  onSave: (data: AuthConfigCreate) => void;
  loading?: boolean;
}

/**
 * 鉴权配置表单
 * 支持项目模板和环境级配置两种模式
 */
const AuthConfigForm: React.FC<AuthConfigFormProps> = ({
  mode,
  initialValues,
  projectTemplate,
  onSave,
  loading = false
}) => {
  const [form] = Form.useForm();
  
  /**
   * 初始化表单
   */
  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue({
        enabled: initialValues.enabled,
        auth_type: initialValues.auth_type,
        injection_target: initialValues.injection.target,
        injection_key: initialValues.injection.key,
        injection_template: initialValues.injection.value_template,
        source_mode: initialValues.source_mode,
        static_value: initialValues.static_value,
        login_api_id: initialValues.login_api_id,
        login_auth_type: initialValues.login_auth_type || AuthTypeEnum.NONE,
        input_mappings: initialValues.input_mappings,
        extract_rules: initialValues.extract_rules
      });
    }
  }, [initialValues, form]);
  
  /**
   * 处理来源模式变化
   */
  const handleSourceModeChange = (value: SourceModeEnum) => {
    if (value === SourceModeEnum.STATIC) {
      form.setFieldValue('login_api_id', undefined);
    } else {
      form.setFieldValue('static_value', undefined);
    }
  };
  
  /**
   * 处理提交
   */
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      // 处理参数映射：根据 login_auth_type 转换为标准格式
      let processedInputMappings = values.input_mappings || [];
      
      if (values.source_mode === SourceModeEnum.DYNAMIC) {
        switch (values.login_auth_type) {
          case AuthTypeEnum.BASIC:
            processedInputMappings = [
              { location: MappingLocationEnum.BODY, key: 'username', value: values.basic_username || '' },
              { location: MappingLocationEnum.BODY, key: 'password', value: values.basic_password || '' }
            ];
            break;
            
          case AuthTypeEnum.BEARER:
            processedInputMappings = [
              { location: MappingLocationEnum.BODY, key: 'token', value: values.bearer_token || '' }
            ];
            break;
            
          case AuthTypeEnum.API_KEY:
            const add_to = values.api_key_add_to || 'header';
            processedInputMappings = [
              { 
                location: add_to === 'header' ? MappingLocationEnum.HEADER : MappingLocationEnum.QUERY, 
                key: values.api_key_key || '', 
                value: values.api_key_value || '' 
              }
            ];
            break;
            
          case AuthTypeEnum.SESSION:
            processedInputMappings = [
              { location: MappingLocationEnum.HEADER, key: values.session_cookie || 'sessionid', value: values.session_id || '' }
            ];
            break;
            
          case AuthTypeEnum.NONE:
          case AuthTypeEnum.CUSTOM:
          default:
            processedInputMappings = values.input_mappings || [];
            break;
        }
      }
      
      const data: AuthConfigCreate = {
        enabled: values.enabled || false,
        auth_type: values.auth_type,
        injection: {
          target: values.injection_target,
          key: values.injection_key,
          value_template: values.injection_template || ''
        },
        source_mode: values.source_mode,
        static_value: values.static_value,
        login_api_id: values.login_api_id,
        login_auth_type: values.login_auth_type,
        input_mappings: processedInputMappings,
        extract_rules: values.extract_rules || []
      };
      
      // 验证数据
      if (data.source_mode === SourceModeEnum.DYNAMIC && !data.login_api_id) {
        message.error('动态模式必须提供登录接口 ID');
        return;
      }
      
      if (data.source_mode === SourceModeEnum.STATIC && !data.static_value) {
        message.error('静态模式必须提供凭证值');
        return;
      }
      
      onSave(data);
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };
  
  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={{
        enabled: false,
        auth_type: AuthTypeEnum.NONE,
        injection_target: InjectionTargetEnum.HEADER,
        source_mode: SourceModeEnum.STATIC,
        login_auth_type: AuthTypeEnum.NONE,
        input_mappings: [],
        extract_rules: []
      }}
    >
      {/* 基本配置 */}
      <Card title="基本配置" style={{ marginBottom: 16 }}>
        <Form.Item
          label="启用鉴权"
          name="enabled"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
        
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
          rules={[{ required: true, message: '请输入注入键名' }]}
        >
          <Input placeholder="如 Authorization、X-API-Key" />
        </Form.Item>
        
        <Form.Item
          label="值模板"
          name="injection_template"
          rules={[{ required: true, message: '请输入值模板' }]}
        >
          <Input.TextArea 
            rows={2} 
            placeholder="如 Bearer {{ACCESS_TOKEN}} 或 {{API_KEY}}"
          />
        </Form.Item>
      </Card>
      
      {/* 来源配置 */}
      <Card title="来源配置" style={{ marginBottom: 16 }}>
        <Form.Item
          label="来源模式"
          name="source_mode"
          rules={[{ required: true, message: '请选择来源模式' }]}
        >
          <Select onChange={handleSourceModeChange}>
            {Object.entries(SourceModeLabels).map(([value, label]) => (
              <Option key={value} value={value}>{label}</Option>
            ))}
          </Select>
        </Form.Item>
        
        <Form.Item noStyle shouldUpdate={(prev, curr) => prev.source_mode !== curr.source_mode}>
          {({ getFieldValue }) => {
            const sourceMode = getFieldValue('source_mode');
            
            if (sourceMode === SourceModeEnum.STATIC) {
              return (
                <Form.Item
                  label="静态凭证值"
                  name="static_value"
                  rules={[{ required: true, message: '请输入静态凭证值' }]}
                >
                  <Input.Password placeholder="请输入静态凭证值" />
                </Form.Item>
              );
            }
            
            return (
              <Form.Item
                label="登录接口 ID"
                name="login_api_id"
                rules={[{ required: true, message: '请输入登录接口 ID' }]}
              >
                <Input type="number" placeholder="请输入登录接口 ID" />
              </Form.Item>
            );
          }}
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, curr) => prev.source_mode !== curr.source_mode}>
          {({ getFieldValue }) => {
            const sourceMode = getFieldValue('source_mode');
            
            if (sourceMode !== SourceModeEnum.DYNAMIC) {
              return null;
            }
            
            return (
              <Form.Item
                label="登录接口鉴权类型"
                name="login_auth_type"
                tooltip="指定调用登录接口时的鉴权方式，会影响参数映射的使用"
                rules={[{ required: true, message: '请选择登录接口鉴权类型' }]}
              >
                <Select placeholder="请选择登录接口鉴权类型">
                  <Option value={AuthTypeEnum.NONE}>无（自定义）</Option>
                  <Option value={AuthTypeEnum.BASIC}>Basic 认证</Option>
                  <Option value={AuthTypeEnum.BEARER}>Bearer 认证</Option>
                  <Option value={AuthTypeEnum.API_KEY}>API Key</Option>
                  <Option value={AuthTypeEnum.SESSION}>Session</Option>
                  <Option value={AuthTypeEnum.CUSTOM}>自定义</Option>
                </Select>
              </Form.Item>
            );
          }}
        </Form.Item>

        <Divider orientation="left">参数映射</Divider>
        <Form.Item noStyle shouldUpdate={(prev, curr) => prev.source_mode !== curr.source_mode || prev.login_auth_type !== curr.login_auth_type}>
          {({ getFieldValue }) => {
            const sourceMode = getFieldValue('source_mode');
            const loginAuthType = getFieldValue('login_auth_type') as AuthTypeEnum;
            
            // 非动态模式，不显示参数映射
            if (sourceMode !== SourceModeEnum.DYNAMIC) {
              return null;
            }
            
            // 动态模式：根据 login_auth_type 显示简化表单
            switch (loginAuthType) {
              case AuthTypeEnum.BASIC:
                return (
                  <div style={{ marginBottom: 16 }}>
                    <p style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
                      Basic 认证：输入用户名和密码，系统将自动构建 Basic 认证请求头
                    </p>
                    <Form.Item
                      label="Username"
                      name="basic_username"
                      rules={[{ required: true, message: '请输入用户名' }]}
                    >
                      <Input placeholder="请输入用户名" />
                    </Form.Item>
                    <Form.Item
                      label="Password"
                      name="basic_password"
                      rules={[{ required: true, message: '请输入密码' }]}
                    >
                      <Input.Password placeholder="请输入密码" />
                    </Form.Item>
                  </div>
                );
              
              case AuthTypeEnum.BEARER:
                return (
                  <div style={{ marginBottom: 16 }}>
                    <p style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
                      Bearer 认证：输入 Token，系统将自动构建 Bearer 认证请求头
                    </p>
                    <Form.Item
                      label="Token"
                      name="bearer_token"
                      rules={[{ required: true, message: '请输入 Token' }]}
                    >
                      <Input placeholder="请输入 Token" />
                    </Form.Item>
                  </div>
                );
              
              case AuthTypeEnum.API_KEY:
                return (
                  <div style={{ marginBottom: 16 }}>
                    <p style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
                      API Key 认证：配置 API Key 和添加位置
                    </p>
                    <Form.Item
                      label="Key"
                      name="api_key_key"
                      rules={[{ required: true, message: '请输入参数名' }]}
                    >
                      <Input placeholder="如 X-API-Key" />
                    </Form.Item>
                    <Form.Item
                      label="Value"
                      name="api_key_value"
                      rules={[{ required: true, message: '请输入 API Key 值' }]}
                    >
                      <Input placeholder="请输入 API Key 值" />
                    </Form.Item>
                    <Form.Item
                      label="添加到"
                      name="api_key_add_to"
                      rules={[{ required: true, message: '请选择添加位置' }]}
                    >
                      <Select placeholder="请选择添加位置">
                        <Option value="header">Header</Option>
                        <Option value="query">Query Params</Option>
                      </Select>
                    </Form.Item>
                  </div>
                );
              
              case AuthTypeEnum.SESSION:
                return (
                  <div style={{ marginBottom: 16 }}>
                    <p style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
                      Session 认证：输入 Session ID 和 Cookie 名称
                    </p>
                    <Form.Item
                      label="Session ID"
                      name="session_id"
                      rules={[{ required: true, message: '请输入 Session ID' }]}
                    >
                      <Input placeholder="请输入 Session ID" />
                    </Form.Item>
                    <Form.Item
                      label="Cookie 名称"
                      name="session_cookie"
                      rules={[{ required: true, message: '请输入 Cookie 名称' }]}
                    >
                      <Input placeholder="如 sessionid" />
                    </Form.Item>
                  </div>
                );
              
              case AuthTypeEnum.NONE:
              case AuthTypeEnum.CUSTOM:
              default:
                return (
                  <Form.List name="input_mappings">
                    {(fields, { add, remove }) => (
                      <>
                        {fields.map((field, index) => (
                          <InputMappingForm
                            key={field.key}
                            field={field}
                            index={index}
                            onRemove={() => remove(field.name)}
                          />
                        ))}
                        <Button
                          type="dashed"
                          onClick={() => add({ location: 'body', key: '', value: '' })}
                          block
                          icon={<PlusOutlined />}
                          style={{ marginBottom: 16 }}
                        >
                          添加参数映射
                        </Button>
                      </>
                    )}
                  </Form.List>
                );
            }
          }}
        </Form.Item>

        <Divider orientation="left">提取规则</Divider>
        <Form.List name="extract_rules">
          {(fields, { add, remove }) => (
            <>
              {fields.map((field, index) => (
                <ExtractRuleForm
                  key={field.key}
                  field={field}
                  index={index}
                  onRemove={() => remove(field.name)}
                />
              ))}
              <Button
                type="dashed"
                onClick={() => add({ name: '', source: 'body', expression: '' })}
                block
                icon={<PlusOutlined />}
              >
                添加提取规则
              </Button>
            </>
          )}
        </Form.List>
      </Card>
      
      {/* 操作按钮 */}
      <Space>
        <Button type="primary" onClick={handleSubmit} loading={loading}>
          保存配置
        </Button>
        <Button onClick={() => form.resetFields()}>
          重置
        </Button>
      </Space>
    </Form>
  );
};

export default AuthConfigForm;