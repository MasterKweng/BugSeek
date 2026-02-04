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
  Row,
  Col,
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
  Divider,
} from 'antd';
import {
  PlayCircleOutlined,
  SaveOutlined,
  CopyOutlined,
  ReloadOutlined,
  CheckOutlined,
} from '@ant-design/icons';
import type { TabsProps } from 'antd';
import api from '../../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface Environment {
  id: number;
  name: string;
  base_url: string;
}

interface ApiDefinition {
  id: number;
  method: string;
  path: string;
  request_schema: any;
  response_schema: any;
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

  // 获取环境列表
  const fetchEnvironments = async () => {
    try {
      const response = await api.get('/environments');
      if (response.code === 0) {
        setEnvironments(response.data.environments || []);
      }
    } catch (error) {
      console.error('获取环境列表失败:', error);
    }
  };

  useEffect(() => {
    fetchEnvironments();
  }, []);

  // 发送调试请求
  const handleSendRequest = async (values: DebugRequest) => {
    setLoading(true);
    setDebugResult(null);

    try {
      const response = await api.post(`/api-definitions/${definition.id}/debug`, {
        environment_id: values.environment_id,
        path_params: values.path_params,
        query_params: values.query_params,
        headers: values.headers,
        body: values.body,
      });

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
          initialValues={{
            headers: {
              'Content-Type': 'application/json',
            },
          }}
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

          <Form.Item name="path_params" label="路径参数">
            <TextArea
              rows={3}
              placeholder='{"id": "123"}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item name="query_params" label="查询参数">
            <TextArea
              rows={3}
              placeholder='{"page": 1, "size": 10}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item name="headers" label="请求头">
            <TextArea
              rows={3}
              placeholder='{"Authorization": "Bearer token"}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item name="body" label="请求体">
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
              <div style={{ marginTop: 8, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
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
              <div style={{ marginTop: 8, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
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
        <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
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