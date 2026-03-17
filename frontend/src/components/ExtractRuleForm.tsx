/**
 * 提取规则编辑器组件
 * 符合前端代码规范
 */

import React from 'react';
import { Form, Select, Input, Button, Card } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { ExtractSourceLabels } from '../types/auth';

const { Option } = Select;

interface ExtractRuleFormProps {
  field: any;
  index: number;
  onRemove: () => void;
}

/**
 * 提取规则编辑器
 * 用于配置从登录响应中提取变量的规则
 */
const ExtractRuleForm: React.FC<ExtractRuleFormProps> = ({ field, index, onRemove }) => {
  return (
    <Card 
      key={field.key}
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
        name={[field.name, 'name']}
        label={`变量名 ${index + 1}`}
        rules={[
          { required: true, message: '请输入变量名' },
          { pattern: /^[A-Z_][A-Z0-9_]*$/, message: '变量名必须是有效的标识符' }
        ]}
      >
        <Input placeholder="如 ACCESS_TOKEN、CSRF_TOKEN" />
      </Form.Item>
      
      <Form.Item
        {...field}
        name={[field.name, 'source']}
        label="提取来源"
        rules={[{ required: true, message: '请选择提取来源' }]}
      >
        <Select placeholder="请选择提取来源">
          {Object.entries(ExtractSourceLabels).map(([value, label]) => (
            <Option key={value} value={value}>{label}</Option>
          ))}
        </Select>
      </Form.Item>
      
      <Form.Item
        {...field}
        name={[field.name, 'expression']}
        label="提取表达式"
        rules={[{ required: true, message: '请输入提取表达式' }]}
      >
        <Input.TextArea 
          rows={2} 
          placeholder="如 $.data.token（JSONPath）或 Set-Cookie（Header 名）"
        />
      </Form.Item>
    </Card>
  );
};

export default ExtractRuleForm;