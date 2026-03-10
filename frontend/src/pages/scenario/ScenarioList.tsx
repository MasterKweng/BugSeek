import React from 'react';
import { Card, Table, Button, Space, Tag } from 'antd';
import { PlusOutlined, PlayCircleOutlined } from '@ant-design/icons';

const ScenarioList: React.FC = () => {
  const columns = [
    {
      title: '场景名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'scenario_type',
      key: 'scenario_type',
      render: (type: string) => (
        <Tag color={type === 'intent' ? 'blue' : 'green'}>
          {type === 'intent' ? '意图生成' : '手动创建'}
        </Tag>
      ),
    },
    {
      title: '节点数量',
      dataIndex: 'node_count',
      key: 'node_count',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'success' : 'default'}>
          {status === 'active' ? '活跃' : '草稿'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: any) => (
        <Space size="small">
          <Button type="link" size="small">
            查看
          </Button>
          <Button type="link" size="small">
            编辑
          </Button>
          <Button 
            type="link" 
            size="small" 
            icon={<PlayCircleOutlined />}
          >
            执行
          </Button>
        </Space>
      ),
    },
  ];

  const data = [
    {
      key: '1',
      name: '电商购买链路',
      scenario_type: 'intent',
      node_count: 5,
      status: 'active',
      created_at: '2024-01-15 10:30:00',
    },
    {
      key: '2',
      name: '用户注册流程',
      scenario_type: 'manual',
      node_count: 3,
      status: 'active',
      created_at: '2024-01-14 15:20:00',
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="场景管理"
        extra={
          <Space>
            <Button type="primary" icon={<PlusOutlined />}>
              创建场景
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={data}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
        />
      </Card>
    </div>
  );
};

export default ScenarioList;