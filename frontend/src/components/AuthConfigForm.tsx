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
   * 处理鉴权类型变化
   * 当选择 BASIC/BEARER/API_KEY/SESSION 时，自动设置注入配置并切换到静态模式
   */
  const handleAuthTypeChange = (value: AuthTypeEnum) => {
    switch (value) {
      case AuthTypeEnum.BASIC:
        form.setFieldsValue({
          source_mode: SourceModeEnum.STATIC,
          injection_target: InjectionTargetEnum.HEADER,
          injection_key: 'Authorization',
          injection_template: 'Basic {static_value}'
        });
        break;
        
      case AuthTypeEnum.BEARER:
        form.setFieldsValue({
          source_mode: SourceModeEnum.STATIC,
          injection_target: InjectionTargetEnum.HEADER,
          injection_key: 'Authorization',
          injection_template: 'Bearer {static_value}'
        });
        break;
        
      case AuthTypeEnum.API_KEY:
        form.setFieldsValue({
          source_mode: SourceModeEnum.STATIC,
          injection_target: InjectionTargetEnum.HEADER,
          injection_key: '',
          injection_template: '{static_value}'
        });
        break;
        
      case AuthTypeEnum.SESSION:
        form.setFieldsValue({
          source_mode: SourceModeEnum.STATIC,
          injection_target: InjectionTargetEnum.HEADER,
          injection_key: 'Cookie',
          injection_template: '{static_value}'
        });
        break;
        
      case AuthTypeEnum.NONE:
      case AuthTypeEnum.CUSTOM:
      default:
        // 不自动设置，保持用户选择
        break;
    }
  };
  
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
      
      // 处理静态模式下的简化输入
      let processedStaticValue = values.static_value;
      
      if (values.source_mode === SourceModeEnum.STATIC) {
        switch (values.auth_type) {
          case AuthTypeEnum.BASIC:
            // BASIC 类型：将 username:password 转换为 base64
            const username = values.basic_username || '';
            const password = values.basic_password || '';
            if (username && password) {
              const credentials = btoa(`${username}:${password}`);
              processedStaticValue = credentials;
            } else {
              processedStaticValue = values.static_value || '';
            }
            break;
            
          case AuthTypeEnum.BEARER:
            // BEARER 类型：直接使用 token
            processedStaticValue = values.bearer_token || '';
            break;
            
          case AuthTypeEnum.API_KEY:
            // API KEY 类型：直接使用值
            processedStaticValue = values.api_key_value || '';
            // 需要更新注入键名为用户输入的 Key 名称
            form.setFieldValue('injection_key', values.api_key_key || '');
            break;
            
          case AuthTypeEnum.SESSION:
            // SESSION 类型：直接使用 session_id
            processedStaticValue = values.session_id || '';
            break;
            
          case AuthTypeEnum.NONE:
          case AuthTypeEnum.CUSTOM:
          default:
            processedStaticValue = values.static_value || '';
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
        static_value: processedStaticValue,
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
          <Select onChange={handleAuthTypeChange}>
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
        
        {/* 简化配置界面：当选择标准鉴权类型时显示 */}
        <Form.Item noStyle shouldUpdate={(prev, curr) => prev.auth_type !== curr.auth_type}>
          {({ getFieldValue }) => {
            const authType = getFieldValue('auth_type') as AuthTypeEnum;
            
            // 非标准鉴权类型，不显示简化配置
            if (![AuthTypeEnum.BASIC, AuthTypeEnum.BEARER, AuthTypeEnum.API_KEY, AuthTypeEnum.SESSION].includes(authType)) {
              return null;
            }
            
            return (
              <div style={{ marginTop: 16, padding: 16, background: '#f5f5f5', borderRadius: 4 }}>
                <Divider orientation="left" style={{ margin: '0 0 12px 0' }}>简化配置</Divider>
                
                {authType === AuthTypeEnum.BASIC && (
                  <div>
                    <p style={{ color: '#666', fontSize: 12, marginBottom: 8 }}>
                      Basic 认证：输入用户名和密码，系统将自动拼接为 base64(username:password)
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
                )}
                
                {authType === AuthTypeEnum.BEARER && (
                  <div>
                    <p style={{ color: '#666', fontSize: 12, marginBottom: 8 }}>
                      Bearer 认证：输入 Token
                    </p>
                    <Form.Item
                      label="Token"
                      name="bearer_token"
                      rules={[{ required: true, message: '请输入 Token' }]}
                    >
                      <Input placeholder="请输入 Token" />
                    </Form.Item>
                  </div>
                )}
                
                {authType === AuthTypeEnum.API_KEY && (
                  <div>
                    <p style={{ color: '#666', fontSize: 12, marginBottom: 8 }}>
                      API Key 认证：配置 API Key 名称、值和添加位置
                    </p>
                    <Form.Item
                      label="Key 名称"
                      name="api_key_key"
                      rules={[{ required: true, message: '请输入 Key 名称' }]}
                    >
                      <Input placeholder="如 X-API-Key" />
                    </Form.Item>
                    <Form.Item
                      label="Key 值"
                      name="api_key_value"
                      rules={[{ required: true, message: '请输入 Key 值' }]}
                    >
                      <Input placeholder="请输入 Key 值" />
                    </Form.Item>
                    <Form.Item
                      label="添加位置"
                      name="api_key_add_to"
                      rules={[{ required: true, message: '请选择添加位置' }]}
                    >
                      <Select placeholder="请选择添加位置">
                        <Option value="header">Header</Option>
                        <Option value="query">Query Params</Option>
                      </Select>
                    </Form.Item>
                  </div>
                )}
                
                {authType === AuthTypeEnum.SESSION && (
                  <div>
                    <p style={{ color: '#666', fontSize: 12, marginBottom: 8 }}>
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
                      initialValue="sessionid"
                      rules={[{ required: true, message: '请输入 Cookie 名称' }]}
                    >
                      <Input placeholder="如 sessionid" />
                    </Form.Item>
                  </div>
                )}
              </div>
            );
          }}
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