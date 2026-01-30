/**
 * 模块详情面板组件
 * 按照方案一B实现：点击左侧模块的详细信息，右侧动态展示对应内容
 */
import React, { useEffect, useState } from 'react';
import {
  Card,
  Table,
  Tag,
  Space,
  Empty,
  Button,
  Progress
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import api from '../../../services/api';

interface ModuleDetailPanelProps {
  moduleId: number | null;
  projectId: number | undefined;
  detailType: 'dependencies' | 'input' | 'output' | null;
}

interface ModuleDependency {
  id: number;
  source_group_id: number;
  source_group_name: string;
  target_group_id: number;
  target_group_name: string;
  dependency_strength: number;
}

interface ApiEndpoint {
  id: number;
  method: string;
  path: string;
  summary: string;
  tags: string[];
}

const ModuleDetailPanel: React.FC<ModuleDetailPanelProps> = ({
  moduleId,
  projectId,
  detailType
}) => {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  // 根据选中的详情类型加载数据
  useEffect(() => {
    if (moduleId && projectId && detailType) {
      loadDetailData(moduleId, projectId, detailType);
    }
  }, [moduleId, projectId, detailType]);

  const loadDetailData = async (mid: number, pid: number, type: string) => {
    setLoading(true);
    try {
      let response;
      switch (type) {
        case 'dependencies':
          response = await api.get(`/api-integration/modules/dependencies?project_id=${pid}`);
          setData(response.data.dependencies?.filter((d: any) => d.target_group_id === mid) || []);
          break;
        case 'input':
          response = await api.get(`/api-integration/modules/${mid}/status`);
          setData(response.data.input_endpoints || []);
          break;
        case 'output':
          response = await api.get(`/api-integration/modules/${mid}/status`);
          setData(response.data.output_endpoints || []);
          break;
      }
    } catch (error) {
      console.error('加载详情失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 依赖关系表格列
  const dependencyColumns: ColumnsType<ModuleDependency> = [
    {
      title: '来源模块',
      dataIndex: 'source_group_name',
      key: 'source_group_name',
      ellipsis: true,
    },
    {
      title: '目标模块',
      dataIndex: 'target_group_name',
      key: 'target_group_name',
      ellipsis: true,
    },
    {
      title: '依赖强度',
      dataIndex: 'dependency_strength',
      key: 'dependency_strength',
      width: 150,
      render: (value: number) => (
        <Progress 
          percent={value * 100} 
          size="small" 
          format={(percent) => `${percent?.toFixed(0)}%`}
        />
      ),
    },
  ];

  // 接口表格列
  const endpointColumns: ColumnsType<ApiEndpoint> = [
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      width: 80,
      render: (method: string) => {
        const colors: Record<string, string> = {
          GET: 'green',
          POST: 'blue',
          PUT: 'orange',
          DELETE: 'red',
          PATCH: 'purple',
        };
        return <Tag color={colors[method] || 'default'}>{method}</Tag>;
      },
    },
    {
      title: '路径',
      dataIndex: 'path',
      key: 'path',
      ellipsis: true,
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: true,
    },
  ];

  if (!moduleId) {
    return (
      <Card>
        <Empty description="请选择一个模块查看详情" />
      </Card>
    );
  }

  const getTitle = () => {
    switch (detailType) {
      case 'dependencies':
        return (
          <Space>
            <span>🔗 依赖关系</span>
            <Tag color="blue">{data.length} 个</Tag>
          </Space>
        );
      case 'input':
        return (
          <Space>
            <span>📥 输入接口</span>
            <Tag color="green">{data.length} 个</Tag>
          </Space>
        );
      case 'output':
        return (
          <Space>
            <span>📤 输出接口</span>
            <Tag color="orange">{data.length} 个</Tag>
          </Space>
        );
      default:
        return '📋 模块详情';
    }
  };

  const getColumns = () => {
    switch (detailType) {
      case 'dependencies':
        return dependencyColumns;
      case 'input':
      case 'output':
        return endpointColumns;
      default:
        return [];
    }
  };

  return (
    <Card 
      title={getTitle()}
      loading={loading}
    >
      {detailType ? (
        <Table
          columns={getColumns()}
          dataSource={data}
          rowKey="id"
          size="small"
          pagination={false}
          scroll={{ y: 500 }}
        />
      ) : (
        <Empty description="请点击左侧模块的详细信息查看对应内容" />
      )}
    </Card>
  );
};

export default ModuleDetailPanel;