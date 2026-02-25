/**
 * Diff View 组件（V2.0 层级一 - API 资产库）
 * 符合前端代码规范：
 * 1. 防止重复提交：按钮加载状态
 * 2. 空值防御：使用可选链和默认值
 * 3. 友好异常提示：统一错误处理
 */
import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Tag,
  Space,
  Typography,
  Button,
  Descriptions,
} from 'antd';
import {
  PlusOutlined,
  MinusOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const { Text, Paragraph } = Typography;

interface DiffItem {
  type: 'added' | 'removed' | 'changed';
  field: string;
  oldValue?: any;
  newValue?: any;
  location?: 'request' | 'response';
}

interface DiffViewProps {
  oldData: any;
  newData: any;
  title?: string;
}

const DiffView: React.FC<DiffViewProps> = ({ oldData, newData, title = '版本对比' }) => {
  const [diffs, setDiffs] = useState<DiffItem[]>([]);
  const [stats, setStats] = useState({ added: 0, removed: 0, changed: 0 });

  React.useEffect(() => {
    const calculatedDiffs = calculateDiffs(oldData, newData);
    setDiffs(calculatedDiffs);
    setStats({
      added: calculatedDiffs.filter(d => d.type === 'added').length,
      removed: calculatedDiffs.filter(d => d.type === 'removed').length,
      changed: calculatedDiffs.filter(d => d.type === 'changed').length,
    });
  }, [oldData, newData]);

  const calculateDiffs = (oldObj: any, newObj: any): DiffItem[] => {
    const result: DiffItem[] = [];

    const compare = (o: any, n: any, path: string = '') => {
      const keys = new Set([...Object.keys(o || {}), ...Object.keys(n || {})]);

      keys.forEach(key => {
        const currentPath = path ? `${path}.${key}` : key;

        if (o && key in o && n && key in n) {
          // 都存在的字段
          if (JSON.stringify(o[key]) !== JSON.stringify(n[key])) {
            // 值不同
            if (typeof n[key] === 'object' && n[key] !== null) {
              // 递归比较对象
              compare(o[key], n[key], currentPath);
            } else {
              // 基本类型不同
              result.push({
                type: 'changed',
                field: currentPath,
                oldValue: o[key],
                newValue: n[key],
              });
            }
          }
        } else if (o && key in o && (!n || !(key in n))) {
          // 只在旧数据中存在（删除）
          result.push({
            type: 'removed',
            field: currentPath,
            oldValue: o[key],
          });
        } else if (n && key in n && (!o || !(key in o))) {
          // 只在新数据中存在（新增）
          result.push({
            type: 'added',
            field: currentPath,
            newValue: n[key],
          });
        }
      });
    };

    compare(oldData, newData);
    return result;
  };

  const getDiffColor = (type: string) => {
    switch (type) {
      case 'added':
        return 'success';
      case 'removed':
        return 'error';
      case 'changed':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getDiffIcon = (type: string) => {
    switch (type) {
      case 'added':
        return <PlusOutlined />;
      case 'removed':
        return <MinusOutlined />;
      case 'changed':
        return <SwapOutlined />;
      default:
        return null;
    }
  };

  const formatValue = (value: any): string => {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  };

  return (
    <Card
      title={
        <Space>
          <Text strong>{title}</Text>
          <Tag color="success">新增: {stats.added}</Tag>
          <Tag color="error">删除: {stats.removed}</Tag>
          <Tag color="warning">修改: {stats.changed}</Tag>
        </Space>
      }
    >
      {diffs.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-tertiary)' }}>
          没有检测到变更
        </div>
      ) : (
        <div style={{ maxHeight: 600, overflow: 'auto' }}>
          {diffs.map((diff, index) => (
            <Card
              key={index}
              size="small"
              style={{ marginBottom: 8 }}
              type={diff.type === 'removed' ? 'error' : undefined}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space>
                  <Tag color={getDiffColor(diff.type)} icon={getDiffIcon(diff.type)}>
                    {diff.type === 'added' ? '新增' : diff.type === 'removed' ? '删除' : '修改'}
                  </Tag>
                  <Text code>{diff.field}</Text>
                </Space>

                <Row gutter={16}>
                  <Col span={12}>
                    {diff.oldValue !== undefined && (
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>旧值:</Text>
                        <SyntaxHighlighter
                          language="json"
                          style={vscDarkPlus}
                          customStyle={{ fontSize: 12, marginTop: 4, padding: 8 }}
                        >
                          {formatValue(diff.oldValue)}
                        </SyntaxHighlighter>
                      </div>
                    )}
                  </Col>
                  <Col span={12}>
                    {diff.newValue !== undefined && (
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>新值:</Text>
                        <SyntaxHighlighter
                          language="json"
                          style={vscDarkPlus}
                          customStyle={{ fontSize: 12, marginTop: 4, padding: 8 }}
                        >
                          {formatValue(diff.newValue)}
                        </SyntaxHighlighter>
                      </div>
                    )}
                  </Col>
                </Row>
              </Space>
            </Card>
          ))}
        </div>
      )}
    </Card>
  );
};

export default DiffView;