import React from 'react';
import { Card, Button, Space, Descriptions, Steps, Tag } from 'antd';
import { ArrowLeftOutlined, EditOutlined, PlayCircleOutlined, SettingOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';

const { Step } = Steps;

const ScenarioDetail: React.FC = () => {
  const navigate = useNavigate();
  const { scenarioId } = useParams();

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/scenario/list')}>
          返回列表
        </Button>
        <Button icon={<SettingOutlined />} onClick={() => navigate(`/scenario/${scenarioId}/design`)}>
          编辑场景
        </Button>
        <Button type="primary" icon={<PlayCircleOutlined />}>
          执行场景
        </Button>
      </Space>

      <Card title="场景详情">
        <Descriptions bordered column={2}>
          <Descriptions.Item label="场景ID">{scenarioId}</Descriptions.Item>
          <Descriptions.Item label="场景名称">电商购买链路</Descriptions.Item>
          <Descriptions.Item label="场景类型">意图生成</Descriptions.Item>
          <Descriptions.Item label="状态">活跃</Descriptions.Item>
          <Descriptions.Item label="节点数量">5</Descriptions.Item>
          <Descriptions.Item label="创建时间">2024-01-15 10:30:00</Descriptions.Item>
        </Descriptions>

        <div style={{ marginTop: 24 }}>
          <h3>场景节点</h3>
          <Steps
            direction="vertical"
            current={-1}
            items={[
              {
                title: '创建用户',
                description: 'POST /api/users',
              },
              {
                title: '登录',
                description: 'POST /api/auth/login',
              },
              {
                title: '浏览商品',
                description: 'GET /api/products',
              },
              {
                title: '下单',
                description: 'POST /api/orders',
              },
              {
                title: '支付',
                description: 'POST /api/payments',
              },
            ]}
          />
        </div>
      </Card>
    </div>
  );
};

export default ScenarioDetail;