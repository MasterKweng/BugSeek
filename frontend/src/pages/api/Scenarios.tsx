/**
 * 场景组装页面 - 整合模块分析和跨模块组合功能
 */
import React, { useEffect, useState } from 'react';
import {
  Card,
  Tabs,
  Table,
  Button,
  Space,
  Modal,
  message,
  Tag,
  Progress,
  Descriptions,
  Form,
  Input,
  Select,
  Steps,
  Alert,
  Empty,
  Tooltip
} from 'antd';
import { Row, Col } from 'antd';
import { LinkOutlined, ArrowDownOutlined, ArrowUpOutlined } from '@ant-design/icons';
import ModuleDetailPanel from './components/ModuleDetailPanel';

import {
  PlusOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  NodeIndexOutlined,
  EditOutlined,
  EyeOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ArrowRightOutlined
} from '@ant-design/icons';
import { useProjectStore } from '../../store/project';
import api from '../../services/api';
import DependencyGraph from '../../components/DependencyGraph';

const { TabPane } = Tabs;
const { Step } = Steps;
const { Option } = Select;
const { TextArea } = Input;

interface Scenario {
  id: number;
  name: string;
  description: string;
  scenario_type: string;
  category: string;
  endpoint_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

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
  endpoint_mappings: any;
}

interface ModuleChain {
  id: number;
  name: string;
  description: string;
  group_ids: number[];
  group_names: string[];
  endpoint_count: number;
  group_count: number;
  created_at: string;
}

