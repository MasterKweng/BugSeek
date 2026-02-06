/**
 * 提取规则表单组件
 * 符合前端代码规范
 */

import React, { useCallback } from 'react';
import { Button, Input, Select, Space, Table } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

import { ExtractRule, ExtractSourceEnum, ExtractSourceLabels } from '../types/auth';

const { Option } = Select;

interface ExtractRuleFormProps {
  value?: ExtractRule[];
  onChange?: (value: ExtractRule[]) => void;
}

const ExtractRuleForm: React.FC<ExtractRuleFormProps> = React.memo(({ value = [], onChange }) => {
  const handleAdd = useCallback(() => {
    const newItem: ExtractRule = {
      name: '',
      source: ExtractSourceEnum.BODY,
      expression: ''
    };
    onChange?.([...value, newItem]);
  }, [value, onChange]);

  const handleRemove = useCallback((index: number) => {
    const newValue = [...value];
    newValue.splice(index, 1);
    onChange?.(newValue);
  }, [value, onChange]);

  const handleUpdate = useCallback((index: number, field: keyof ExtractRule, fieldValue: any) => {
    const newValue = [...value];
    newValue[index] = { ...newValue[index], [field]: fieldValue };
    onChange?.(newValue);
  }, [value, onChange]);

  const columns = [
    {
      title: '变量名',
      dataIndex: 'name',
      width: 150,
      render: (name: string, record: ExtractRule, index: number) => (
        <Input
          value={name}
          onChange={(e) => handleUpdate(index, 'name', e.target.value)}
          placeholder="例如: ACCESS_TOKEN"
        />
      )
    },
    {
      title: '提取来源',
      dataIndex: 'source',
      width: 120,
      render: (source: ExtractSourceEnum, record: ExtractRule, index: number) => (
        <Select
          value={source}
          onChange={(val) => handleUpdate(index, 'source', val)}
          style={{ width: '100%' }}
        >
          {Object.entries(ExtractSourceLabels).map(([value, label]) => (
            <Option key={value} value={value}>{label}</Option>
          ))}
        </Select>
      )
    },
    {
      title: '提取表达式',
      dataIndex: 'expression',
      render: (expression: string, record: ExtractRule, index: number) => (
        <Input
          value={expression}
          onChange={(e) => handleUpdate(index, 'expression', e.target.value)}
          placeholder="例如: $.data.token"
        />
      )
    },
    {
      title: '操作',
      width: 80,
      render: (_: any, record: ExtractRule, index: number) => (
        <Button
          type="link"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleRemove(index)}
        />
      )
    }
  ];

  return (
    <div>
      <div style={{ marginBottom: '8px' }}>
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={handleAdd}
          block
        >
          添加提取规则
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={value}
        rowKey={(record, index) => `rule-${index}`}
        pagination={false}
        size="small"
      />
    </div>
  );
});

ExtractRuleForm.displayName = 'ExtractRuleForm';

export default ExtractRuleForm;