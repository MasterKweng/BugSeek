import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Table, 
  Button, 
  Space, 
  Tag, 
  Modal, 
  message, 
  Spin, 
  Tabs, 
  Descriptions,
  Badge,
  Checkbox,
  Drawer,
  Progress,
  Steps,
  Statistic,
  Row,
  Col,
  Switch,
  Form,
  Alert,
  List,
  Empty,
  Result
} from 'antd';
import { 
  PlusOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined,
  PlayCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useProjectStore } from '../store/project';
import * as fieldMappingService from '../services/fieldMapping';
import { getDbSchemas } from '../services/dbSchema';
import type { 
  FieldMappingSuggestion, 
  FieldMappingCandidate,
  FieldMappingBatchApplyItem,
  AsyncTask,
  AsyncTaskCreateRequest,
  TaskProgress
} from '../services/fieldMapping';
import type { FieldMapping } from '../types';
import { FieldMappingStageProgress } from '../components/FieldMappingStageProgress';

const { TabPane } = Tabs;

const FieldMappingSuggestions: React.FC = () => {
  const navigate = useNavigate();
  const { currentProject, currentVersion } = useProjectStore();
  const [suggestions, setSuggestions] = useState<FieldMappingSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
  const [selectedCandidates, setSelectedCandidates] = useState<Record<number, FieldMappingCandidate | null>>({});
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedSuggestion, setSelectedSuggestion] = useState<FieldMappingSuggestion | null>(null);
  const [includePaths, setIncludePaths] = useState(true);
  const [includeQuery, setIncludeQuery] = useState(true);
  const [includeBody, setIncludeBody] = useState(true);
  
  // 异步任务相关状态
  const [taskModalVisible, setTaskModalVisible] = useState(false);
  const [progressModalVisible, setProgressModalVisible] = useState(false);
  const [currentTask, setCurrentTask] = useState<AsyncTask | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  const [useAi, setUseAi] = useState(true);
  const [aiHighPriority, setAiHighPriority] = useState(true);
  const [aiMediumPriority, setAiMediumPriority] = useState(true);
  const [aiLowPriority, setAiLowPriority] = useState(false);
  
  // 数据结构状态
  const [schemaList, setSchemaList] = useState<any[]>([]);
  
  // 高置信度阈值
  const HIGH_CONFIDENCE_THRESHOLD = 0.85;
  // 中等置信度阈值
  const MEDIUM_CONFIDENCE_THRESHOLD = 0.60;

  // 获取数据结构列表
  const fetchSchemas = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      setSchemaList([]);
      return;
    }
    try {
      const res = await getDbSchemas({
        project_id: currentProject.id,
        version_id: currentVersion.id
      });
      setSchemaList(res.data?.items || []);
    } catch (error: any) {
      console.error('获取数据结构失败:', error);
      setSchemaList([]);
    }
  };

  // 初始化时获取数据结构列表
  useEffect(() => {
    if (currentProject?.id && currentVersion?.id) {
      fetchSchemas();
    }
  }, [currentProject?.id, currentVersion?.id]);

  // 获取建议
  const fetchSuggestions = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    // 检查是否有数据结构
    if (schemaList.length === 0) {
      message.warning('当前版本尚未导入数据库结构，请先在"版本中心-数据结构"导入结构后再生成映射建议');
      return;
    }

    setLoading(true);
    try {
      const response = await fieldMappingService.suggestFieldMappings(
        { include_paths: includePaths, include_query: includeQuery, include_body: includeBody },
        { project_id: currentProject.id, version_id: currentVersion.id }
      );
      
      if (response.code === 0) {
        setSuggestions(response.data?.items || []);
        message.success(`生成了 ${response.data?.items?.length || 0} 个映射建议`);
      } else {
        message.error(response.message || '获取建议失败');
      }
    } catch (error: any) {
      console.error('获取建议失败:', error);
      message.error(error.message || '获取建议失败');
    } finally {
      setLoading(false);
    }
  };

  // 创建异步任务
  const handleCreateTask = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    // 检查是否有数据结构
    if (schemaList.length === 0) {
      message.warning('当前版本尚未导入数据库结构，请先在"版本中心-数据结构"导入结构后再生成映射建议');
      return;
    }

    const data: AsyncTaskCreateRequest = {
      include_paths: includePaths,
      include_query: includeQuery,
      include_body: includeBody,
      use_ai: useAi,
      ai_config: {
        high_priority_enabled: aiHighPriority,
        medium_priority_enabled: aiMediumPriority,
        low_priority_enabled: aiLowPriority
      }
    };

    setLoading(true);
    try {
      const response = await fieldMappingService.createFieldMappingSuggestTask(
        data,
        { project_id: currentProject.id, version_id: currentVersion.id }
      );

      if (response.code === 0 && response.data) {
        const taskId = response.data.task_id;
        message.success(`任务已创建，预计处理时间约 ${Math.ceil((response.data.estimated_duration || 0) / 60)} 分钟`);
        setTaskModalVisible(false);
        
        // 开始轮询任务进度
        startPolling(taskId);
      } else {
        message.error(response.message || '创建任务失败');
      }
    } catch (error: any) {
      console.error('创建任务失败:', error);
      message.error(error.message || '创建任务失败');
    } finally {
      setLoading(false);
    }
  };

  // 开始轮询任务进度
  const startPolling = (taskId: number) => {
    // 先获取一次任务信息
    fetchTaskProgress(taskId);
    
    // 每3秒轮询一次
    const interval = setInterval(() => {
      fetchTaskProgress(taskId);
    }, 3000);
    
    setPollingInterval(interval);
    setProgressModalVisible(true);
  };

  // 获取任务进度
  const fetchTaskProgress = async (taskId: number) => {
    try {
      const response = await fieldMappingService.getAsyncTask(taskId);
      
      if (response.code === 0 && response.data) {
        setCurrentTask(response.data);
        
        // 如果任务完成或失败，停止轮询
        if (response.data.status === 'completed' || response.data.status === 'failed' || response.data.status === 'cancelled') {
          if (pollingInterval) {
            clearInterval(pollingInterval);
            setPollingInterval(null);
          }
          
          if (response.data.status === 'completed') {
            message.success('任务完成');
            // 加载结果
            loadTaskResults(taskId);
          } else if (response.data.status === 'failed') {
            message.error(`任务失败: ${response.data.error_message || '未知错误'}`);
          } else if (response.data.status === 'cancelled') {
            message.info('任务已取消');
          }
        }
      }
    } catch (error: any) {
      console.error('获取任务进度失败:', error);
    }
  };

  // 加载任务结果
  const loadTaskResults = async (taskId: number) => {
    try {
      const response = await fieldMappingService.getFieldMappingSuggestions(taskId);
      
      if (response.code === 0 && response.data) {
        setSuggestions(response.data.items || []);
      }
    } catch (error: any) {
      console.error('加载任务结果失败:', error);
      message.error(error.message || '加载结果失败');
    }
  };

  // 取消任务
  const handleCancelTask = async () => {
    if (!currentTask) return;

    try {
      const response = await fieldMappingService.cancelAsyncTask(currentTask.id);
      
      if (response.code === 0) {
        message.success('任务已取消');
        if (pollingInterval) {
          clearInterval(pollingInterval);
          setPollingInterval(null);
        }
        setProgressModalVisible(false);
      } else {
        message.error(response.message || '取消任务失败');
      }
    } catch (error: any) {
      console.error('取消任务失败:', error);
      message.error(error.message || '取消任务失败');
    }
  };

  // 关闭进度对话框
  const handleCloseProgressModal = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    setProgressModalVisible(false);
  };

  // 组件卸载时清理轮询
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  // 获取阶段状态颜色
  const getStageStatus = (stageName: string) => {
    if (!currentTask?.stages) return 'wait';
    
    const stage = currentTask.stages.find(s => s.name === stageName);
    if (!stage) return 'wait';
    
    if (stage.status === 'completed') return 'finish';
    if (stage.status === 'running') return 'process';
    if (stage.status === 'failed') return 'error';
    return 'wait';
  };

  // 获取阶段进度百分比
  const getStageProgress = (stageName: string): number => {
    if (!currentTask?.stages) return 0;
    
    const stage = currentTask.stages.find(s => s.name === stageName);
    if (!stage) return 0;
    
    return stage.progress || 0;
  };

  // 获取阶段进度状态
  const getStageProgressStatus = (stageName: string): 'success' | 'exception' | 'active' | 'normal' => {
    const status = getStageStatus(stageName);
    if (status === 'finish') return 'success';
    if (status === 'error') return 'exception';
    if (status === 'process') return 'active';
    return 'normal';
  };

  // 获取当前阶段索引
  const getCurrentStageIndex = () => {
    if (!currentTask?.stages) return 0;
    
    for (let i = 0; i < currentTask.stages.length; i++) {
      if (currentTask.stages[i].status === 'running') {
        return i;
      }
    }
    
    // 如果没有正在运行的，检查是否有已完成的
    for (let i = currentTask.stages.length - 1; i >= 0; i--) {
      if (currentTask.stages[i].status === 'completed') {
        return i + 1;
      }
    }
    
    return 0;
  };

  // 批量确认选中的映射
  const handleBatchConfirm = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    const selectedSuggestions = suggestions.filter(s => selectedRowKeys.includes(s.definition_id));
    
    if (selectedSuggestions.length === 0) {
      message.warning('请先选择要确认的映射');
      return;
    }

    // 准备批量应用的数据
    const batchItems: FieldMappingBatchApplyItem[] = [];
    
    selectedSuggestions.forEach(suggestion => {
      const selectedCandidate = selectedCandidates[suggestion.definition_id];
      if (selectedCandidate) {
        batchItems.push({
          definition_id: suggestion.definition_id,
          api_field_path: suggestion.api_field_path,
          db_table: selectedCandidate.db_table,
          db_column: selectedCandidate.db_column,
          relation_type: 'direct',
          source: 'ai'
        });
      }
    });

    if (batchItems.length === 0) {
      message.warning('请为选中的映射选择候选字段');
      return;
    }

    try {
      const response = await fieldMappingService.batchApplyFieldMappings(
        { items: batchItems, mode: 'confirm' },
        { project_id: currentProject.id, version_id: currentVersion.id }
      );

      if (response.code === 0) {
        message.success(`成功确认了 ${response.data?.processed_count} 个映射`);
        setConfirmModalVisible(false);
        setSelectedRowKeys([]);
        // 重新获取建议
        fetchSuggestions();
      } else {
        message.error(response.message || '批量确认失败');
      }
    } catch (error: any) {
      console.error('批量确认失败:', error);
      message.error(error.message || '批量确认失败');
    }
  };

  // 单个确认映射
  const handleConfirmSingle = async (suggestion: FieldMappingSuggestion, candidate: FieldMappingCandidate) => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    try {
      const response = await fieldMappingService.batchApplyFieldMappings(
        {
          items: [{
            definition_id: suggestion.definition_id,
            api_field_path: suggestion.api_field_path,
            db_table: candidate.db_table,
            db_column: candidate.db_column,
            relation_type: 'direct',
            source: 'ai'
          }],
          mode: 'confirm'
        },
        { project_id: currentProject.id, version_id: currentVersion.id }
      );

      if (response.code === 0) {
        message.success('映射确认成功');
        // 重新获取建议
        fetchSuggestions();
      } else {
        message.error(response.message || '确认失败');
      }
    } catch (error: any) {
      console.error('确认映射失败:', error);
      message.error(error.message || '确认失败');
    }
  };

  // 显示详情模态框
  const showDetailModal = (suggestion: FieldMappingSuggestion) => {
    setSelectedSuggestion(suggestion);
    setDetailModalVisible(true);
  };

  // 表格列定义
  const columns = [
    {
      title: 'API',
      dataIndex: 'definition_path',
      key: 'api',
      render: (text: string, record: FieldMappingSuggestion) => (
        <div>
          <Tag color={getMethodColor(record.definition_method)}>
            {record.definition_method}
          </Tag>
          <span>{record.definition_path}</span>
        </div>
      )
    },
    {
      title: 'API 字段路径',
      dataIndex: 'api_field_path',
      key: 'api_field_path'
    },
    {
      title: '推荐表/字段',
      key: 'recommended',
      render: (_: any, record: FieldMappingSuggestion) => {
        if (record.candidates && record.candidates.length > 0) {
          const topCandidate = record.candidates[0];
          return (
            <div>
              <div><strong>{topCandidate.db_table}</strong>.{topCandidate.db_column}</div>
              <div style={{ fontSize: '12px', color: '#999' }}>
                置信度: {(topCandidate.score * 100).toFixed(1)}%
              </div>
            </div>
          );
        }
        return <span style={{ color: '#ccc' }}>无推荐</span>;
      }
    },
    {
      title: '置信度',
      key: 'confidence',
      render: (_: any, record: FieldMappingSuggestion) => {
        if (record.candidates && record.candidates.length > 0) {
          const topCandidate = record.candidates[0];
          let color = 'default';
          if (topCandidate.score >= HIGH_CONFIDENCE_THRESHOLD) {
            color = 'success';
          } else if (topCandidate.score >= MEDIUM_CONFIDENCE_THRESHOLD) {
            color = 'warning';
          } else {
            color = 'error';
          }
          
          return <Tag color={color}>{(topCandidate.score * 100).toFixed(1)}%</Tag>;
        }
        return <span>-</span>;
      }
    },
    {
      title: '原因',
      key: 'reasons',
      render: (_: any, record: FieldMappingSuggestion) => {
        if (record.candidates && record.candidates.length > 0) {
          const topCandidate = record.candidates[0];
          return (
            <Space wrap>
              {topCandidate.reasons.map((reason, idx) => (
                <Tag key={idx} color="blue">{reason}</Tag>
              ))}
            </Space>
          );
        }
        return <span>-</span>;
      }
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: FieldMappingSuggestion) => (
        <Space size="middle">
          <Button 
            type="link" 
            size="small"
            onClick={() => showDetailModal(record)}
          >
            详情
          </Button>
          {record.candidates && record.candidates.length > 0 && (
            <Button 
              type="primary" 
              size="small"
              onClick={() => handleConfirmSingle(record, record.candidates[0])}
            >
              确认
            </Button>
          )}
        </Space>
      )
    }
  ];

  // 获取HTTP方法对应的颜色
  const getMethodColor = (method: string) => {
    const colorMap: Record<string, string> = {
      GET: 'blue',
      POST: 'green',
      PUT: 'orange',
      DELETE: 'red',
      PATCH: 'volcano'
    };
    return colorMap[method] || 'default';
  };

  // 选择行的配置
  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
    getCheckboxProps: (record: FieldMappingSuggestion) => ({
      disabled: !record.candidates || record.candidates.length === 0,
      name: record.api_field_path,
    }),
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title="字段映射建议"
        extra={
          <Space>
            <Button 
              icon={<SyncOutlined />} 
              onClick={() => setTaskModalVisible(true)}
              loading={loading}
              type="primary"
            >
              生成映射建议（异步）
            </Button>
            <Button 
              icon={<SyncOutlined />} 
              onClick={fetchSuggestions}
              loading={loading}
            >
              重新生成建议（同步）
            </Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => setConfirmModalVisible(true)}
              disabled={selectedRowKeys.length === 0}
            >
              批量确认 ({selectedRowKeys.length})
            </Button>
          </Space>
        }
      >
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Checkbox 
              checked={includePaths} 
              onChange={e => setIncludePaths(e.target.checked)}
            >
              包含路径参数
            </Checkbox>
            <Checkbox 
              checked={includeQuery} 
              onChange={e => setIncludeQuery(e.target.checked)}
            >
              包含查询参数
            </Checkbox>
            <Checkbox 
              checked={includeBody} 
              onChange={e => setIncludeBody(e.target.checked)}
            >
              包含请求体参数
            </Checkbox>
          </Space>
        </div>

        {suggestions.length === 0 && !loading ? (
          <Result
            icon={<Empty description="" />}
            title="暂无映射建议"
            subTitle="点击上方「生成映射建议」按钮开始智能分析"
            extra={
              <Button 
                type="primary" 
                icon={<SyncOutlined />}
                onClick={() => setTaskModalVisible(true)}
              >
                立即生成
              </Button>
            }
          />
        ) : (
          <Table
            rowSelection={rowSelection}
            columns={columns}
            dataSource={suggestions}
            rowKey="definition_id"
            loading={loading}
            pagination={{
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 条`,
            }}
          />
        )}
      </Card>

      {/* 任务创建模态框 */}
      <Modal
        title="生成字段映射建议"
        open={taskModalVisible}
        onCancel={() => setTaskModalVisible(false)}
        onOk={handleCreateTask}
        okText="开始生成"
        cancelText="取消"
        confirmLoading={loading}
        width={600}
      >
        <Form layout="vertical">
          <Form.Item label="使用AI推荐">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Switch checked={useAi} onChange={setUseAi} />
              <span style={{ fontSize: 12, color: '#999' }}>
                启用AI将提高推荐准确率，但会增加处理时间约10分钟
              </span>
            </Space>
          </Form.Item>

          <Form.Item label="包含参数类型">
            <Space direction="vertical">
              <Checkbox checked={includePaths} onChange={e => setIncludePaths(e.target.checked)}>
                路径参数
              </Checkbox>
              <Checkbox checked={includeQuery} onChange={e => setIncludeQuery(e.target.checked)}>
                查询参数
              </Checkbox>
              <Checkbox checked={includeBody} onChange={e => setIncludeBody(e.target.checked)}>
                请求体参数
              </Checkbox>
            </Space>
          </Form.Item>

          <Form.Item label="AI优先级配置">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Checkbox checked={aiHighPriority} onChange={e => setAiHighPriority(e.target.checked)}>
                高优先级（ID字段、语义冲突）
              </Checkbox>
              <Checkbox checked={aiMediumPriority} onChange={e => setAiMediumPriority(e.target.checked)}>
                中优先级（中等置信度）
              </Checkbox>
              <Checkbox checked={aiLowPriority} onChange={e => setAiLowPriority(e.target.checked)}>
                低优先级（通用字段）
              </Checkbox>
            </Space>
          </Form.Item>

          <Alert
            message="预计处理时间"
            description={useAi ? "约10分钟，处理约1000个字段" : "约30秒，处理约1000个字段"}
            type="info"
            showIcon
          />
        </Form>
      </Modal>

      {/* 进度对话框 */}
      <Modal
        title="映射建议生成进度"
        open={progressModalVisible}
        onCancel={handleCloseProgressModal}
        footer={null}
        width={720}
      >
        {currentTask && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* 总体进度 */}
            <div>
              <div style={{ marginBottom: 8 }}>
                <strong>总体进度</strong>
                <span style={{ marginLeft: 16, color: '#999' }}>
                  {currentTask.progress}%
                </span>
              </div>
              <Progress 
                percent={currentTask.progress} 
                status={currentTask.status === 'failed' ? 'exception' : currentTask.status === 'completed' ? 'success' : 'active'}
              />
              {currentTask.progress_message && (
                <div style={{ marginTop: 8, color: '#999' }}>{currentTask.progress_message}</div>
              )}
            </div>

            {/* 统计信息 */}
            {currentTask.statistics && (
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic title="总字段数" value={currentTask.statistics.total_fields || 0} />
                </Col>
                <Col span={6}>
                  <Statistic title="已处理" value={currentTask.statistics.processed || 0} />
                </Col>
                <Col span={6}>
                  <Statistic title="AI增强" value={currentTask.statistics.ai_enhanced || 0} />
                </Col>
                <Col span={6}>
                  <Statistic title="自动确认" value={currentTask.statistics.auto_confirmed || 0} />
                </Col>
              </Row>
            )}

            {/* 阶段进度 */}
            <div>
              <strong style={{ marginBottom: 12, display: 'block' }}>处理阶段</strong>
              <FieldMappingStageProgress
                taskId={currentTask.id}
                progress={currentTask as any}
                onRetry={async (stageNum) => {
                  // 重试后重新轮询任务进度
                  await fetchTaskProgress(currentTask.id);
                }}
                onResume={async () => {
                  // 继续执行后重新轮询任务进度
                  await fetchTaskProgress(currentTask.id);
                }}
                onReset={async () => {
                  // 重置后清空当前任务状态
                  setCurrentTask(null);
                }}
              />
            </div>

            {/* 筛选统计 */}
            {currentTask.status === 'running' && currentTask.statistics && (
              <div>
                <strong style={{ marginBottom: 8, display: 'block' }}>筛选统计</strong>
                <List
                  size="small"
                  dataSource={[
                    { label: '自动确认', count: currentTask.statistics.auto_confirmed || 0, color: 'green' },
                    { label: '高优先级AI', count: currentTask.statistics.ai_high || 0, color: 'red' },
                    { label: '中优先级AI', count: currentTask.statistics.ai_medium || 0, color: 'orange' },
                    { label: '低优先级AI', count: currentTask.statistics.ai_low || 0, color: 'blue' }
                  ]}
                  renderItem={item => (
                    <List.Item>
                      <Tag color={item.color}>{item.label}</Tag>
                      <span>{item.count}个字段</span>
                    </List.Item>
                  )}
                />
              </div>
            )}

            {/* 操作按钮 */}
            {currentTask.status === 'completed' && (
              <Space>
                <Button type="primary" onClick={() => {
                  handleCloseProgressModal();
                }}>
                  查看结果
                </Button>
              </Space>
            )}

            {currentTask.status === 'running' && (
              <Button danger onClick={handleCancelTask}>
                取消任务
              </Button>
            )}

            {currentTask.status === 'failed' && (
              <Alert
                message="处理失败"
                description={currentTask.error_message}
                type="error"
                showIcon
              />
            )}
          </Space>
        )}
      </Modal>

      {/* 批量确认模态框 */}
      <Modal
        title="批量确认映射"
        open={confirmModalVisible}
        onCancel={() => setConfirmModalVisible(false)}
        onOk={handleBatchConfirm}
        okText="确认应用"
        cancelText="取消"
      >
        <p>您选择了 {selectedRowKeys.length} 个映射建议，确认后将自动创建字段映射关系。</p>
        <p>高置信度（≥{HIGH_CONFIDENCE_THRESHOLD*100}%）的映射将被自动确认。</p>
      </Modal>

      {/* 详情模态框 */}
      <Modal
        title="映射详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={800}
      >
        {selectedSuggestion && (
          <div>
            <Descriptions title="API 信息" bordered column={2} size="small">
              <Descriptions.Item label="方法">
                <Tag color={getMethodColor(selectedSuggestion.definition_method)}>
                  {selectedSuggestion.definition_method}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="路径">{selectedSuggestion.definition_path}</Descriptions.Item>
              <Descriptions.Item label="字段路径">{selectedSuggestion.api_field_path}</Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 24 }}>
              <h3>候选映射列表</h3>
              {selectedSuggestion.candidates && selectedSuggestion.candidates.length > 0 ? (
                <div>
                  {selectedSuggestion.candidates.map((candidate, idx) => (
                    <Card 
                      key={idx} 
                      size="small" 
                      style={{ 
                        marginBottom: 12,
                        borderLeft: candidate.score >= HIGH_CONFIDENCE_THRESHOLD ? '4px solid #52c41a' : 
                                    candidate.score >= MEDIUM_CONFIDENCE_THRESHOLD ? '4px solid #faad14' : '4px solid #ff4d4f'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <strong>{candidate.db_table}.{candidate.db_column}</strong>
                          <div style={{ marginTop: 4 }}>
                            <Tag color={
                              candidate.score >= HIGH_CONFIDENCE_THRESHOLD ? 'success' : 
                              candidate.score >= MEDIUM_CONFIDENCE_THRESHOLD ? 'warning' : 'error'
                            }>
                              置信度: {(candidate.score * 100).toFixed(1)}%
                            </Tag>
                            <Space style={{ marginLeft: 8 }}>
                              {candidate.reasons.map((reason, i) => (
                                <Tag key={i} color="blue">{reason}</Tag>
                              ))}
                            </Space>
                          </div>
                        </div>
                        <Button 
                          type="primary"
                          size="small"
                          onClick={() => handleConfirmSingle(selectedSuggestion, candidate)}
                        >
                          确认此映射
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '24px', color: '#999' }}>
                  没有找到合适的候选映射
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default FieldMappingSuggestions;