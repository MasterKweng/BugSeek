import React from 'react';
import { Card, Table, Button, Space, Tag, Badge } from 'antd';

const Executions: React.FC = () => {
  const columns = [
    {
      title: '执行 ID',
      dataIndex: 'executionId',
      key: 'executionId',
    },
    {
      title: '执行类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => {
        const colorMap: Record<string, string> = {
          single: 'blue',
          scenario: 'green',
          suite: 'orange',
        };
        return <Tag color={colorMap[type] || 'default'}>{type}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          running: { color: 'processing', text: '运行中' },
          completed: { color: 'success', text: '已完成' },
          failed: { color: 'error', text: '失败' },
        };
        const config = statusMap[status] || { color: 'default', text: status };
        return <Badge status={config.color as any} text={config.text} />;
      },
    },
    {
      title: '通过/失败',
      dataIndex: 'result',
      key: 'result',
      render: (result: { passed: number; failed: number; total: number }) => (
        <span>{result.passed}/{result.total}</span>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      render: (duration: number) => `${duration}s`,
    },
    {
      title: '开始时间',
      dataIndex: 'startedAt',
      key: 'startedAt',
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space size="small">
          <Button type="link" size="small">查看详情</Button>
          <Button type="link" size="small">查看报告</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card title="执行记录">
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

export default Executions;