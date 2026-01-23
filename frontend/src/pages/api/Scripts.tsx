import React from 'react';
import { Card, Table, Button, Space, Tag } from 'antd';

const Scripts: React.FC = () => {
  const columns = [
    {
      title: '脚本名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '测试类型',
      dataIndex: 'testType',
      key: 'testType',
      render: (type: string) => {
        const colorMap: Record<string, string> = {
          positive: 'green',
          negative: 'red',
          boundary: 'orange',
          exception: 'purple',
        };
        return <Tag color={colorMap[type] || 'default'}>{type}</Tag>;
      },
    },
    {
      title: '关联接口',
      dataIndex: 'endpoint',
      key: 'endpoint',
    },
    {
      title: '生成时间',
      dataIndex: 'generatedAt',
      key: 'generatedAt',
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space size="small">
          <Button type="link" size="small">预览</Button>
          <Button type="link" size="small">编辑</Button>
          <Button type="link" size="small">执行</Button>
          <Button type="link" size="small" danger>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="测试脚本"
        extra={<Button type="primary">生成脚本</Button>}
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

export default Scripts;