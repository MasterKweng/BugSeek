/**
 * 测试登录抽屉组件
 * 符合前端代码规范
 */

import React, { useState } from 'react';
import { Drawer, Button, Space, Alert, Spin, Card, Empty, Descriptions } from 'antd';
import { PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';

import { testAcquisition } from '../services/auth';
import type { TestAcquisitionRequest, TestAcquisitionResponse } from '../types/auth';

interface TestLoginDrawerProps {
  visible: boolean;
  onClose: () => void;
  projectId: number;
}

const TestLoginDrawer: React.FC<TestLoginDrawerProps> = ({ visible, onClose, projectId }) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestAcquisitionResponse | null>(null);

  const handleTest = async () => {
    setLoading(true);
    setResult(null);

    try {
      const request: TestAcquisitionRequest = {};
      const response = await testAcquisition(projectId, request);

      if (response.code === 0) {
        setResult(response.data);
      } else {
        setResult({
          success: false,
          message: response.message || '测试失败',
          extracted_vars: {},
          error: response.message
        });
      }
    } catch (error: any) {
      setResult({
        success: false,
        message: '测试异常',
        extracted_vars: {},
        error: error.message || '未知错误'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setResult(null);
    onClose();
  };

  return (
    <Drawer
      title="测试登录"
      placement="right"
      width={600}
      onClose={handleClose}
      open={visible}
      footer={
        <Space>
          <Button onClick={handleClose}>关闭</Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleTest}
            loading={loading}
          >
            开始测试
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Alert
          message="测试说明"
          description="点击开始测试后，系统将使用当前配置执行登录请求，并提取凭证变量。测试结果将显示在下方。"
          type="info"
          showIcon
        />

        {loading && (
          <Card>
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <Spin size="large" tip="正在测试登录..." />
            </div>
          </Card>
        )}

        {result && !loading && (
          <Card
            title={
              <Space>
                {result.success ? (
                  <CheckCircleOutlined style={{ color: '#52c41a' }} />
                ) : (
                  <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                )}
                <span>{result.success ? '测试成功' : '测试失败'}</span>
              </Space>
            }
          >
            <Descriptions column={1} bordered>
              <Descriptions.Item label="状态">
                {result.success ? (
                  <span style={{ color: '#52c41a' }}>成功</span>
                ) : (
                  <span style={{ color: '#ff4d4f' }}>失败</span>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="消息">
                {result.message}
              </Descriptions.Item>
              {result.error && (
                <Descriptions.Item label="错误">
                  <span style={{ color: '#ff4d4f' }}>{result.error}</span>
                </Descriptions.Item>
              )}
            </Descriptions>

            {result.extracted_vars && Object.keys(result.extracted_vars).length > 0 && (
              <div style={{ marginTop: '16px' }}>
                <h4>提取的变量：</h4>
                <Card size="small">
                  {Object.entries(result.extracted_vars).map(([key, value]) => (
                    <div key={key}>
                      <strong>{key}:</strong> {String(value)}
                    </div>
                  ))}
                </Card>
              </div>
            )}

            {result.response_data && (
              <div style={{ marginTop: '16px' }}>
                <h4>响应数据：</h4>
                <Card size="small">
                  <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {result.response_data}
                  </pre>
                </Card>
              </div>
            )}
          </Card>
        )}

        {!result && !loading && (
          <Card>
            <Empty description="点击开始测试按钮进行测试" />
          </Card>
        )}
      </Space>
    </Drawer>
  );
};

export default TestLoginDrawer;