const Scenarios: React.FC = () => {
  // 模块详情相关状态
  const [selectedModuleId, setSelectedModuleId] = useState<number | null>(null);
  const [selectedDetailType, setSelectedDetailType] = useState<'dependencies' | 'input' | 'output' | null>(null);

  // 处理显示依赖关系
  const handleShowDependencies = (moduleId: number) => {
    setSelectedModuleId(moduleId);
    setSelectedDetailType('dependencies');
  };

  // 处理显示输入接口
  const handleShowInputEndpoints = (moduleId: number) => {
    setSelectedModuleId(moduleId);
    setSelectedDetailType('input');
  };

  // 处理显示输出接口
  const handleShowOutputEndpoints = (moduleId: number) => {
    setSelectedModuleId(moduleId);
    setSelectedDetailType('output');
  };

  const { currentProject } = useProjectStore();
  const [activeTab, setActiveTab] = useState('modules');

  // 场景列表相关状态
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzeModalVisible, setAnalyzeModalVisible] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState(0);
  const [analyzeResult, setAnalyzeResult] = useState<any>(null);
  const [graphModalVisible, setGraphModalVisible] = useState(false);
  const [graphData, setGraphData] = useState<any>(null);
  const [generateModalVisible, setGenerateModalVisible] = useState(false);
  const [selectedChain, setSelectedChain] = useState<number[]>([]);
  const [scenarioName, setScenarioName] = useState('');
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [currentScenario, setCurrentScenario] = useState<Scenario | null>(null);
  const [executeModalVisible, setExecuteModalVisible] = useState(false);
  const [environments, setEnvironments] = useState<any[]>([]);
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState<number | null>(null);
  const [executionResult, setExecutionResult] = useState<any>(null);

  // 模块分析相关状态
  const [modules, setModules] = useState<Module[]>([]);
  const [moduleDetailVisible, setModuleDetailVisible] = useState(false);
  const [moduleDetail, setModuleDetail] = useState<ModuleDetail | null>(null);
  const [dependencies, setDependencies] = useState<ModuleDependency[]>([]);
  const [dependencyGraphVisible, setDependencyGraphVisible] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [loadingModules, setLoadingModules] = useState(false);
  const [analyzingCrossModule, setAnalyzingCrossModule] = useState(false);
  const [selectedModuleIds, setSelectedModuleIds] = useState<number[]>([]);
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(null);
  const [taskProgress, setTaskProgress] = useState<any>(null);

  // 跨模块组合相关状态
  const [moduleChains, setModuleChains] = useState<ModuleChain[]>([]);
  const [composeVisible, setComposeVisible] = useState(false);
  const [chainDetailVisible, setChainDetailVisible] = useState(false);
  const [selectedChainDetail, setSelectedChainDetail] = useState<ModuleChain | null>(null);
  const [composing, setComposing] = useState(false);
  const [composeForm] = Form.useForm();

  // ==================== 场景列表 ====================

  const scenarioColumns = [
    {
      title: '场景名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      render: (category: string) => category || '-',
    },
    {
      title: '接口数量',
      dataIndex: 'endpoint_count',
      key: 'endpoint_count',
      render: (count: number) => <Tag color="blue">{count}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'default'}>
          {status === 'active' ? '活跃' : '已归档'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Scenario) => (
        <Space size="small">
          <Button type="link" size="small" icon={<NodeIndexOutlined />} onClick={() => handleViewGraph(record.id)}>
            依赖图
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditScenario(record.id)}>
            编辑
          </Button>
          <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleExecuteScenario(record.id)}>
            执行
          </Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteScenario(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const loadScenarios = async () => {
    if (!currentProject) {
      message.warning('请先选择项目');
      return;
    }

    setLoading(true);
    try {
      const response: any = await api.get(`/api-integration/scenarios?project_id=${currentProject.id}`);
      setScenarios(response.data.scenarios || []);
    } catch (error: any) {
      message.error(error.message || '加载场景列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeDependencies = async () => {
    if (!currentProject) {
      message.warning('请先选择项目');
      return;
    }

    setAnalyzeModalVisible(true);
    setAnalyzeProgress(0);
    setAnalyzeResult(null);

    try {
      const response: any = await api.post('/api-integration/scenarios/analyze', {
        project_id: currentProject.id,
        version_id: currentProject.currentVersion?.id || null,
      });

      const taskId = response.data.task_id;
      message.info('依赖分析任务已创建，正在后台执行...');

      const pollInterval = setInterval(async () => {
        try {
          const progressResponse: any = await api.get(`/api-integration/scenarios/analyze/progress/${taskId}`);
          const progressData = progressResponse.data;
          setAnalyzeProgress(progressData.progress);

          if (progressData.status === 'completed') {
            clearInterval(pollInterval);
            setAnalyzeProgress(100);
            setAnalyzeResult(progressData.result);
            message.success('依赖分析完成');
          } else if (progressData.status === 'failed') {
            clearInterval(pollInterval);
            message.error(`依赖分析失败: ${progressData.error_message}`);
            setAnalyzeModalVisible(false);
          }
        } catch (error: any) {
          clearInterval(pollInterval);
          message.error(error.message || '查询任务进度失败');
          setAnalyzeModalVisible(false);
        }
      }, 1000);

    } catch (error: any) {
      message.error(error.message || '依赖分析失败');
      setAnalyzeModalVisible(false);
    }
  };

  const handleGenerateScenario = async () => {
    if (!currentProject) {
      message.warning('请先选择项目');
      return;
    }

    if (!scenarioName.trim()) {
      message.warning('请输入场景名称');
      return;
    }

    if (selectedChain.length < 2) {
      message.warning('请选择至少2个接口的业务链路');
      return;
    }

    try {
      await api.post('/api-integration/scenarios/generate', {
        project_id: currentProject.id,
        chain: selectedChain,
        name: scenarioName,
        description: '自动生成的业务链路测试场景',
      });

      message.success('场景生成成功');
      setGenerateModalVisible(false);
      setScenarioName('');
      setSelectedChain([]);
      loadScenarios();
    } catch (error: any) {
      message.error(error.message || '场景生成失败');
    }
  };

  const handleViewGraph = async (scenarioId: number) => {
    try {
      const response: any = await api.get(`/api-integration/scenarios/${scenarioId}/graph`);
      setGraphData(response.data);
      setGraphModalVisible(true);
    } catch (error: any) {
      message.error(error.message || '获取依赖图失败');
    }
  };

  const handleExecuteScenario = async (scenarioId: number) => {
    if (!currentProject) {
      message.warning('请先选择项目');
      return;
    }

    try {
      const response: any = await api.get(`/environments?project_id=${currentProject.id}`);
      setEnvironments(response.data.environments || []);
      
      if (response.data.environments && response.data.environments.length > 0) {
        setSelectedEnvironmentId(response.data.environments[0].id);
      }
      
      setCurrentScenario(scenarios.find(s => s.id === scenarioId) || null);
      setExecutionResult(null);
      setExecuteModalVisible(true);
    } catch (error: any) {
      message.error(error.message || '加载环境列表失败');
    }
  };

  const handleExecuteWithEnvironment = async () => {
    if (!selectedEnvironmentId) {
      message.warning('请选择测试环境');
      return;
    }

    if (!currentScenario) {
      message.warning('场景信息不存在');
      return;
    }

    try {
      const response: any = await api.post('/api-integration/scenarios/execute', {
        scenario_id: currentScenario.id,
        environment_id: selectedEnvironmentId,
      });

      setExecutionResult(response.data);
      message.success('场景执行完成');
    } catch (error: any) {
      message.error(error.message || '场景执行失败');
    }
  };

  const handleEditScenario = async (scenarioId: number) => {
    try {
      const response: any = await api.get(`/api-integration/scenarios/${scenarioId}`);
      setCurrentScenario(response.data);
      setEditModalVisible(true);
    } catch (error: any) {
      message.error(error.message || '获取场景详情失败');
    }
  };

  const handleSaveScenario = async () => {
    if (!currentScenario) {
      message.warning('场景信息不存在');
      return;
    }

    try {
      await api.put(`/api-integration/scenarios/${currentScenario.id}`, {
        name: currentScenario.name,
        description: currentScenario.description,
        timeout: currentScenario.timeout,
        retry_count: currentScenario.retry_count,
        continue_on_failure: currentScenario.continue_on_failure,
      });

      message.success('场景保存成功');
      setEditModalVisible(false);
      loadScenarios();
    } catch (error: any) {
      message.error(error.message || '场景保存失败');
    }
  };

  const handleDeleteScenario = async (scenarioId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个场景吗？',
      onOk: async () => {
        try {
          await api.delete(`/api-integration/scenarios/${scenarioId}`);
          message.success('场景删除成功');
          loadScenarios();
        } catch (error: any) {
          message.error(error.message || '场景删除失败');
        }
      },
    });
  };

  // ==================== 模块分析 ====================

  const loadModules = async () => {
    if (!currentProject?.id) {
      return;
    }
  
    setLoadingModules(true);
    try {
      const response = await api.get(`/api-integration/modules?project_id=${currentProject.id}`);
      if (response.code === 0) {
        const modules = response.data.modules || [];
        setModules(modules);
        console.log('加载模块列表成功:', modules);
      } else {
        message.error(response.message || '加载模块列表失败');
      }
    } catch (error: any) {
      console.error('加载模块列表失败:', error);
      message.error(error.response?.data?.message || '加载模块列表失败');
    } finally {
      setLoadingModules(false);
    }
  };
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

  const analyzeAllModules = async () => {
    if (!currentProject?.id) return;

    setAnalyzing(true);
    try {
      const response = await api.post('/api-integration/modules/analyze-all', {
        project_id: currentProject.id
      });
      if (response.code === 0) {
        const taskId = response.data?.task_id;
        if (taskId) {
          setCurrentTaskId(taskId);
          // 立即查询一次进度
          await refreshTaskProgress(taskId);
        }
        message.success('模块分析任务已创建，请点击"刷新进度"查看分析状态');
        loadModules();
      } else {
        message.error(response.message || '创建分析任务失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '创建分析任务失败');
    } finally {
      setAnalyzing(false);
    }
  };

  // 刷新任务进度
  const refreshTaskProgress = async (taskId?: number) => {
    const targetTaskId = taskId || currentTaskId;
    if (!targetTaskId) {
      message.warning('没有可查询的任务');
      return;
    }

    try {
      const response = await api.get(`/api-integration/scenarios/analyze/progress/${targetTaskId}`);
      if (response.code === 0) {
        setTaskProgress(response.data);

        // 如果任务完成，自动刷新模块列表
        if (response.data?.status === 'completed') {
          message.success('模块分析完成');
          await loadModules();
          // 5秒后自动清除任务状态
          setTimeout(() => {
            setCurrentTaskId(null);
            setTaskProgress(null);
          }, 5000);
        } else if (response.data?.status === 'failed') {
          message.error(`分析失败: ${response.data?.error_message || '未知错误'}`);
        }
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '刷新进度失败');
    }
  };

  const analyzeSelectedModules = async () => {
    if (!currentProject?.id) return;
    if (selectedModuleIds.length === 0) {
      message.warning('请先选择要分析的模块');
      return;
    }
  
    setAnalyzing(true);
    try {
      // 分析选中的模块
      const promises = selectedModuleIds.map(moduleId =>
        api.post(`/api-integration/modules/${moduleId}/analyze`, {
          project_id: currentProject.id
        })
      );
  
      await Promise.all(promises);
      message.success(`已创建 ${selectedModuleIds.length} 个模块的分析任务`);
      setSelectedModuleIds([]);
      await loadModules();
    } catch (error: any) {
      message.error(error.response?.data?.message || '创建分析任务失败');
    } finally {
      setAnalyzing(false);
    }
  };
  const viewModuleDetail = async (module: Module) => {
    try {
      const response = await api.get(`/api-integration/modules/${module.id}/status`);
      if (response.code === 0) {
        setModuleDetail(response.data);
        setModuleDetailVisible(true);
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '加载模块详情失败');
    }
  };

  const analyzeCrossModuleDependencies = async () => {
    if (!currentProject?.id) return;
  
    setAnalyzingCrossModule(true);
    try {
      const response = await api.post('/api-integration/modules/analyze-cross-module', {
        project_id: currentProject.id
      });
      if (response.code === 0) {
        message.success('模块间依赖分析完成');
        loadDependencies();
      } else {
        message.error(response.message || '模块间依赖分析失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '模块间依赖分析失败');
    } finally {
      setAnalyzingCrossModule(false);
    }
  };
  const loadDependencies = async () => {
    if (!currentProject?.id) return;

    try {
      const response = await api.get(`/api-integration/modules/dependencies?project_id=${currentProject.id}`);
      if (response.code === 0) {
        setDependencies(response.data.dependencies || []);
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '加载模块间依赖失败');
    }
  };

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

  const moduleColumns = [
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
      title: '详细信息',
      key: 'details',
      render: (_: any, record: Module) => (
        <Space size="small">
          <Tooltip title="点击查看依赖关系">
            <Button 
              type="text" 
              size="small"
              icon={<LinkOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                handleShowDependencies(record.id);
              }}
              style={{ 
                color: '#1890ff',
                fontWeight: selectedModuleId === record.id && selectedDetailType === 'dependencies' ? 'bold' : 'normal'
              }}
            >
              依赖: {record.dependency_count || 0}
            </Button>
          </Tooltip>
          <Tooltip title="点击查看输入接口">
            <Button 
              type="text" 
              size="small"
              icon={<ArrowDownOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                handleShowInputEndpoints(record.id);
              }}
              style={{ 
                color: '#52c41a',
                fontWeight: selectedModuleId === record.id && selectedDetailType === 'input' ? 'bold' : 'normal'
              }}
            >
              输入: {record.input_endpoint_count || 0}
            </Button>
          </Tooltip>
          <Tooltip title="点击查看输出接口">
            <Button 
              type="text" 
              size="small"
              icon={<ArrowUpOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                handleShowOutputEndpoints(record.id);
              }}
              style={{ 
                color: '#fa8c16',
                fontWeight: selectedModuleId === record.id && selectedDetailType === 'output' ? 'bold' : 'normal'
              }}
            >
              输出: {record.output_endpoint_count || 0}
            </Button>
          </Tooltip>
        </Space>
      ),
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
          <Button type="link" icon={<EyeOutlined />} onClick={() => viewModuleDetail(record)}>
            详情
          </Button>
          <Button type="link" icon={<PlayCircleOutlined />} onClick={() => analyzeModule(record.id)}>
            {record.analysis_status === 'completed' ? '重新分析' : '分析'}
          </Button>
        </Space>
      )
    }
  ];

  // ==================== 跨模块组合 ====================

  const loadModuleChains = async () => {
    if (!currentProject?.id) return;

    try {
      const response = await api.get(`/api-integration/modules/chains?project_id=${currentProject.id}`);
      if (response.code === 0) {
        setModuleChains(response.data.chains || []);
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '加载模块链路列表失败');
    }
  };

  const handleCompose = async () => {
    try {
      const values = await composeForm.validateFields();
      const { chain_name, description, module_chain } = values;

      setComposing(true);
      const response = await api.post('/api-integration/modules/compose', {
        project_id: currentProject.id,
        module_chain: module_chain,
        chain_name,
        description
      });

      if (response.code === 0) {
        message.success('跨模块场景组合成功');
        setComposeVisible(false);
        composeForm.resetFields();
        loadModuleChains();
        loadScenarios();
      } else {
        message.error(response.message || '跨模块场景组合失败');
      }
    } catch (error: any) {
      if (error.errorFields) {
        message.error('请填写完整信息');
      } else {
        message.error(error.response?.data?.message || '跨模块场景组合失败');
      }
    } finally {
      setComposing(false);
    }
  };

  const viewChainDetail = async (chain: ModuleChain) => {
    setSelectedChainDetail(chain);
    setChainDetailVisible(true);
  };

  const deleteChain = async (chainId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个模块链路吗？',
      onOk: async () => {
        try {
          const response = await api.delete(`/api-integration/modules/chains/${chainId}`);
          if (response.code === 0) {
            message.success('删除成功');
            loadModuleChains();
          } else {
            message.error(response.message || '删除失败');
          }
        } catch (error: any) {
          message.error(error.response?.data?.message || '删除失败');
        }
      }
    });
  };

  const chainColumns = [
    {
      title: '链路名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong>{text}</strong>
    },
    {
      title: '模块链路',
      dataIndex: 'group_names',
      key: 'group_names',
      render: (names: string[]) => (
        <Space>
          {names.map((name, index) => (
            <React.Fragment key={name}>
              <Tag color="blue">{name}</Tag>
              {index < names.length - 1 && <ArrowRightOutlined />}
            </React.Fragment>
          ))}
        </Space>
      )
    },
    {
      title: '接口数量',
      dataIndex: 'endpoint_count',
      key: 'endpoint_count',
      width: 100
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString('zh-CN')
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: ModuleChain) => (
        <Space size="small">
          <Button type="link" icon={<EyeOutlined />} onClick={() => viewChainDetail(record)}>
            详情
          </Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => deleteChain(record.id)}>
            删除
          </Button>
        </Space>
      )
    }
  ];

  useEffect(() => {
    if (currentProject?.id) {
      loadScenarios();
      loadModules();
      loadDependencies();
      loadModuleChains();
    }
  }, [currentProject?.id]);

  return (
    <div>
      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          {/* 模块分析标签页 - 第一步：分析模块内部依赖 */}
                              <TabPane tab="模块分析" key="modules">
            <Card
              title="模块列表"
              extra={
                <Space>
                  <Button icon={<ReloadOutlined />} onClick={loadModules} loading={loadingModules}>
                    刷新
                  </Button>
                  <Button type="primary" icon={<PlayCircleOutlined />} onClick={analyzeAllModules} loading={analyzing}>
                    分析所有模块
                  </Button>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={analyzeSelectedModules}
                    loading={analyzing}
                    disabled={selectedModuleIds.length === 0}
                  >
                    分析选中模块 ({selectedModuleIds.length})
                  </Button>
                  <Button icon={<PlayCircleOutlined />} onClick={analyzeCrossModuleDependencies} loading={analyzingCrossModule}>
                    分析模块间依赖
                  </Button>
                  <Button onClick={() => setDependencyGraphVisible(true)} disabled={dependencies.length === 0 || analyzingCrossModule}>
                    查看依赖图
                  </Button>
                </Space>
              }
            >
              <Table
                columns={moduleColumns}
                dataSource={modules}
                rowKey="id"
                scroll={{ y: 500 }}
                pagination={false}
                locale={{
                  emptyText: (
                    <Empty
                      description={
                      <div>
                        <p>暂无模块数据</p>
                        <p style={{ fontSize: '12px', color: '#999' }}>
                          请先在"接口定义"页面创建分组并添加接口，<br/>
                          只有包含接口的分组才会作为模块显示
                        </p>
                      </div>
                    }
                  />
                )
                }}
                rowSelection={{
                  selectedRowKeys: selectedModuleIds,
                  onChange: (selectedKeys) => setSelectedModuleIds(selectedKeys as number[]),
                  getCheckboxProps: (record: Module) => ({
                    disabled: record.analysis_status === 'completed',
                  }),
                }}
                expandable={{
                  expandedRowRender: (record: Module) => (
                    <div style={{ padding: '16px 0' }}>
                      <ModuleDetailPanel 
                        moduleId={record.id}
                        projectId={currentProject?.id}
                        detailType={selectedDetailType}
                      />
                    </div>
                  ),
                  expandIcon: ({ expanded, onExpand, record }) => {
                    if (expanded) {
                      return <Button type="link" size="small" onClick={(e) => onExpand(record, e)}>收起 ▲</Button>;
                    }
                    return <Button type="link" size="small" onClick={(e) => onExpand(record, e)}>展开 ▼</Button>;
                  },
                }}
              />
            </Card>

            {/* 任务状态显示 */}
            {currentTaskId && (
              <Card 
                size="small" 
                style={{ marginTop: 16, backgroundColor: '#f6ffed', borderColor: '#b7eb8f' }}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Space>
                      <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      <span style={{ fontWeight: 500 }}>分析任务已创建</span>
                      <Tag color={taskProgress?.status === 'completed' ? 'success' : taskProgress?.status === 'failed' ? 'error' : 'processing'}>
                        {taskProgress?.status === 'completed' ? '已完成' : taskProgress?.status === 'failed' ? '失败' : '进行中'}
                      </Tag>
                    </Space>
                    <Button size="small" icon={<ReloadOutlined />} onClick={() => refreshTaskProgress()}>
                      刷新进度
                    </Button>
                  </div>
                  {taskProgress && (
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ fontSize: 12, color: '#666' }}>分析进度</span>
                        <span style={{ fontSize: 12, fontWeight: 500 }}>{taskProgress.progress || 0}%</span>
                      </div>
                      <Progress 
                        percent={taskProgress.progress || 0} 
                        status={taskProgress.status === 'failed' ? 'exception' : taskProgress.status === 'completed' ? 'success' : 'active'}
                        strokeColor={{
                          '0%': '#108ee9',
                          '100%': '#87d068',
                        }}
                      />
                      {taskProgress.progress_message && (
                        <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                          {taskProgress.progress_message}
                        </div>
                      )}
                      {taskProgress.status === 'completed' && taskProgress.task_result && (
                        <div style={{ marginTop: 8, fontSize: 12 }}>
                          <Tag color="success">分析完成</Tag>
                          <span style={{ marginLeft: 8 }}>
                            共分析 {taskProgress.task_result.dependency_count || 0} 个依赖，
                            发现 {taskProgress.task_result.chain_count || 0} 个业务链路
                          </span>
                        </div>
                      )}
                      {taskProgress.status === 'failed' && taskProgress.error_message && (
                        <div style={{ marginTop: 8, fontSize: 12, color: '#ff4d4f' }}>
                          错误: {taskProgress.error_message}
                        </div>
                      )}
                    </div>
                  )}
                </Space>
              </Card>
            )}
          </TabPane>

          {/* 跨模块组合标签页 */}
          <TabPane tab="跨模块组合" key="module-chains">
            <div style={{ marginBottom: 16 }}>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setComposeVisible(true)}>
                组合新场景
              </Button>
            </div>
            <Table
              columns={chainColumns}
              dataSource={moduleChains}
              rowKey="id"
              scroll={{ y: 500 }}
              pagination={false}
            />
          </TabPane>

          {/* 场景列表标签页 - 第三步：查看和管理所有场景 */}
          <TabPane tab="场景列表" key="scenarios">
            <div style={{ marginBottom: 16 }}>
              <Space>
                <Button type="primary" icon={<PlusOutlined />} onClick={handleAnalyzeDependencies}>
                  分析依赖
                </Button>
              </Space>
            </div>
            <Table
              columns={scenarioColumns}
              dataSource={scenarios}
              rowKey="id"
              loading={loading}
              scroll={{ y: 500 }}
              pagination={false}
            />
          </TabPane>
        </Tabs>
      </Card>

      {/* 场景相关的弹窗 */}
      <Modal
        title="接口依赖分析"
        open={analyzeModalVisible}
        onCancel={() => setAnalyzeModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setAnalyzeModalVisible(false)}>
            关闭
          </Button>,
          analyzeResult && (
            <Button key="generate" type="primary" onClick={() => {
              setAnalyzeModalVisible(false);
              setGenerateModalVisible(true);
            }}>
              生成场景
            </Button>
          ),
        ]}
        width={800}
      >
        {analyzeProgress < 100 ? (
          <div style={{ padding: '40px 0' }}>
            <Progress percent={analyzeProgress} status="active" />
            <p style={{ textAlign: 'center', marginTop: '16px', color: '#999' }}>
              正在分析接口依赖关系...
            </p>
          </div>
        ) : (
          <div>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="发现依赖">
                <Tag color="blue">{analyzeResult?.dependency_count || 0}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="识别链路">
                <Tag color="green">{analyzeResult?.chain_count || 0}</Tag>
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: '16px' }}>
              <h4>业务链路列表：</h4>
              {analyzeResult?.chains?.map((chain: number[], index: number) => (
                <div key={index} style={{ marginBottom: '8px' }}>
                  <Tag color={selectedChain.join(',') === chain.join(',') ? 'blue' : 'default'}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelectedChain(chain)}>
                    链路 {index + 1}: {chain.join(' → ')}
                  </Tag>
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>

      <Modal
        title="生成场景"
        open={generateModalVisible}
        onOk={handleGenerateScenario}
        onCancel={() => setGenerateModalVisible(false)}
        okText="生成"
        cancelText="取消"
      >
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px' }}>场景名称：</label>
          <input
            type="text"
            value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
            placeholder="请输入场景名称"
            style={{ width: '100%', padding: '8px', border: '1px solid #d9d9d9', borderRadius: '4px' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: '8px' }}>选择的业务链路：</label>
          <Tag color="blue">{selectedChain.join(' → ')}</Tag>
        </div>
      </Modal>

      <Modal
        title="场景依赖图"
        open={graphModalVisible}
        onCancel={() => setGraphModalVisible(false)}
        footer={[<Button key="close" onClick={() => setGraphModalVisible(false)}>关闭</Button>]}
        width={1000}
        style={{ top: 20 }}
      >
        {graphData ? (
          <div style={{ padding: '20px', background: '#fff', borderRadius: '4px' }}>
            <div style={{ marginBottom: '16px' }}>
              <Tag color="blue">节点数: {graphData.nodes.length}</Tag>
              <Tag color="green">边数: {graphData.edges.length}</Tag>
              <Tag color="red">红色=直接依赖</Tag>
              <Tag color="default">灰色=间接依赖</Tag>
            </div>
            <DependencyGraph data={graphData} width={950} height={500} />
          </div>
        ) : (
          <p style={{ textAlign: 'center', color: '#999' }}>加载中...</p>
        )}
      </Modal>

      <Modal
        title="编辑场景"
        open={editModalVisible}
        onOk={handleSaveScenario}
        onCancel={() => setEditModalVisible(false)}
        okText="保存"
        cancelText="取消"
        width={600}
      >
        {currentScenario && (
          <div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>场景名称：</label>
              <input
                type="text"
                value={currentScenario.name}
                onChange={(e) => setCurrentScenario({ ...currentScenario, name: e.target.value })}
                placeholder="请输入场景名称"
                style={{ width: '100%', padding: '8px', border: '1px solid #d9d9d9', borderRadius: '4px' }}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>场景描述：</label>
              <TextArea
                value={currentScenario.description || ''}
                onChange={(e) => setCurrentScenario({ ...currentScenario, description: e.target.value })}
                placeholder="请输入场景描述"
                rows={4}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>超时时间（秒）：</label>
              <input
                type="number"
                value={currentScenario.timeout || 300}
                onChange={(e) => setCurrentScenario({ ...currentScenario, timeout: parseInt(e.target.value) })}
                style={{ width: '100%', padding: '8px', border: '1px solid #d9d9d9', borderRadius: '4px' }}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>重试次数：</label>
              <input
                type="number"
                value={currentScenario.retry_count || 0}
                onChange={(e) => setCurrentScenario({ ...currentScenario, retry_count: parseInt(e.target.value) })}
                style={{ width: '100%', padding: '8px', border: '1px solid #d9d9d9', borderRadius: '4px' }}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'flex', alignItems: 'center', marginBottom: '8px', fontWeight: 'bold' }}>
                <input
                  type="checkbox"
                  checked={currentScenario.continue_on_failure || false}
                  onChange={(e) => setCurrentScenario({ ...currentScenario, continue_on_failure: e.target.checked })}
                  style={{ marginRight: '8px' }}
                />
                失败后继续执行
              </label>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        title="执行场景"
        open={executeModalVisible}
        onCancel={() => setExecuteModalVisible(false)}
        footer={executionResult ? [
          <Button key="close" onClick={() => setExecuteModalVisible(false)}>关闭</Button>,
        ] : [
          <Button key="cancel" onClick={() => setExecuteModalVisible(false)}>取消</Button>,
          <Button key="execute" type="primary" onClick={handleExecuteWithEnvironment} loading={!executionResult}>
            执行
          </Button>,
        ]}
        width={800}
      >
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>选择测试环境：</label>
          <select
            value={selectedEnvironmentId || ''}
            onChange={(e) => setSelectedEnvironmentId(Number(e.target.value))}
            style={{ width: '100%', padding: '8px', border: '1px solid #d9d9d9', borderRadius: '4px' }}
          >
            {environments.map((env) => (
              <option key={env.id} value={env.id}>{env.name}</option>
            ))}
          </select>
        </div>

        {executionResult && (
          <div>
            <h4 style={{ marginBottom: '16px' }}>执行结果：</h4>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="执行状态">
                <Tag color={executionResult.status === 'success' ? 'green' : 'red'}>
                  {executionResult.status === 'success' ? '成功' : '失败'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="执行时长">{executionResult.duration_ms} ms</Descriptions.Item>
              <Descriptions.Item label="总步骤数">{executionResult.total_steps}</Descriptions.Item>
              <Descriptions.Item label="通过步骤">
                <Tag color="green">{executionResult.passed_steps}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="失败步骤">
                <Tag color="red">{executionResult.failed_steps}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="开始时间">
                {new Date(executionResult.started_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
            </Descriptions>
          </div>
        )}
      </Modal>

      {/* 模块分析相关的弹窗 */}
      <Modal
        title={`模块详情 - ${moduleDetail?.group_name}`}
        open={moduleDetailVisible}
        onCancel={() => setModuleDetailVisible(false)}
        footer={null}
        width={1000}
      >
        {moduleDetail && (
          <>
            <Descriptions bordered column={2} style={{ marginBottom: 16 }}>
              <Descriptions.Item label="模块名称">{moduleDetail.group_name}</Descriptions.Item>
              <Descriptions.Item label="状态">{getStatusTag(moduleDetail.status)}</Descriptions.Item>
              <Descriptions.Item label="依赖关系数量">{moduleDetail.dependency_count}</Descriptions.Item>
              <Descriptions.Item label="输入接口数">{moduleDetail.input_endpoints.length}</Descriptions.Item>
              <Descriptions.Item label="输出接口数">{moduleDetail.output_endpoints.length}</Descriptions.Item>
              <Descriptions.Item label="内部链路数">{moduleDetail.internal_chains.length}</Descriptions.Item>
            </Descriptions>

            {moduleDetail.status === 'completed' && (
              <>
                {/* 内部业务链路 */}
                {moduleDetail.internal_chains.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <h4 style={{ marginBottom: 8 }}>内部业务链路</h4>
                    <div style={{ backgroundColor: '#fafafa', padding: 12, borderRadius: 4 }}>
                      {moduleDetail.internal_chains.map((chain, index) => (
                        <div key={index} style={{ marginBottom: 8 }}>
                          <Tag color="blue" style={{ marginRight: 8 }}>链路 {index + 1}</Tag>
                          <span style={{ fontSize: 12 }}>
                            接口 {chain.join(' → ')}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 输入接口 */}
                {moduleDetail.input_endpoints.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <h4 style={{ marginBottom: 8 }}>输入接口（接收外部数据）</h4>
                    <div style={{ backgroundColor: '#f6ffed', padding: 12, borderRadius: 4 }}>
                      {moduleDetail.input_endpoints.map((endpointId, index) => (
                        <Tag key={endpointId} color="green" style={{ marginBottom: 4 }}>
                          接口 ID: {endpointId}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}

                {/* 输出接口 */}
                {moduleDetail.output_endpoints.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <h4 style={{ marginBottom: 8 }}>输出接口（向外输出数据）</h4>
                    <div style={{ backgroundColor: '#fff7e6', padding: 12, borderRadius: 4 }}>
                      {moduleDetail.output_endpoints.map((endpointId, index) => (
                        <Tag key={endpointId} color="orange" style={{ marginBottom: 4 }}>
                          接口 ID: {endpointId}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {moduleDetail.status !== 'completed' && (
              <Alert
                message="模块尚未完成分析"
                description="请先完成模块分析后再查看详细结果"
                type="info"
                showIcon
              />
            )}
          </>
        )}
      </Modal>

      <Modal
        title="模块依赖关系图"
        open={dependencyGraphVisible}
        onCancel={() => setDependencyGraphVisible(false)}
        footer={null}
        width={1200}
      >
        <DependencyGraph dependencies={dependencies} />
      </Modal>

      {/* 跨模块组合相关的弹窗 */}
      <Modal
        title="组合跨模块场景"
        open={composeVisible}
        onOk={handleCompose}
        onCancel={() => {
          setComposeVisible(false);
          composeForm.resetFields();
        }}
        confirmLoading={composing}
        width={800}
      >
        <Form
          form={composeForm}
          layout="vertical"
          initialValues={{ module_chain: [] }}
        >
          <Form.Item label="链路名称" name="chain_name" rules={[{ required: true, message: '请输入链路名称' }]}>
            <Input placeholder="例如：用户下单支付流程" />
          </Form.Item>

          <Form.Item label="描述" name="description">
            <TextArea rows={3} placeholder="请输入场景描述" />
          </Form.Item>

          <Form.Item label="选择模块链路" name="module_chain" rules={[{ required: true, message: '请选择至少一个模块' }]}>
            <Select mode="multiple" placeholder="请选择模块（按执行顺序）" style={{ width: '100%' }}>
              {modules.filter(m => m.analysis_status === 'completed').map(module => (
                <Option key={module.id} value={module.id}>{module.name}</Option>
              ))}
            </Select>
          </Form.Item>

          {modules.filter(m => m.analysis_status !== 'completed').length > 0 && (
            <Alert
              message="部分模块未完成分析"
              description="只有已完成分析的模块才能参与跨模块场景组合"
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}
        </Form>

        <Alert
          message="提示"
          description="模块的执行顺序将按照您选择的顺序进行，系统会自动识别模块间的数据传递关系"
          type="info"
          showIcon
        />
      </Modal>

      <Modal
        title={`链路详情 - ${selectedChainDetail?.name}`}
        open={chainDetailVisible}
        onCancel={() => setChainDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedChainDetail && (
          <>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="链路名称">{selectedChainDetail.name}</Descriptions.Item>
              <Descriptions.Item label="接口数量">{selectedChainDetail.endpoint_count}</Descriptions.Item>
              <Descriptions.Item label="模块数量">{selectedChainDetail.group_count}</Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(selectedChainDetail.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label="描述" span={2}>
                {selectedChainDetail.description || '无'}
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 24 }}>
              <h4>模块执行顺序</h4>
              <Steps
                direction="vertical"
                current={-1}
                items={selectedChainDetail.group_names.map((name, index) => ({
                  title: name,
                  description: `步骤 ${index + 1}`,
                  icon: <CheckCircleOutlined />
                }))}
              />
            </div>
          </>
        )}
      </Modal>
    </div>
  );
};

export default Scenarios;