import React from 'react';
import { Card, Table, Button, Space, Tag } from 'antd';

const TestSuites: React.FC = () => {
  const columns = [
    {
      title: '套件名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '用例数量',
      dataIndex: 'testCaseCount',
      key: 'testCaseCount',
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[]) => (
        <>
          {tags?.map((tag: string) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </>
      ),
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space size="small">
          <Button type="link" size="small">查看</Button>
          <Button type="link" size="small">执行</Button>
          <Button type="link" size="small">编辑</Button>
          <Button type="link" size="small" danger>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="测试套件"
        extra={<Button type="primary">创建套件</Button>}
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

export default TestSuites;