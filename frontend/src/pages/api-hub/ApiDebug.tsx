/**
 * 在线调试组件（V2.0 层级一 - API 资产库）
 * 符合前端代码规范：
 * 1. 防止重复提交：按钮加载状态
 * 2. 空值防御：使用可选链和默认值
 * 3. 友好异常提示：统一错误处理
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Select,
  Input,
  Form,
  message,
  Tabs,
  Alert,
  Tag,
  Space,
  Typography,
} from 'antd';
import {
  PlayCircleOutlined,
  SaveOutlined,
  CopyOutlined,
  ReloadOutlined,
  CheckOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { TabsProps } from 'antd';
import api from '../../services/api';

const { TextArea } = Input;

const { Text } = Typography;

interface Environment {
  id: number;
  name: string;
  base_url: string;
  project_id?: number;
  headers?: Record<string, string>;
  variables?: Record<string, any>;
}

interface ApiDefinition {
  id: number;
  method: string;
  path: string;
  schema_snapshot?: {
    parameters?: any[];
  };
  request_schema?: any;
  response_schema?: any;
}

interface DebugRequest {
  environment_id: number;
  path_params?: Record<string, any>;
  query_params?: Record<string, any>;
  headers?: Record<string, string>;
  body?: Record<string, any>;
}

interface DebugResponse {
  status_code: number;
  response_time: number;
  response_headers: Record<string, string>;
  response_body: any;
  request_url: string;
  request_method: string;
  request_headers: Record<string, string>;
  request_body: any;
}

interface ApiDebugProps {
  definition: ApiDefinition;
}

const ApiDebug: React.FC<ApiDebugProps> = ({ definition }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [debugResult, setDebugResult] = useState<DebugResponse | null>(null);
  const [activeTab, setActiveTab] = useState('request');
  const [, setPathParams] = useState<Record<string, any>>({});
  const [, setQueryParams] = useState<Record<string, any>>({});
  const [, setRequestBody] = useState<Record<string, any>>({});

  // 辅助函数：从定义中获取参数（优先从 schema_snapshot 获取）
  const getParameters = (): any[] => {
    if (definition?.schema_snapshot?.parameters) {
      return definition.schema_snapshot.parameters;
    } else if (definition?.request_schema?.parameters) {
      // 兼容旧数据（parameters 可能被错误地放在 request_schema 中）
      return definition.request_schema.parameters;
    } else if (Array.isArray(definition?.request_schema)) {
      // 兼容另一种格式
      return definition.request_schema;
    }
    return [];
  };

  // 获取环境列表
  const fetchEnvironments = async () => {
    try {
      const response = await api.get('/environments');
      console.log('环境列表响应:', response);
      if (response.code === 0) {
        setEnvironments(response.data.environments || []);
      }
    } catch (error) {
      console.error('获取环境列表失败:', error);
    }
  };


  // 智能注入鉴权信息（自动选择注入方式）
  const handleInjectAuth = async () => {
    const selectedEnvId = form.getFieldValue('environment_id');
    const environment = environments.find(e => e.id === selectedEnvId);

    if (!environment) {
      message.warning('请先选择环境');
      return;
    }

    try {
      const projectId = environment.project_id;
      if (!projectId) {
        message.warning('无法获取项目 ID');
        return;
      }

      // 调用后端智能注入接口
      const response = await api.get(`/projects/${projectId}/environments/${environment.id}/auth-config/inject`);

      if (response.code === 0 && response.data) {
        const headers = response.data.headers || {};
        const source = response.data.source || 'unknown';

        // 合并 Content-Type
        const resultHeaders: Record<string, string> = {
          'Content-Type': 'application/json',
          ...headers
        };

        form.setFieldsValue({
          headers: JSON.stringify(resultHeaders, null, 2),
        });

        // 根据来源显示不同的提示消息
        if (source === 'environment') {
          message.success('已注入环境配置的鉴权信息');
        } else if (source === 'project_auth') {
          message.success('已自动获取并注入 Token');
        } else {
          message.success('鉴权信息注入成功');
        }
      } else {
        message.warning(response.message || '注入鉴权信息失败');
      }
    } catch (error: any) {
      message.error(error.message || '注入鉴权信息失败');
    }
  };

  // 初始化表单默认值
  const getInitialValues = () => {
    const pathParams: Record<string, any> = {};
    const queryParams: Record<string, any> = {};
    const requestBody: Record<string, any> = {};

    const parameters = getParameters();
    
    // 处理 parameters 数组中的参数（path、query、header、body）
    if (parameters.length > 0) {
      parameters.forEach((param: any) => {
        const name = param.name;
        const paramIn = param.in; // path, query, body, header

        if (paramIn === 'path') {
          // 路径参数 - 使用默认值或占位符
          pathParams[name] = param.schema?.default || `{${name}}`;
        } else if (paramIn === 'query') {
          // 查询参数
          queryParams[name] = param.schema?.default || '';
        } else if (paramIn === 'body') {
          // 请求体参数
          if (param.schema?.type === 'object') {
            requestBody[name] = param.schema?.default || {};
          } else {
            requestBody[name] = param.schema?.default || '';
          }
        }
      });
    }
    
    // 如果没有 parameters，尝试从 request_schema.properties 中提取请求体
    // 适用于 POST/PUT 等有请求体的接口
    // 显示所有字段（不管是否是必填，只排除 readOnly 字段）
    if (Object.keys(requestBody).length === 0 && definition?.request_schema?.properties) {
      const properties = definition.request_schema.properties;
      Object.keys(properties).forEach(key => {
        const prop = properties[key];
        // 只排除 readOnly 字段（系统自动维护的字段）
        // 不排除必填字段，让用户填写所有可编辑字段
        if (!prop.readOnly) {
          // 根据字段类型设置默认值
          if (prop.type === 'string') {
            requestBody[key] = prop.default !== undefined ? prop.default : '';
          } else if (prop.type === 'number') {
            requestBody[key] = prop.default !== undefined ? prop.default : 0;
          } else if (prop.type === 'boolean') {
            requestBody[key] = prop.default !== undefined ? prop.default : false;
          } else if (prop.type === 'integer') {
            requestBody[key] = prop.default !== undefined ? prop.default : 0;
          } else if (prop.type === 'array') {
            requestBody[key] = prop.default !== undefined ? prop.default : [];
          } else if (prop.type === 'object') {
            requestBody[key] = prop.default !== undefined ? prop.default : {};
          } else if (prop.nullable === true) {
            requestBody[key] = null;
          } else {
            requestBody[key] = prop.default !== undefined ? prop.default : '';
          }
        }
      });
    }

    // 返回序列化后的字符串，因为 TextArea 组件需要字符串
    return {
      path_params: JSON.stringify(pathParams, null, 2),
      query_params: JSON.stringify(queryParams, null, 2),
      body: JSON.stringify(requestBody, null, 2),
      headers: JSON.stringify({
        'Content-Type': 'application/json',
      }, null, 2),
    };
  };

  useEffect(() => {
    fetchEnvironments();
  }, []); // 只在组件挂载时获取环境列表

  // 监听definition变化并设置表单值
  useEffect(() => {
    if (!definition) {
      return;
    }
    
    const parameters = getParameters();
    const newRequestBody: Record<string, any> = {};
    
    // 处理 parameters 数组中的参数
    if (parameters.length > 0) {
      const newPathParams: Record<string, any> = {};
      const newQueryParams: Record<string, any> = {};

      parameters.forEach((param: any) => {
        const name = param.name;
        const paramIn = param.in;

        if (paramIn === 'path') {
          newPathParams[name] = param.schema?.default || `{${name}}`;
        } else if (paramIn === 'query') {
          newQueryParams[name] = param.schema?.default || '';
        } else if (paramIn === 'body') {
          if (param.schema?.type === 'object') {
            newRequestBody[name] = param.schema?.default || {};
          } else {
            newRequestBody[name] = param.schema?.default || '';
          }
        }
      });

      setPathParams(newPathParams);
      setQueryParams(newQueryParams);
    }
    
    // 如果没有 parameters 中的 body 参数，尝试从 request_schema.properties 中提取
    // 显示所有字段（不管是否是必填，只排除 readOnly 字段）
    if (Object.keys(newRequestBody).length === 0 && definition?.request_schema?.properties) {
      const properties = definition.request_schema.properties;
      Object.keys(properties).forEach(key => {
        const prop = properties[key];
        // 只排除 readOnly 字段（系统自动维护的字段）
        if (!prop.readOnly) {
          // 根据字段类型设置默认值
          if (prop.type === 'string') {
            newRequestBody[key] = prop.default !== undefined ? prop.default : '';
          } else if (prop.type === 'number') {
            newRequestBody[key] = prop.default !== undefined ? prop.default : 0;
          } else if (prop.type === 'boolean') {
            newRequestBody[key] = prop.default !== undefined ? prop.default : false;
          } else if (prop.type === 'integer') {
            newRequestBody[key] = prop.default !== undefined ? prop.default : 0;
          } else if (prop.type === 'array') {
            newRequestBody[key] = prop.default !== undefined ? prop.default : [];
          } else if (prop.type === 'object') {
            newRequestBody[key] = prop.default !== undefined ? prop.default : {};
          } else if (prop.nullable === true) {
            newRequestBody[key] = null;
          } else {
            newRequestBody[key] = prop.default !== undefined ? prop.default : '';
          }
        }
      });
      setRequestBody(newRequestBody);
    } else if (Object.keys(newRequestBody).length > 0) {
      setRequestBody(newRequestBody);
    }
    
    // 同时更新表单值（使用getInitialValues确保序列化）
    const initialValues = getInitialValues();
    if (Object.keys(initialValues).length > 0) {
      form.setFieldsValue(initialValues);
    } else {
      // 如果没有参数，设置默认的空值
      form.setFieldsValue({
        path_params: '{}',
        query_params: '{}',
        body: '{}',
        headers: JSON.stringify({
          'Content-Type': 'application/json',
        }, null, 2),
      });
    }
  }, [definition, form]);

  // 发送调试请求
  const handleSendRequest = async (values: DebugRequest) => {
    setLoading(true);
    setDebugResult(null);

    try {
      // 将 JSON 字符串解析为对象
      const requestPayload = {
        environment_id: values.environment_id,
        path_params: typeof values.path_params === 'string' ? JSON.parse(values.path_params) : values.path_params,
        query_params: typeof values.query_params === 'string' ? JSON.parse(values.query_params) : values.query_params,
        headers: typeof values.headers === 'string' ? JSON.parse(values.headers) : values.headers,
        body: typeof values.body === 'string' ? JSON.parse(values.body) : values.body,
      };

      const response = await api.post(`/api-definitions/${definition.id}/debug`, requestPayload);

      if (response.code === 0) {
        setDebugResult(response.data);
        setActiveTab('response');
        message.success(`请求成功 (${response.data.response_time}ms)`);
      } else {
        message.error(response.message || '请求失败');
      }
    } catch (error: any) {
      console.error('调试失败:', error);
      message.error(error.message || '调试失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 获取状态码颜色
  const getStatusColor = (statusCode: number) => {
    if (statusCode >= 200 && statusCode < 300) return 'success';
    if (statusCode >= 300 && statusCode < 400) return 'processing';
    if (statusCode >= 400 && statusCode < 500) return 'warning';
    if (statusCode >= 500) return 'error';
    return 'default';
  };

  // 保存为用例
  const handleSaveAsCase = async () => {
    if (!debugResult) {
      message.warning('请先发送请求');
      return;
    }

    try {
      const formValues = form.getFieldsValue();
      const response = await api.post(`/api-definitions/${definition.id}/cases`, {
        name: `${definition.method} ${definition.path} - 调试用例`,
        description: '从在线调试保存的用例',
        request_data: {
          path_params: formValues.path_params,
          query_params: formValues.query_params,
          headers: formValues.headers,
          body: formValues.body,
        },
        environment_id: formValues.environment_id,
        assertion_rules: [
          {
            source: 'status',
            operator: 'equals',
            value: debugResult.status_code,
          },
        ],
      });

      if (response.code === 0) {
        message.success('保存成功');
      } else {
        message.error(response.message || '保存失败');
      }
    } catch (error) {
      console.error('保存失败:', error);
      message.error('保存失败，请稍后重试');
    }
  };

  // 根据响应自动生成断言
  const generateAssertionsFromResponse = (responseBody: any) => {
    const assertions: any[] = [];

    // 添加状态码断言
    if (debugResult) {
      assertions.push({
        source: 'status',
        operator: 'equals',
        value: debugResult.status_code,
      });
    }

    // 如果响应体是对象，添加关键字段断言
    if (responseBody && typeof responseBody === 'object') {
      // 检查 code 字段
      if (responseBody.code !== undefined) {
        assertions.push({
          source: 'body',
          operator: 'equals',
          field: '$.code',
          value: 0,
        });
      }

      // 检查 message 字段
      if (responseBody.message) {
        assertions.push({
          source: 'body',
          operator: 'not_empty',
          field: '$.message',
        });
      }

      // 检查 data 字段
      if (responseBody.data) {
        assertions.push({
          source: 'body',
          operator: 'not_null',
          field: '$.data',
        });
      }
    }

    // 将生成的断言显示在控制台
    console.log('自动生成的断言:', assertions);
    message.success(`已生成 ${assertions.length} 条断言，请查看控制台`);
  };

  // 格式化 JSON
  const formatJson = (data: any) => {
    if (typeof data === 'object' && data !== null) {
      return JSON.stringify(data, null, 2);
    }
    return String(data);
  };

  // Tab 内容
  const items: TabsProps['items'] = [
    {
      key: 'request',
      label: '请求参数',
      children: (
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSendRequest}
          initialValues={getInitialValues()}
        >
          <Form.Item
            name="environment_id"
            label="执行环境"
            rules={[{ required: true, message: '请选择执行环境' }]}
          >
            <Select placeholder="请选择环境">
              {environments.map((env) => (
                <Select.Option key={env.id} value={env.id}>
                  {env.name} ({env.base_url})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item 
            name="path_params" 
            label={
              <Space>
                <span>路径参数</span>
                {getParameters().filter((p: any) => p.in === 'path').length > 0 && (
                  <Tag color="blue">
                    {getParameters().filter((p: any) => p.in === 'path').length} 个参数
                  </Tag>
                )}
              </Space>
            }
            extra={
              getParameters().filter((p: any) => p.in === 'path').length > 0 ? (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                  <Text>参数说明：</Text>
                  {getParameters()
                    .filter((p: any) => p.in === 'path')
                    .map((param: any, idx: number) => (
                      <Tag key={idx} style={{ marginTop: 4 }}>
                        {param.name}: {param.description || param.schema?.type || 'unknown'}
                        {param.required && <Text type="danger"> *</Text>}
                      </Tag>
                    ))}
                </div>
              ) : (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-tertiary)' }}>
                  此接口没有路径参数
                </div>
              )
            }
          >
            <TextArea
              rows={3}
              placeholder='{"id": "123"}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item 
            name="query_params" 
            label={
              <Space>
                <span>查询参数</span>
                {getParameters().filter((p: any) => p.in === 'query').length > 0 && (
                  <Tag color="green">
                    {getParameters().filter((p: any) => p.in === 'query').length} 个参数
                  </Tag>
                )}
              </Space>
            }
            extra={
              getParameters().filter((p: any) => p.in === 'query').length > 0 ? (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                  <Text>参数说明：</Text>
                  {getParameters()
                    .filter((p: any) => p.in === 'query')
                    .map((param: any, idx: number) => (
                      <Tag key={idx} style={{ marginTop: 4 }}>
                        {param.name}: {param.description || param.schema?.type || 'unknown'}
                        {param.required && <Text type="danger"> *</Text>}
                      </Tag>
                    ))}
                </div>
              ) : (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-tertiary)' }}>
                  此接口没有查询参数
                </div>
              )
            }
          >
            <TextArea
              rows={3}
              placeholder='{"page": 1, "size": 10}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item
            name="headers"
            label={
              <Space>
                <span>请求头</span>
                <Button
                  type="link"
                  size="small"
                  icon={<ThunderboltOutlined />}
                  onClick={handleInjectAuth}
                >
                  注入鉴权信息
                </Button>
              </Space>
            }
            extra={
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-tertiary)' }}>
                自动根据环境配置注入鉴权信息（环境 headers/variables 或项目鉴权配置）
              </div>
            }
          >
            <TextArea
              rows={3}
              placeholder='{"Authorization": "Bearer token"}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item 
            name="body" 
            label={
              <Space>
                <span>请求体</span>
                {getParameters().filter((p: any) => p.in === 'body').length > 0 && (
                  <Tag color="orange">
                    {getParameters().filter((p: any) => p.in === 'body').length} 个参数
                  </Tag>
                )}
              </Space>
            }
            extra={
              getParameters().filter((p: any) => p.in === 'body').length > 0 ? (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                  <Text>参数说明：</Text>
                  {getParameters()
                    .filter((p: any) => p.in === 'body')
                    .map((param: any, idx: number) => (
                      <Tag key={idx} style={{ marginTop: 4 }}>
                        {param.name}: {param.description || param.schema?.type || 'unknown'}
                        {param.required && <Text type="danger"> *</Text>}
                      </Tag>
                    ))}
                </div>
              ) : (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-tertiary)' }}>
                  此接口没有请求体参数
                </div>
              )
            }
          >
            <TextArea
              rows={8}
              placeholder='{"username": "test", "password": "123456"}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Space>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={loading}
              htmlType="submit"
            >
              发送请求
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => form.resetFields()}>
              重置
            </Button>
          </Space>
        </Form>
      ),
    },
    {
      key: 'response',
      label: '响应结果',
      children: debugResult ? (
        <div>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* 状态信息 */}
            <Alert
              message={
                <Space>
                  <Tag color={getStatusColor(debugResult.status_code)}>
                    {debugResult.status_code}
                  </Tag>
                  <Text type="secondary">{debugResult.response_time}ms</Text>
                </Space>
              }
              type={debugResult.status_code >= 400 ? 'error' : 'success'}
            />

            {/* 响应头 */}
            <div>
              <Text strong>响应头</Text>
              <div style={{ marginTop: 8, background: 'var(--bg-tertiary)', padding: 12, borderRadius: 4 }}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {formatJson(debugResult.response_headers)}
                </pre>
              </div>
            </div>

            {/* 响应体 */}
            <div>
              <Space>
                <Text strong>响应体</Text>
                <Button
                  type="link"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => {
                    navigator.clipboard.writeText(formatJson(debugResult.response_body));
                    message.success('已复制');
                  }}
                >
                  复制
                </Button>
                <Button
                  type="link"
                  size="small"
                  icon={<CheckOutlined />}
                  onClick={() => {
                    generateAssertionsFromResponse(debugResult.response_body);
                  }}
                >
                  自动生成断言
                </Button>
              </Space>
              <div style={{ marginTop: 8, background: 'var(--bg-tertiary)', padding: 12, borderRadius: 4 }}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {formatJson(debugResult.response_body)}
                </pre>
              </div>
            </div>

            {/* 操作按钮 */}
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSaveAsCase}
            >
              保存为用例
            </Button>
          </Space>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-tertiary)' }}>
          请先发送请求查看响应结果
        </div>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <Tag color="blue">{definition.method}</Tag>
          <Text>{definition.path}</Text>
        </Space>
      }
      extra={
        <Text type="secondary">在线调试</Text>
      }
    >
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />
    </Card>
  );
};

export default ApiDebug;
