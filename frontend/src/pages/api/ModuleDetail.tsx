/**
 * 模块详情页面 - 独立页面方案
 * 适用于大数据量场景（如几千条链路）
 * 
 * [SCENARIO-A-SOLUTION] 场景组装方案A：独立页面
 * [BACKUP-MARK] 此文件可回滚，备份文件：Modules_backup_before_route_change.tsx
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Tabs,
  Table,
  Button,
  Space,
  Tag,
  Input,
  Select,
  message,
  Row,
  Col,
  Descriptions,
  Empty
} from 'antd';
import {
  ArrowLeftOutlined,
  SearchOutlined,
  FilterOutlined,
  DownloadOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useProjectStore } from '../../store/project';
import { useScenarioStore } from '../../store/scenario';
import type { Module, ModuleDetail as ModuleDetailType, ModuleDependency, ApiEndpoint } from '../../types/scenario';

const { TabPane } = Tabs;
const { Option } = Select;
const { TextArea } = Input;

const ModuleDetail: React.FC = () => {
  const navigate = useNavigate();
  const { moduleId } = useParams<{ moduleId: string }>();
  const [searchParams] = useSearchParams();
  const { currentProject } = useProjectStore();
  
  const {
    modules,
    moduleDetail,
    moduleDetailVisible,
    loadingModuleDetail,
    loadingDependencies,
    loadingModuleChains,
    loadingInternalChains,
    moduleChains,
    internalChains,
    dependencies,
    setModuleDetailVisible,
    viewModuleDetail,
    loadDependencies,
    loadModuleChains,
    loadInternalChains,  // [SCENARIO-A-SOLUTION] 添加 loadInternalChains
  } = useScenarioStore();

  const [activeTab, setActiveTab] = useState<'dependencies' | 'input' | 'output' | 'internal-chains'>('internal-chains');
  const [searchText, setSearchText] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [chainPage, setChainPage] = useState(1);
  const [chainPageSize, setChainPageSize] = useState(50);

  // 获取当前模块
  const currentModule = modules.find(m => m.id === Number(moduleId));

  // [SCENARIO-A-SOLUTION] 从 URL 参数中读取 tab 并设置 activeTab
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && ['internal-chains', 'input', 'output', 'dependencies'].includes(tabParam)) {
      setActiveTab(tabParam as any);
    }
  }, [searchParams]);

  // 加载模块详情
  useEffect(() => {
    if (moduleId && currentModule) {
      viewModuleDetail(currentModule);
    }
  }, [moduleId, currentModule]);

  // [SCENARIO-A-SOLUTION] 组件卸载时清理弹框状态
  useEffect(() => {
    return () => {
      setModuleDetailVisible(false);
    };
  }, []);

  // 加载依赖数据
  useEffect(() => {
    if (moduleId && currentProject?.id) {
      loadDependencies();
      loadModuleChains();
      // [SCENARIO-A-SOLUTION] 加载内部链路
      loadInternalChains(Number(moduleId));
    }
  }, [moduleId, currentProject?.id, loadDependencies, loadModuleChains, loadInternalChains]);

  // 返回列表页
  const handleBack = () => {
    navigate('/api/scenarios?tab=modules');
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
      case 'failed':
        return <Tag color="error">失败</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  // 过滤链路数据
  const filteredChains = (internalChains || []).filter(chain => {
    if (searchText) {
      const text = searchText.toLowerCase();
      return chain.chain_id.toString().includes(text) ||
             chain.start_endpoint?.toLowerCase().includes(text) ||
             chain.end_endpoint?.toLowerCase().includes(text);
    }
    return true;
  });

  // 分页后的链路数据
  const paginatedChains = filteredChains.slice(
    (chainPage - 1) * chainPageSize,
    chainPage * chainPageSize
  );

  // 依赖关系列
  const dependencyColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '源模块',
      dataIndex: 'source_group_name',
      key: 'source_group_name',
      width: 200,
    },
    {
      title: '目标模块',
      dataIndex: 'target_group_name',
      key: 'target_group_name',
      width: 200,
    },
    {
      title: '依赖强度',
      dataIndex: 'dependency_strength',
      key: 'dependency_strength',
      width: 120,
      render: (strength: number) => {
        const color = strength > 0.7 ? 'red' : strength > 0.4 ? 'orange' : 'green';
        return <Tag color={color}>{(strength * 100).toFixed(1)}%</Tag>;
      },
    },
  ];

  // 接口列
  const endpointColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '接口路径',
      dataIndex: 'path',
      key: 'path',
      width: 300,
      ellipsis: true,
    },
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      width: 100,
      render: (method: string) => {
        const colorMap: Record<string, string> = {
          GET: 'green',
          POST: 'blue',
          PUT: 'orange',
          DELETE: 'red',
          PATCH: 'purple',
        };
        return <Tag color={colorMap[method] || 'default'}>{method}</Tag>;
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
  ];

  // 获取 HTTP 方法颜色
  const getMethodColor = (method: string): string => {
    const colorMap: Record<string, string> = {
      GET: 'green',
      POST: 'blue',
      PUT: 'orange',
      DELETE: 'red',
      PATCH: 'purple',
    };
    return colorMap[method] || 'default';
  };

  // 内部链路列
  const chainColumns = [
    {
      title: '链路ID',
      dataIndex: 'chain_id',
      key: 'chain_id',
      width: 100,
      sorter: (a: any, b: any) => a.chain_id - b.chain_id,
    },
    {
      title: '步骤数',
      dataIndex: 'step_count',
      key: 'step_count',
      width: 100,
      sorter: (a: any, b: any) => a.step_count - b.step_count,
    },
    {
      title: '起点接口',
      dataIndex: 'start_endpoint',
      key: 'start_endpoint',
      width: 400,
      ellipsis: true,
      render: (endpoint: any) => endpoint ? (
        <Space direction="vertical" size={0}>
          <Space>
            <Tag color={getMethodColor(endpoint.method)}>{endpoint.method}</Tag>
            <span style={{fontSize: 12, color: '#999'}}>ID: {endpoint.id}</span>
          </Space>
          <div style={{fontSize: 12}}>{endpoint.path}</div>
        </Space>
      ) : <span style={{color: '#999'}}>-</span>
    },
    {
      title: '终点接口',
      dataIndex: 'end_endpoint',
      key: 'end_endpoint',
      width: 400,
      ellipsis: true,
      render: (endpoint: any) => endpoint ? (
        <Space direction="vertical" size={0}>
          <Space>
            <Tag color={getMethodColor(endpoint.method)}>{endpoint.method}</Tag>
            <span style={{fontSize: 12, color: '#999'}}>ID: {endpoint.id}</span>
          </Space>
          <div style={{fontSize: 12}}>{endpoint.path}</div>
        </Space>
      ) : <span style={{color: '#999'}}>-</span>
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      fixed: 'right' as const,
      render: (_: any, record: any) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => handleViewChainDetail(record)}
        >
          详情
        </Button>
      ),
    },
  ];

  // 查看链路详情
  const handleViewChainDetail = (chain: any) => {
    navigate(`/api/modules/${moduleId}/chains/${chain.chain_id}`);
  };

  // 导出数据
  const handleExport = () => {
    message.success('导出功能开发中...');
    // TODO: 实现导出逻辑
  };

  if (!currentModule) {
    return (
      <div style={{ padding: '24px' }}>
        <Empty description="模块不存在" />
      </div>
    );
  }

  return (
    <div style={{ padding: '24px', height: 'calc(100vh - 112px)', overflow: 'auto' }}>
      {/* 返回按钮和标题 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={handleBack}
            >
              返回列表
            </Button>
            <h2 style={{ margin: 0 }}>{currentModule.name} - 模块详情</h2>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                if (currentModule) viewModuleDetail(currentModule);
              }}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 基本信息 */}
      <Card style={{ marginBottom: 24 }}>
        <Descriptions bordered column={3}>
          <Descriptions.Item label="模块名称">{currentModule.name}</Descriptions.Item>
          <Descriptions.Item label="模块描述">{currentModule.description || '-'}</Descriptions.Item>
          <Descriptions.Item label="分析状态">{getStatusTag(currentModule.analysis_status)}</Descriptions.Item>
          <Descriptions.Item label="接口数量">{currentModule.endpoint_count}</Descriptions.Item>
          <Descriptions.Item label="依赖关系数">
            {moduleDetail?.dependency_count || (dependencies || []).filter(d => 
              d.source_group_id === currentModule.id || d.target_group_id === currentModule.id
            ).length}
          </Descriptions.Item>
          <Descriptions.Item label="内部链路数">
            {moduleDetail?.internal_chains?.length || (internalChains || []).length}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 详情内容 */}
      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          tabBarExtraContent={
            activeTab === 'internal-chains' && (
              <Space>
                <Input
                  placeholder="搜索链路..."
                  prefix={<SearchOutlined />}
                  style={{ width: 200 }}
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                />
                <Select
                  value={chainPageSize}
                  onChange={setChainPageSize}
                  style={{ width: 120 }}
                >
                  <Option value={20}>20条/页</Option>
                  <Option value={50}>50条/页</Option>
                  <Option value={100}>100条/页</Option>
                </Select>
                <Button
                  icon={<DownloadOutlined />}
                  onClick={handleExport}
                >
                  导出
                </Button>
              </Space>
            )
          }
        >
          <TabPane 
            tab={`内部链路 (${(internalChains || []).length})`} 
            key="internal-chains"
          >
            <Table
              columns={chainColumns}
              dataSource={paginatedChains}
              rowKey="chain_id"
              loading={loadingInternalChains}
              scroll={{ x: 1200, y: 500 }}
              pagination={{
                current: chainPage,
                pageSize: chainPageSize,
                total: filteredChains.length,
                showSizeChanger: false,
                showTotal: (total) => `共 ${total} 条链路，显示 ${(chainPage - 1) * chainPageSize + 1}-${Math.min(chainPage * chainPageSize, total)} 条`,
                onChange: (page) => setChainPage(page),
              }}
            />
          </TabPane>

          <TabPane 
            tab={`输入接口 (${moduleDetail?.input_endpoints_detail?.length || 0})`} 
            key="input"
          >
            <Table
              columns={endpointColumns}
              dataSource={moduleDetail?.input_endpoints_detail || []}
              rowKey="id"
              loading={loadingModuleDetail}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 个输入接口`
              }}
            />
          </TabPane>

          <TabPane 
            tab={`输出接口 (${moduleDetail?.output_endpoints_detail?.length || 0})`} 
            key="output"
          >
            <Table
              columns={endpointColumns}
              dataSource={moduleDetail?.output_endpoints_detail || []}
              rowKey="id"
              loading={loadingModuleDetail}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 个输出接口`
              }}
            />
          </TabPane>

          <TabPane 
            tab={`依赖关系 (${
              (dependencies || []).filter(d => 
                d.source_group_id === currentModule.id || d.target_group_id === currentModule.id
              ).length
            })`} 
            key="dependencies"
          >
            <Table
              columns={dependencyColumns}
              dataSource={(dependencies || []).filter(d => 
                d.source_group_id === currentModule.id || d.target_group_id === currentModule.id
              )}
              rowKey="id"
              loading={loadingDependencies}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条依赖关系`
              }}
            />
          </TabPane>
        </Tabs>
      </Card>
    </div>
  );
};

export default ModuleDetail;