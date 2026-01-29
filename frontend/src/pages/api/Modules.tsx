/**
 * 模块依赖分析页面
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  message,
  Modal,
  Descriptions,
  Progress,
  Tooltip,
  Row,
  Col
} from 'antd';
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  EyeOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectStore } from '@/store/project';
import { api } from '@/services/api';
import DependencyGraph from '@/components/DependencyGraph';

interface Module {
  id: number;
  name: string;
  description: string;
  analysis_status: string;
  endpoint_count: number;
}

interface ModuleDetail {
  group_id: number;
  group_name: string;
  status: string;
  dependency_count: number;
  internal_chains: number[][];
  input_endpoints: number[];
  output_endpoints: number[];
}

interface ModuleDependency {
  id: number;
  source_group_id: number;
  source_group_name: string;
  target_group_id: number;
  target_group_name: string;
  dependency_strength: number;
}

const Modules: React.FC = () => {
  const navigate = useNavigate();
  const { currentProject } = projectStore();

  const [modules, setModules] = useState<Module[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);
  const [moduleDetailVisible, setModuleDetailVisible] = useState(false);
  const [moduleDetail, setModuleDetail] = useState<ModuleDetail | null>(null);
  const [dependencies, setDependencies] = useState<ModuleDependency[]>([]);
  const [dependencyGraphVisible, setDependencyGraphVisible] = useState(false);

  // 加载模块列表
  const loadModules = async () => {
    if (!currentProject?.id) {
      message.warning('请先选择项目');
      return;
    }

    setLoading(true);
    try {
      const response = await api.get(`/api-integration/modules?project_id=${currentProject.id}`);
      if (response.data.code === 0) {
        setModules(response.data.data.modules || []);
      } else {
        message.error(response.data.message || '加载模块列表失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '加载模块列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 分析单个模块
  const analyzeModule = async (moduleId: number) => {
    if (!currentProject?.id) return;

    try {
      await api.post(`/api-integration/modules/${moduleId}/analyze`, {
        project_id: currentProject.id
      });
      message.success('模块分析任务已创建');
      loadModules();
    } catch (error: any) {
      message.error(error.response?.data?.message || '创建模块分析任务失败');
    }
  };

  // 分析所有模块
  const analyzeAllModules = async () => {
    if (!currentProject?.id) return;

    setAnalyzing(true);
    try {
      const response = await api.post('/api-integration/modules/analyze-all', {
        project_id: currentProject.id
      });
      if (response.data.code === 0) {
        message.success('所有模块分析任务已创建');
        loadModules();
      } else {
        message.error(response.data.message || '创建分析任务失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '创建分析任务失败');
    } finally {
      setAnalyzing(false);
    }
  };

  // 查看模块详情
  const viewModuleDetail = async (module: Module) => {
    setSelectedModule(module);
    setModuleDetailVisible(true);

    try {
      const response = await api.get(`/api-integration/modules/${module.id}/status`);
      if (response.data.code === 0) {
        setModuleDetail(response.data.data);
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '加载模块详情失败');
    }
  };

  // 分析模块间依赖
  const analyzeCrossModuleDependencies = async () => {
    if (!currentProject?.id) return;

    try {
      const response = await api.post('/api-integration/modules/analyze-cross-module', {
        project_id: currentProject.id
      });
      if (response.data.code === 0) {
        message.success('模块间依赖分析完成');
        loadDependencies();
      } else {
        message.error(response.data.message || '模块间依赖分析失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '模块间依赖分析失败');
    }
  };

  // 加载模块间依赖
  const loadDependencies = async () => {
    if (!currentProject?.id) return;

    try {
      const response = await api.get(`/api-integration/modules/dependencies?project_id=${currentProject.id}`);
      if (response.data.code === 0) {
        setDependencies(response.data.data.dependencies || []);
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '加载模块间依赖失败');
    }
  };

  // 获取状态标签
  const getStatusTag = (status: string) => {
    switch (status) {
      case 'completed':
        return <Tag icon={<CheckCircleOutlined />} color="success">已完成</Tag>;
      case 'analyzing':
        return <Tag icon={<ClockCircleOutlined />} color="processing">分析中</Tag>;
      case 'pending':
        return <Tag icon={<ClockCircleOutlined />} color="default">待分析</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  useEffect(() => {
    loadModules();
    loadDependencies();
  }, [currentProject?.id]);

  const columns = [
    {
      title: '模块名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Module) => (
        <Space>
          <span>{text}</span>
          {getStatusTag(record.analysis_status)}
        </Space>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '接口数量',
      dataIndex: 'endpoint_count',
      key: 'endpoint_count',
      width: 100
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: Module) => (
        <Space size="small">
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => viewModuleDetail(record)}
          >
            详情
          </Button>
          {record.analysis_status !== 'completed' && (
            <Button
              type="link"
              icon={<PlayCircleOutlined />}
              onClick={() => analyzeModule(record.id)}
            >
              分析
            </Button>
          )}
        </Space>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title="模块依赖分析"
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadModules}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={analyzeAllModules}
              loading={analyzing}
            >
              分析所有模块
            </Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={analyzeCrossModuleDependencies}
            >
              分析模块间依赖
            </Button>
            <Button
              onClick={() => setDependencyGraphVisible(true)}
              disabled={dependencies.length === 0}
            >
              查看依赖图
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={modules}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个模块`
          }}
        />
      </Card>

      {/* 模块详情弹窗 */}
      <Modal
        title={`模块详情 - ${selectedModule?.name}`}
        open={moduleDetailVisible}
        onCancel={() => setModuleDetailVisible(false)}
        footer={null}
        width={800}
      >
        {moduleDetail && (
          <Descriptions bordered column={2}>
            <Descriptions.Item label="模块名称">{moduleDetail.group_name}</Descriptions.Item>
            <Descriptions.Item label="状态">{getStatusTag(moduleDetail.status)}</Descriptions.Item>
            <Descriptions.Item label="依赖关系数量">{moduleDetail.dependency_count}</Descriptions.Item>
            <Descriptions.Item label="输入接口数">{moduleDetail.input_endpoints.length}</Descriptions.Item>
            <Descriptions.Item label="输出接口数">{moduleDetail.output_endpoints.length}</Descriptions.Item>
            <Descriptions.Item label="内部链路数">{moduleDetail.internal_chains.length}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      {/* 模块依赖图弹窗 */}
      <Modal
        title="模块依赖关系图"
        open={dependencyGraphVisible}
        onCancel={() => setDependencyGraphVisible(false)}
        footer={null}
        width={1200}
      >
        <DependencyGraph dependencies={dependencies} />
      </Modal>
    </div>
  );
};

export default Modules;