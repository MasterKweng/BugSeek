import React from 'react';
import { Card, Table, Button, Space } from 'antd';

const Scenarios: React.FC = () => {
  const columns = [
    {
      title: '场景名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '接口数量',
      dataIndex: 'endpointCount',
      key: 'endpointCount',
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
          <Button type="link" size="small">查看依赖图</Button>
          <Button type="link" size="small">生成脚本</Button>
          <Button type="link" size="small">执行</Button>
          <Button type="link" size="small" danger>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="场景组装"
        extra={<Button type="primary">分析依赖</Button>}
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

export default Scenarios;