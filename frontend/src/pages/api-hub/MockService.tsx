/**
 * Mock 服务组件（V2.0 层级一 - API 资产库）
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
  Input,
  Form,
  message,
  Alert,
  Tag,
  Space,
  Typography,
  InputNumber,
  Switch,
  Divider,
  Tabs,
} from 'antd';
import {
  CopyOutlined,
  SaveOutlined,
  ReloadOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import type { TabsProps } from 'antd';
import api from '../../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface ApiDefinition {
  id: number;
  method: string;
  path: string;
  mock_data?: any;
  mock_rules?: any;
  response_schema?: any;
}

interface MockServiceProps {
  definition: ApiDefinition;
}

const MockService: React.FC<MockServiceProps> = ({ definition }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [mockUrl, setMockUrl] = useState<string>('');
  const [activeTab, setActiveTab] = useState('data');

  // 获取 Mock 地址
  const fetchMockUrl = async () => {
    try {
      const response = await api.get(`/api-definitions/${definition.id}/mock-url`);
      if (response.code === 0) {
        setMockUrl(response.data.mock_url);
      }
    } catch (error) {
      console.error('获取 Mock 地址失败:', error);
    }
  };

  useEffect(() => {
    fetchMockUrl();
  }, [definition.id]);

  useEffect(() => {
    if (definition.mock_data) {
      form.setFieldsValue({
        mock_data: JSON.stringify(definition.mock_data, null, 2),
        delay: definition.mock_rules?.delay || 0,
        error_rate: definition.mock_rules?.error_rate || 0,
        enabled: definition.mock_rules?.enabled !== false,
      });
    }
  }, [definition, form]);

  // 保存 Mock 数据
  const handleSave = async (values: any) => {
    setLoading(true);

    try {
      let mockData;
      try {
        mockData = JSON.parse(values.mock_data);
      } catch (e) {
        message.error('Mock 数据格式错误，请检查 JSON 语法');
        setLoading(false);
        return;
      }

      const mockRules = {
        delay: values.delay || 0,
        error_rate: values.error_rate || 0,
        enabled: values.enabled !== false,
      };

      const response = await api.put(`/api-definitions/${definition.id}/mock-data`, {
        mock_data: mockData,
        mock_rules: mockRules,
      });

      if (response.code === 0) {
        message.success('保存成功');
      } else {
        message.error(response.message || '保存失败');
      }
    } catch (error) {
      console.error('保存失败:', error);
      message.error('保存失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 复制 Mock 地址
  const handleCopyUrl = () => {
    const fullUrl = `${window.location.origin}${mockUrl}`;
    navigator.clipboard.writeText(fullUrl);
    message.success('Mock 地址已复制');
  };

  // 生成默认 Mock 数据
  const generateDefaultMock = () => {
    if (!definition.response_schema) {
      message.warning('没有响应 Schema，无法生成默认 Mock 数据');
      return;
    }

    const generateFromSchema = (schema: any): any => {
      if (!schema) return null;

      // 根据类型生成默认值
      if (schema.type === 'string') {
        return schema.example || 'mock_string';
      }
      if (schema.type === 'number' || schema.type === 'integer') {
        return schema.example || 123;
      }
      if (schema.type === 'boolean') {
        return schema.example || true;
      }
      if (schema.type === 'array') {
        return [generateFromSchema(schema.items)];
      }
      if (schema.type === 'object') {
        const result: any = {};
        if (schema.properties) {
          Object.keys(schema.properties).forEach(key => {
            result[key] = generateFromSchema(schema.properties[key]);
          });
        }
        return result;
      }
      return null;
    };

    const defaultMock = {
      code: 0,
      message: 'success',
      data: generateFromSchema(definition.response_schema),
    };

    form.setFieldsValue({
      mock_data: JSON.stringify(defaultMock, null, 2),
    });

    message.success('已生成默认 Mock 数据');
  };

  // 格式化 JSON
  const formatJson = () => {
    const value = form.getFieldValue('mock_data');
    try {
      const parsed = JSON.parse(value);
      form.setFieldsValue({
        mock_data: JSON.stringify(parsed, null, 2),
      });
    } catch (e) {
      message.error('JSON 格式错误，无法格式化');
    }
  };

  // Tab 内容
  const items: TabsProps['items'] = [
    {
      key: 'data',
      label: 'Mock 数据',
      children: (
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
        >
          <Alert
            message="Mock 数据模板"
            description="使用 Mock.js 语法生成动态数据，如：@name、@email、@date"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Form.Item
            name="mock_data"
            label="Mock 数据"
            rules={[{ required: true, message: '请输入 Mock 数据' }]}
          >
            <TextArea
              rows={15}
              placeholder='{"code": 0, "message": "success", "data": {"id": "@id", "name": "@name"}}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Space>
            <Button icon={<ReloadOutlined />} onClick={formatJson}>
              格式化
            </Button>
            <Button onClick={generateDefaultMock}>
              生成默认数据
            </Button>
          </Space>

          <Divider />

          <Form.Item>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={loading}
              htmlType="submit"
            >
              保存 Mock 数据
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'rules',
      label: 'Mock 规则',
      children: (
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
        >
          <Form.Item name="enabled" label="启用 Mock" valuePropName="checked">
            <Switch />
          </Form.Item>

          <Form.Item
            name="delay"
            label="响应延迟（毫秒）"
            tooltip="模拟网络延迟，0 表示不延迟"
          >
            <InputNumber min={0} max={10000} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="error_rate"
            label="错误率（%）"
            tooltip="模拟接口不稳定，0 表示不返回错误"
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={loading}
              htmlType="submit"
            >
              保存 Mock 规则
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'url',
      label: 'Mock 地址',
      children: (
        <div>
          <Alert
            message="Mock 地址"
            description="复制此地址到 HTTP 客户端（如 Postman）即可调用 Mock 接口"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <div>
              <Text strong>Mock URL</Text>
              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <Input
                  value={`${window.location.origin}${mockUrl}`}
                  readOnly
                  style={{ flex: 1, fontFamily: 'monospace' }}
                />
                <Button
                  icon={<CopyOutlined />}
                  onClick={handleCopyUrl}
                >
                  复制
                </Button>
              </div>
            </div>

            <div>
              <Text strong>示例请求</Text>
              <div style={{ marginTop: 8, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                <pre style={{ margin: 0 }}>
                  {`curl -X ${definition.method} "${window.location.origin}${mockUrl}"`}
                </pre>
              </div>
            </div>

            <Alert
              message="注意事项"
              description="Mock 接口仅在当前环境可用，请确保 Mock 功能已启用"
              type="warning"
              showIcon
            />
          </Space>
        </div>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <ApiOutlined />
          <Text>Mock 服务</Text>
        </Space>
      }
      extra={
        <Tag color="green">{definition.method}</Tag>
      }
    >
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />
    </Card>
  );
};

export default MockService;