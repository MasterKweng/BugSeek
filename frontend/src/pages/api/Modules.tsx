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
  Progress,
  Tooltip,
  Alert,
  Empty
} from 'antd';
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  LinkOutlined,
  ArrowDownOutlined,
  ArrowUpOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useProjectStore } from '../../store/project';
import { useScenarioStore } from '../../store/scenario';
import DependencyGraph from '../../components/DependencyGraph';
import type { Module, AnalysisStatus } from '../../types/scenario';

const Modules: React.FC = () => {
  const navigate = useNavigate();
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
    loadModules,
    analyzeModule,
    analyzeAllModules,
    analyzeSelectedModules,
    analyzeCrossModuleDependencies,
    loadDependencies,
    setSelectedModuleIds,
    refreshTaskProgress,
    setDependencyGraphVisible
  } = useScenarioStore();

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

  const moduleColumns = [
    {
      title: '模块名称',
      dataIndex: 'name',
      key: 'name',
      width: 250,
      ellipsis: true,
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
      width: 180,
      ellipsis: true,
      responsive: ['lg', 'xl', 'xxl']
    },
    {
      title: '详细信息',
      key: 'details',
      render: (_: any, record: Module) => (
        <Space size="small">
          <Tooltip title="点击查看内部链路">
            <Button
              type="text"
              size="small"
              icon={<LinkOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/api/modules/${record.id}?tab=internal-chains`);
              }}
              style={{
                color: '#1890ff',
              }}
            >
              内部链路: {record.internal_chains_count || 0}
            </Button>
          </Tooltip>
          <Tooltip title="点击查看输入接口">
            <Button
              type="text"
              size="small"
              icon={<ArrowDownOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/api/modules/${record.id}?tab=input`);
              }}
              style={{
                color: '#52c41a',
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
                navigate(`/api/modules/${record.id}?tab=output`);
              }}
              style={{
                color: '#fa8c16',
              }}
            >
              输出: {record.output_endpoint_count || 0}
            </Button>
          </Tooltip>
          <Tooltip title="点击查看依赖关系">
            <Button
              type="text"
              size="small"
              icon={<LinkOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/api/modules/${record.id}?tab=dependencies`);
              }}
              style={{
                color: '#722ed1',
              }}
            >
              依赖: {record.dependency_count || 0}
            </Button>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: '接口数量',
      dataIndex: 'endpoint_count',
      key: 'endpoint_count',
      width: 100,
      align: 'center'
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      fixed: 'right',
      responsive: ['md', 'lg', 'xl', 'xxl'],
      render: (_: any, record: Module) => (
        <Button
          type="link"
          icon={<PlayCircleOutlined />}
          onClick={() => analyzeModule(record.id)}
        >
          {record.analysis_status === 'completed' ? '重新分析' : '分析'}
        </Button>
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
          scroll={{ x: 1200 }}
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