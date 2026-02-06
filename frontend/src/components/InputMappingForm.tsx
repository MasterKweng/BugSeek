/**
 * 参数映射表单组件
 * 符合前端代码规范
 */

import React, { useCallback } from 'react';
import { Button, Input, Select, Space, Table } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

import { InputMapping, MappingLocationEnum, MappingLocationLabels } from '../types/auth';

const { Option } = Select;

interface InputMappingFormProps {
  value?: InputMapping[];
  onChange?: (value: InputMapping[]) => void;
}

const InputMappingForm: React.FC<InputMappingFormProps> = React.memo(({ value = [], onChange }) => {
  const handleAdd = useCallback(() => {
    const newItem: InputMapping = {
      location: MappingLocationEnum.BODY,
      key: '',
      value: ''
    };
    onChange?.([...value, newItem]);
  }, [value, onChange]);

  const handleRemove = useCallback((index: number) => {
    const newValue = [...value];
    newValue.splice(index, 1);
    onChange?.(newValue);
  }, [value, onChange]);

  const handleUpdate = useCallback((index: number, field: keyof InputMapping, fieldValue: any) => {
    const newValue = [...value];
    newValue[index] = { ...newValue[index], [field]: fieldValue };
    onChange?.(newValue);
  }, [value, onChange]);

  const columns = [
    {
      title: '参数位置',
      dataIndex: 'location',
      width: 150,
      render: (location: MappingLocationEnum, record: InputMapping, index: number) => (
        <Select
          value={location}
          onChange={(val) => handleUpdate(index, 'location', val)}
          style={{ width: '100%' }}
        >
          {Object.entries(MappingLocationLabels).map(([value, label]) => (
            <Option key={value} value={value}>{label}</Option>
          ))}
        </Select>
      )
    },
    {
      title: '参数名',
      dataIndex: 'key',
      width: 200,
      render: (key: string, record: InputMapping, index: number) => (
        <Input
          value={key}
          onChange={(e) => handleUpdate(index, 'key', e.target.value)}
          placeholder="参数名"
        />
      )
    },
    {
      title: '参数值',
      dataIndex: 'value',
      render: (val: string, record: InputMapping, index: number) => (
        <Input
          value={val}
          onChange={(e) => handleUpdate(index, 'value', e.target.value)}
          placeholder="参数值"
        />
      )
    },
    {
      title: '操作',
      width: 80,
      render: (_: any, record: InputMapping, index: number) => (
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
          添加参数映射
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={value}
        rowKey={(record, index) => `mapping-${index}`}
        pagination={false}
        size="small"
      />
    </div>
  );
});

InputMappingForm.displayName = 'InputMappingForm';

export default InputMappingForm;