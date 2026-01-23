import React from 'react';
import { Card, Table, Button, Space, Switch } from 'antd';

const Mock: React.FC = () => {
  const columns = [
    {
      title: 'Mock 名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Mock URL',
      dataIndex: 'mockUrl',
      key: 'mockUrl',
    },
    {
      title: '关联接口',
      dataIndex: 'endpoint',
      key: 'endpoint',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: boolean) => (
        <Switch checked={status} checkedChildren="运行中" unCheckedChildren="已停止" />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space size="small">
          <Button type="link" size="small">配置规则</Button>
          <Button type="link" size="small">查看日志</Button>
          <Button type="link" size="small" danger>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="Mock 服务"
        extra={<Button type="primary">创建 Mock</Button>}
      >
        <Table
          columns={columns}
          dataSource={[]}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
};

export default Mock;