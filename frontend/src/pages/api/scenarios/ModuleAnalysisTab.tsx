/**
 * 模块分析标签页组件
 */
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Button,
  Space,
  message,
  Tag,
  Modal,
  Descriptions,
  Progress,
  Alert,
  Empty,
  Tooltip
} from 'antd';
import {
  LinkOutlined,
  ArrowDownOutlined,
  ArrowUpOutlined,
  PlusOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DeleteOutlined
} from '@ant-design/icons';
import { useScenarioStore } from '../../../store/scenario';
import type { Module, AnalysisStatus } from '../../../types/scenario';
import ModuleDetailPanel from '../components/ModuleDetailPanel';

interface ModuleAnalysisTabProps {
  selectedModuleId: number | null;
  selectedDetailType: 'dependencies' | 'input' | 'output' | null;
  onSelectModuleId: (id: number | null) => void;
  onSelectDetailType: (type: 'dependencies' | 'input' | 'output' | null) => void;
}

const ModuleAnalysisTab: React.FC<ModuleAnalysisTabProps> = ({
  selectedModuleId,
  selectedDetailType,
  onSelectModuleId,
  onSelectDetailType
}) => {
  const navigate = useNavigate();  // [SCENARIO-A-SOLUTION] 添加 navigate hook
  const {
    modules,
    selectedModuleIds,
    moduleDetail,
    moduleDetailVisible,
    currentTaskId,
    taskProgress,
    loadingModules,
    analyzing,
    analyzingCrossModule,
    loadModules,
    analyzeModule,
    analyzeAllModules,
    analyzeSelectedModules,
    analyzeCrossModuleDependencies,
    setModuleDetailVisible,
    setSelectedModuleIds,
    refreshTaskProgress,
    setCurrentTaskId
  } = useScenarioStore();

  useEffect(() => {
    loadModules();
  }, []);

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
    onSelectModuleId(moduleId);
    onSelectDetailType('dependencies');
  };

  const handleShowInputEndpoints = (moduleId: number) => {
    onSelectModuleId(moduleId);
    onSelectDetailType('input');
  };

  const handleShowOutputEndpoints = (moduleId: number) => {
    onSelectModuleId(moduleId);
    onSelectDetailType('output');
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
          {/* [SCENARIO-A-SOLUTION] 详情按钮改为跳转到独立页面 */}
          <Button 
            type="link" 
            icon={<EyeOutlined />} 
            onClick={() => navigate(`/api/modules/${record.id}`)}
          >
            详情
          </Button>
          <Button type="link" icon={<PlayCircleOutlined />} onClick={() => analyzeModule(record.id)}>
            {record.analysis_status === 'completed' ? '重新分析' : '分析'}
          </Button>
        </Space>
      )
    }
  ];

  return (
    <>
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
                      请先在"接口定义"页面创建分组并添加接口，<br />
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
              </div>
            )}
          </Space>
        </Card>
      )}

      {/* 模块详情弹窗 */}
      <Modal
        title="模块详情"
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
    </>
  );
};

export default ModuleAnalysisTab;