/**
 * 参数映射编辑器组件
 * 符合前端代码规范
 */

import React from 'react';
import { Form, Select, Input, Button, Space, Card } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { MappingLocationEnum, MappingLocationLabels } from '../types/auth';

const { Option } = Select;

interface InputMappingFormProps {
  field: any;
  index: number;
  onRemove: () => void;
}

/**
 * 参数映射编辑器
 * 用于配置登录接口的参数映射
 */
const InputMappingForm: React.FC<InputMappingFormProps> = ({ field, index, onRemove }) => {
  return (
    <Card 
      size="small" 
      style={{ marginBottom: 8 }}
      extra={
        <Button 
          type="text" 
          danger 
          icon={<DeleteOutlined />} 
          onClick={onRemove}
        >
          删除
        </Button>
      }
    >
      <Form.Item
        {...field}
        name={[field.name, 'location']}
        label={`参数位置 ${index + 1}`}
        rules={[{ required: true, message: '请选择参数位置' }]}
      >
        <Select placeholder="请选择参数位置">
          {Object.entries(MappingLocationLabels).map(([value, label]) => (
            <Option key={value} value={value}>{label}</Option>
          ))}
        </Select>
      </Form.Item>
      
      <Form.Item
        {...field}
        name={[field.name, 'key']}
        label="参数名"
        rules={[{ required: true, message: '请输入参数名' }]}
      >
        <Input placeholder="如 username、password" />
      </Form.Item>
      
      <Form.Item
        {...field}
        name={[field.name, 'value']}
        label="参数值"
        rules={[{ required: true, message: '请输入参数值' }]}
      >
        <Input placeholder="支持环境变量，如 {{auth_username}}" />
      </Form.Item>
    </Card>
  );
};

export default InputMappingForm;