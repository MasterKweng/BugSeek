import React from 'react';
import { Card, Table, Button, Space, Tag, Select } from 'antd';

const Reports: React.FC = () => {
  const columns = [
    {
      title: '报告 ID',
      dataIndex: 'reportId',
      key: 'reportId',
    },
    {
      title: '执行 ID',
      dataIndex: 'executionId',
      key: 'executionId',
    },
    {
      title: '格式',
      dataIndex: 'format',
      key: 'format',
      render: (format: string) => {
        const colorMap: Record<string, string> = {
          json: 'blue',
          junit: 'green',
          html: 'orange',
          allure: 'purple',
        };
        return <Tag color={colorMap[format] || 'default'}>{format}</Tag>;
      },
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
          <Button type="link" size="small">下载</Button>
          <Button type="link" size="small">预览</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="测试报告"
        extra={
          <Space>
            <Select placeholder="选择格式" style={{ width: 120 }}>
              <Select.Option value="json">JSON</Select.Option>
              <Select.Option value="junit">JUnit</Select.Option>
              <Select.Option value="html">HTML</Select.Option>
              <Select.Option value="allure">Allure</Select.Option>
            </Select>
            <Button type="primary">生成报告</Button>
          </Space>
        }
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

export default Reports;