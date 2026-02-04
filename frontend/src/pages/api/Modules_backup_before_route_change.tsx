/**
 * 模块依赖分析页面 - 优化版
 * 使用统一 API 响应格式、Zustand Store
 */
import React, { useEffect, useState, useCallback } from 'react';
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
  Alert,
  Empty
} from 'antd';
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  EyeOutlined,
  ReloadOutlined,
  LinkOutlined,
  ArrowDownOutlined,
  ArrowUpOutlined
} from '@ant-design/icons';
import { useProjectStore } from '../../store/project';
import { useScenarioStore } from '../../store/scenario';
import api from '../../services/api';
import DependencyGraph from '../../components/DependencyGraph';
import type { Module, AnalysisStatus } from '../../types/scenario';

const Modules: React.FC = () => {
  const { currentProject } = useProjectStore();
  const {
    modules,
    selectedModuleIds,
    loadingModules,
    analyzing,
    currentTaskId,
    taskProgress,
    dependencies,
    dependencyGraphVisible,
    moduleDetail,
    moduleDetailVisible,
    loadModules,
    analyzeModule,
    analyzeAllModules,
    analyzeSelectedModules,
    analyzeCrossModuleDependencies,
    loadDependencies,
    viewModuleDetail,
    setModuleDetailVisible,
    setSelectedModuleIds,
    refreshTaskProgress,
    setDependencyGraphVisible
  } = useScenarioStore();

  // 详情展示类型
  const [selectedModuleId, setSelectedModuleId] = useState<number | null>(null);
  const [selectedDetailType, setSelectedDetailType] = useState<'dependencies' | 'input' | 'output' | null>(null);

  useEffect(() => {
    loadModules();
    loadDependencies();
  }, [currentProject?.id]);

  const getStatusTag = (status: AnalysisStatus) => {
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

  const handleShowDependencies = (moduleId: number) => {
    setSelectedModuleId(moduleId);
    setSelectedDetailType('dependencies');
  };

  const handleShowInputEndpoints = (moduleId: number) => {
    setSelectedModuleId(moduleId);
    setSelectedDetailType('input');
  };

  const handleShowOutputEndpoints = (moduleId: number) => {
    setSelectedModuleId(moduleId);
    setSelectedDetailType('output');
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
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
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
          <Button
            type="link"
            icon={<PlayCircleOutlined />}
            onClick={() => analyzeModule(record.id)}
          >
            {record.analysis_status === 'completed' ? '重新分析' : '分析'}
          </Button>
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
            <Button icon={<PlayCircleOutlined />} onClick={analyzeCrossModuleDependencies} loading={analyzing}>
              分析模块间依赖
            </Button>
            <Button onClick={() => setDependencyGraphVisible(true)} disabled={dependencies.length === 0}>
              查看依赖图
            </Button>
          </Space>
        }
      >
        <Table
          columns={moduleColumns}
          dataSource={modules}
          rowKey="id"
          loading={loadingModules}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个模块`
          }}
          rowSelection={{
            selectedRowKeys: selectedModuleIds,
            onChange: (selectedKeys) => setSelectedModuleIds(selectedKeys as number[]),
            getCheckboxProps: (record: Module) => ({
              disabled: record.analysis_status === 'completed',
            }),
          }}
        />
      </Card>

      {/* 任务进度显示 */}
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
              </div>
            )}
          </Space>
        </Card>
      )}

      {/* 模块详情弹窗 */}
      <Modal
        title={`模块详情 - ${moduleDetail?.group_name}`}
        open={moduleDetailVisible}
        onCancel={() => setModuleDetailVisible(false)}
        footer={null}
        width={800}
      >
        {moduleDetail && (
          <Descriptions bordered column={2}>
            <Descriptions.Item label="模块名称">{moduleDetail.group_name}</Descriptions.Item>
            <Descriptions.Item label="状态">{getStatusTag(moduleDetail.status as AnalysisStatus)}</Descriptions.Item>
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