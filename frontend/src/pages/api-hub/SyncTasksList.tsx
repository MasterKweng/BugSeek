/**
 * 同步任务列表页面（V2.0 层级一 - API 资产库）
 * 符合前端代码规范：
 * 1. 防止重复提交：按钮加载状态
 * 2. 空值防御：使用可选链和默认值
 * 3. 友好异常提示：统一错误处理
 */
import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Space,
  Select,
  Input,
  Tag,
  Modal,
  Form,
  message,
  Card,
  Row,
  Col,
  Tooltip,
  Drawer,
  Progress,
  Alert,
  Tabs,
  Checkbox,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EyeOutlined,
  DeleteOutlined,
  StopOutlined,
  SyncOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import api from '../../services/api';

interface SyncTask {
  id: number;
  project_id: number;
  name: string;
  source_type: string;
  source_url: string | null;
  source_version: string | null;
  task_id: string | null;
  status: string;
  progress: number;
  total_count: number;
  added_count: number;
  updated_count: number;
  deleted_count: number;
  conflict_count: number;
  error_message: string | null;
  execution_log: any[];
  diff_data: any | null;
  impact_analysis: any | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  created_by: number | null;
}

const SyncTasksList: React.FC = () => {
  // 状态管理
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<SyncTask[]>([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // 筛选条件
  const [filters, setFilters] = useState({
    status: undefined as string | undefined,
    source_type: undefined as string | undefined,
  });

  // 弹窗状态
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [reviewModalVisible, setReviewModalVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<SyncTask | null>(null);
  const [selectedOperations, setSelectedOperations] = useState<any[]>([]);
  const [applyingChanges, setApplyingChanges] = useState(false);

  const [form] = Form.useForm();

  // 获取同步任务列表
  const fetchTasks = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        skip: String((pagination.current - 1) * pagination.pageSize),
        limit: String(pagination.pageSize),
      });

      if (filters.status) params.append('status', filters.status);
      if (filters.source_type) params.append('source_type', filters.source_type);

      const response = await api.get(`/sync-tasks?${params}`);

      if (response.code === 0) {
        setDataSource(response.data.items || []);
        setTotal(response.data.total || 0);
      } else {
        message.error(response.message || '获取数据失败');
      }
    } catch (error) {
      console.error('获取同步任务列表失败:', error);
      message.error('获取数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [pagination, filters.status, filters.source_type]);

  // 创建同步任务
  const handleCreate = async (values: any) => {
    setLoading(true);
    try {
      const response = await api.post('/sync-tasks', values);

      if (response.code === 0) {
        message.success('创建成功');
        setCreateModalVisible(false);
        form.resetFields();
        fetchTasks();
      } else {
        message.error(response.message || '创建失败');
      }
    } catch (error) {
      console.error('创建失败:', error);
      message.error('创建失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 取消同步任务
  const handleCancel = async (record: SyncTask) => {
    try {
      const response = await api.post(`/sync-tasks/${record.id}/cancel`);

      if (response.code === 0) {
        message.success('任务已取消');
        fetchTasks();
      } else {
        message.error(response.message || '取消失败');
      }
    } catch (error) {
      console.error('取消失败:', error);
      message.error('取消失败，请稍后重试');
    }
  };

  // 处理变更
  const handleOperationToggle = (
    type: string,
    method: string,
    path: string,
    checked: boolean,
    strategy?: string
  ) => {
    setSelectedOperations(prev => {
      if (checked) {
        return [...prev, { type, method, path, strategy: strategy || 'overwrite' }];
      } else {
        return prev.filter(op => !(op.type === type && op.method === method && op.path === path));
      }
    });
  };

  const handleApplyChanges = async () => {
    if (!currentRecord) return;

    setApplyingChanges(true);
    try {
      const response = await api.post(`/sync-tasks/${currentRecord.id}/apply`, {
        operations: selectedOperations
      });

      if (response.code === 0) {
        message.success('变更应用成功');
        setReviewModalVisible(false);
        fetchTasks();
      } else {
        message.error(response.message || '应用变更失败');
      }
    } catch (error) {
      console.error('应用变更失败:', error);
      message.error('应用变更失败，请稍后重试');
    } finally {
      setApplyingChanges(false);
    }
  };

  const handleReviewModalOpen = (record: SyncTask) => {
    setCurrentRecord(record);
    // 默认选中所有新增和更新的接口
    const defaults: any[] = [];
    
    if (record.diff_data?.added) {
      record.diff_data.added.forEach((item: any) => {
        defaults.push({ type: 'add', method: item.method, path: item.path });
      });
    }
    
    if (record.diff_data?.changed) {
      record.diff_data.changed.forEach((item: any) => {
        defaults.push({ type: 'update', method: item.method, path: item.path, strategy: 'overwrite' });
      });
    }
    
    setSelectedOperations(defaults);
    setReviewModalVisible(true);
  };

  // AI 自动修复
  const handleAIAutoFix = async (record: SyncTask) => {
    try {
      const response = await api.post(`/sync-tasks/${record.id}/ai-auto-fix`);

      if (response.code === 0) {
        message.success('AI 自动修复成功');
        // 显示修复结果的弹窗
        Modal.info({
          title: 'AI 自动修复结果',
          width: 800,
          content: (
            <div>
              <p>修复了 {response.data.fixes?.length || 0} 个用例</p>
              {response.data.fixes?.map((fix: any, index: number) => (
                <div key={index} style={{ marginBottom: 8 }}>
                  <Tag color="blue">{fix.case_name}</Tag>
                  <span> - {fix.fix_type}</span>
                </div>
              ))}
            </div>
          )
        });
        fetchTasks();
      } else {
        message.error(response.message || 'AI 自动修复失败');
      }
    } catch (error) {
      console.error('AI 自动修复失败:', error);
      message.error('AI 自动修复失败，请稍后重试');
    }
  };

  // 删除同步任务
  const handleDelete = async (record: SyncTask) => {
    try {
      const response = await api.delete(`/sync-tasks/${record.id}`);

      if (response.code === 0) {
        message.success('删除成功');
        fetchTasks();
      } else {
        message.error(response.message || '删除失败');
      }
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请稍后重试');
    }
  };

  // 状态标签
  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { text: string; color: string }> = {
      pending: { text: '待处理', color: 'default' },
      running: { text: '运行中', color: 'processing' },
      completed: { text: '已完成', color: 'success' },
      failed: { text: '失败', color: 'error' },
      cancelled: { text: '已取消', color: 'default' },
    };
    const statusInfo = statusMap[status] || { text: status, color: 'default' };
    return <Tag color={statusInfo.color}>{statusInfo.text}</Tag>;
  };

  // 来源类型标签
  const getSourceTypeTag = (sourceType: string) => {
    const typeMap: Record<string, { text: string; color: string }> = {
      swagger: { text: 'Swagger', color: 'purple' },
      postman: { text: 'Postman', color: 'orange' },
      yapi: { text: 'YApi', color: 'blue' },
      manual: { text: '手动', color: 'green' },
    };
    const typeInfo = typeMap[sourceType] || { text: sourceType, color: 'default' };
    return <Tag color={typeInfo.color}>{typeInfo.text}</Tag>;
  };

  // 表格列定义
  const columns: ColumnsType<SyncTask> = [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
    },
    {
      title: '来源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 120,
      render: getSourceTypeTag,
      filters: [
        { text: 'Swagger', value: 'swagger' },
        { text: 'Postman', value: 'postman' },
        { text: 'YApi', value: 'yapi' },
      ],
    },
    {
      title: '来源版本',
      dataIndex: 'source_version',
      key: 'source_version',
      width: 120,
      render: (version: string | null) => version || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: getStatusTag,
      filters: [
        { text: '待处理', value: 'pending' },
        { text: '运行中', value: 'running' },
        { text: '已完成', value: 'completed' },
        { text: '失败', value: 'failed' },
      ],
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 150,
      render: (progress: number) => (
        <Progress percent={progress} size="small" />
      ),
    },
    {
      title: '变更统计',
      key: 'statistics',
      width: 150,
      render: (_: any, record: SyncTask) => (
        <Space direction="vertical" size={0}>
          <div>新增: <Tag color="green">{record.added_count}</Tag></div>
          <div>更新: <Tag color="blue">{record.updated_count}</Tag></div>
          <div>删除: <Tag color="red">{record.deleted_count}</Tag></div>
          <div>冲突: <Tag color="orange">{record.conflict_count}</Tag></div>
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (createdAt: string) => {
        const date = new Date(createdAt);
        return date.toLocaleString('zh-CN');
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right',
      render: (_: any, record: SyncTask) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => {
                setCurrentRecord(record);
                setDetailDrawerVisible(true);
              }}
            />
          </Tooltip>
          {record.status === 'completed' && record.diff_data && (
            <Tooltip title="处理变更">
              <Button
                type="link"
                size="small"
                icon={<SyncOutlined />}
                onClick={() => handleReviewModalOpen(record)}
              >
                处理变更
              </Button>
            </Tooltip>
          )}
          {record.status === 'running' && (
            <Tooltip title="取消任务">
              <Button
                type="link"
                size="small"
                icon={<StopOutlined />}
                onClick={() => handleCancel(record)}
              />
            </Tooltip>
          )}
          {record.status === 'completed' && record.conflict_count > 0 && (
            <Tooltip title="AI 自动修复">
              <Button
                type="link"
                size="small"
                icon={<RobotOutlined />}
                onClick={() => handleAIAutoFix(record)}
              />
            </Tooltip>
          )}
          {(record.status === 'completed' || record.status === 'failed' || record.status === 'cancelled') && (
            <Tooltip title="删除任务">
              <Popconfirm
                title="确认删除"
                description={`确定要删除同步任务 "${record.name}" 吗？`}
                onConfirm={() => handleDelete(record)}
                okText="确定"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button
                  type="link"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                />
              </Popconfirm>
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        {/* 顶部操作栏 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={4}>
            <Select
              placeholder="状态筛选"
              style={{ width: '100%' }}
              value={filters.status}
              onChange={(value) => setFilters({ ...filters, status: value })}
              allowClear
            >
              <Select.Option value="pending">待处理</Select.Option>
              <Select.Option value="running">运行中</Select.Option>
              <Select.Option value="completed">已完成</Select.Option>
              <Select.Option value="failed">失败</Select.Option>
            </Select>
          </Col>
          <Col span={4}>
            <Select
              placeholder="来源类型"
              style={{ width: '100%' }}
              value={filters.source_type}
              onChange={(value) => setFilters({ ...filters, source_type: value })}
              allowClear
            >
              <Select.Option value="swagger">Swagger</Select.Option>
              <Select.Option value="postman">Postman</Select.Option>
              <Select.Option value="yapi">YApi</Select.Option>
            </Select>
          </Col>
          <Col span={16} style={{ textAlign: 'right' }}>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchTasks}
                loading={loading}
              >
                刷新
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  form.resetFields();
                  setCreateModalVisible(true);
                }}
              >
                新建同步任务
              </Button>
            </Space>
          </Col>
        </Row>

        {/* 数据表格 */}
        <Table
          columns={columns}
          dataSource={dataSource}
          rowKey="id"
          loading={loading}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setPagination({ current: page, pageSize: pageSize || 20 });
            },
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* 创建弹窗 */}
      <Modal
        title="新建同步任务"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setCreateModalVisible(false)}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={loading}
            onClick={() => form.submit()}
          >
            创建
          </Button>,
        ]}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="name"
            label="任务名称"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="例如: Swagger 同步任务" />
          </Form.Item>
          <Form.Item
            name="source_type"
            label="来源类型"
            rules={[{ required: true, message: '请选择来源类型' }]}
          >
            <Select placeholder="请选择来源类型">
              <Select.Option value="swagger">Swagger</Select.Option>
              <Select.Option value="postman">Postman</Select.Option>
              <Select.Option value="yapi">YApi</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="source_url"
            label="来源URL"
            rules={[{ required: true, message: '请输入来源URL' }]}
          >
            <Input placeholder="例如: https://api.example.com/swagger.json" />
          </Form.Item>
          <Form.Item
            name="source_version"
            label="来源版本"
          >
            <Input placeholder="例如: v1.2.3" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 详情抽屉 */}
      <Drawer
        title="同步任务详情"
        placement="right"
        width={720}
        open={detailDrawerVisible}
        onClose={() => setDetailDrawerVisible(false)}
      >
        {currentRecord && (
          <div>
            <Row gutter={[16, 16]}>
              <Col span={24}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>任务名称</div>
                <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{currentRecord.name}</div>
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>来源类型</div>
                {getSourceTypeTag(currentRecord.source_type)}
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>状态</div>
                {getStatusTag(currentRecord.status)}
              </Col>
              <Col span={24}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>来源URL</div>
                <div>{currentRecord.source_url || '-'}</div>
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>来源版本</div>
                <div>{currentRecord.source_version || '-'}</div>
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>任务ID</div>
                <div>{currentRecord.task_id || '-'}</div>
              </Col>
              <Col span={24}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>进度</div>
                <Progress percent={currentRecord.progress} />
              </Col>
              <Col span={24}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>变更统计</div>
                <Row gutter={16}>
                  <Col span={6}>
                    <Card size="small">
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>
                        {currentRecord.added_count}
                      </div>
                      <div style={{ color: 'var(--text-tertiary)' }}>新增</div>
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small">
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>
                        {currentRecord.updated_count}
                      </div>
                      <div style={{ color: 'var(--text-tertiary)' }}>更新</div>
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small">
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ff4d4f' }}>
                        {currentRecord.deleted_count}
                      </div>
                      <div style={{ color: 'var(--text-tertiary)' }}>删除</div>
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small">
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fa8c16' }}>
                        {currentRecord.conflict_count}
                      </div>
                      <div style={{ color: 'var(--text-tertiary)' }}>冲突</div>
                    </Card>
                  </Col>
                </Row>
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>开始时间</div>
                <div>{currentRecord.started_at ? new Date(currentRecord.started_at).toLocaleString('zh-CN') : '-'}</div>
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>完成时间</div>
                <div>{currentRecord.completed_at ? new Date(currentRecord.completed_at).toLocaleString('zh-CN') : '-'}</div>
              </Col>
              {currentRecord.error_message && (
                <Col span={24}>
                  <Alert
                    message="错误信息"
                    description={currentRecord.error_message}
                    type="error"
                    showIcon
                  />
                </Col>
              )}
              {currentRecord.execution_log && currentRecord.execution_log.length > 0 && (
                <Col span={24}>
                  <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>执行日志</div>
                  <div style={{ background: 'var(--bg-tertiary)', padding: '12px', borderRadius: '4px', maxHeight: '300px', overflowY: 'auto' }}>
                    {currentRecord.execution_log.map((log: any, index: number) => (
                      <div key={index} style={{ marginBottom: '4px', fontSize: '12px' }}>
                        {log.timestamp && <span style={{ color: 'var(--text-tertiary)' }}>[{new Date(log.timestamp).toLocaleTimeString()}]</span>}
                        <span>{log.message}</span>
                      </div>
                    ))}
                  </div>
                </Col>
              )}
              {currentRecord.diff_data && (
                <Col span={24}>
                  <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>变更详情</div>
                  <Tabs defaultActiveKey="added">
                    <Tabs.TabPane tab={`新增 (${currentRecord.diff_data.summary?.added_count || 0})`} key="added">
                      {currentRecord.diff_data.added?.map((item: any, index: number) => (
                        <div key={index} style={{ padding: '8px', background: 'rgba(82, 196, 26, 0.1)', marginBottom: '4px', borderRadius: '4px' }}>
                          <Tag color="green">{item.method}</Tag>
                          <span style={{ fontWeight: 'bold' }}>{item.path}</span>
                          <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                            {item.summary || '无描述'}
                          </div>
                        </div>
                      ))}
                    </Tabs.TabPane>
                    <Tabs.TabPane tab={`删除 (${currentRecord.diff_data.summary?.removed_count || 0})`} key="removed">
                      {currentRecord.diff_data.removed?.map((item: any, index: number) => (
                        <div key={index} style={{ padding: '8px', background: 'var(--bg-elevated)', marginBottom: '4px', borderRadius: '4px' }}>
                          <Tag color="red">{item.method}</Tag>
                          <span style={{ fontWeight: 'bold' }}>{item.path}</span>
                          <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                            {item.summary || '无描述'}
                          </div>
                        </div>
                      ))}
                    </Tabs.TabPane>
                    <Tabs.TabPane tab={`变更 (${currentRecord.diff_data.summary?.changed_count || 0})`} key="changed">
                      {currentRecord.diff_data.changed?.map((item: any, index: number) => (
                        <div key={index} style={{ padding: '8px', background: 'var(--bg-elevated)', marginBottom: '4px', borderRadius: '4px' }}>
                          <Tag color="orange">{item.method}</Tag>
                          <span style={{ fontWeight: 'bold' }}>{item.path}</span>
                          <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                            {item.summary || '无描述'}
                          </div>
                          {item.diff?.summary?.total_changes > 0 && (
                            <div style={{ marginTop: '4px', fontSize: '12px' }}>
                              <span style={{ color: '#fa8c16' }}>Schema 变更: {item.diff.summary.total_changes} 处</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </Tabs.TabPane>
                  </Tabs>
                </Col>
              )}
              {currentRecord.impact_analysis && (
                <Col span={24}>
                  <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>影响分析</div>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Card size="small" title="受影响的用例">
                        <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1890ff' }}>
                          {currentRecord.impact_analysis.summary?.affected_case_count || 0}
                        </div>
                        <div style={{ color: 'var(--text-tertiary)' }}>用例</div>
                        {currentRecord.impact_analysis.affected_cases?.map((case_item: any, index: number) => (
                          <div key={index} style={{ marginTop: '8px', padding: '8px', background: '#f0f5ff', borderRadius: '4px' }}>
                            <div style={{ fontWeight: 'bold' }}>{case_item.case_name}</div>
                            <Tag color={case_item.priority === 'P0' ? 'red' : case_item.priority === 'P1' ? 'orange' : 'blue'}>
                              {case_item.priority}
                            </Tag>
                            <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                              变更字段: {case_item.changed_fields?.join(', ') || '无'}
                            </div>
                          </div>
                        ))}
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card size="small" title="受影响的场景">
                        <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#52c41a' }}>
                          {currentRecord.impact_analysis.summary?.affected_scenario_count || 0}
                        </div>
                        <div style={{ color: 'var(--text-tertiary)' }}>场景</div>
                        {currentRecord.impact_analysis.affected_scenarios?.map((scenario_item: any, index: number) => (
                          <div key={index} style={{ marginTop: '8px', padding: '8px', background: 'rgba(82, 196, 26, 0.1)', borderRadius: '4px' }}>
                            <div style={{ fontWeight: 'bold' }}>{scenario_item.scenario_name}</div>
                            <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                              接口数: {scenario_item.endpoint_count}
                            </div>
                          </div>
                        ))}
                      </Card>
                    </Col>
                  </Row>
                </Col>
              )}
            </Row>
          </div>
        )}
      </Drawer>

      {/* 变更审核模态框 */}
      <Modal
        title="变更审核"
        open={reviewModalVisible}
        onCancel={() => {
          setReviewModalVisible(false);
          setSelectedOperations([]);
        }}
        footer={[
          <Button key="cancel" onClick={() => {
            setReviewModalVisible(false);
            setSelectedOperations([]);
          }}>
            取消
          </Button>,
          <Button
            key="apply"
            type="primary"
            loading={applyingChanges}
            onClick={handleApplyChanges}
            disabled={selectedOperations.length === 0}
          >
            确认应用变更 ({selectedOperations.length})
          </Button>,
        ]}
        width={1000}
      >
        {currentRecord && currentRecord.diff_data && (
          <div>
            {/* 变更统计 */}
            <Row gutter={16} style={{ marginBottom: 24 }}>
              <Col span={8}>
                <Card size="small">
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>
                    {currentRecord.diff_data.added?.length || 0}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)' }}>新增</div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>
                    {currentRecord.diff_data.changed?.length || 0}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)' }}>更新</div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ff4d4f' }}>
                    {currentRecord.diff_data.removed?.length || 0}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)' }}>删除</div>
                </Card>
              </Col>
            </Row>

            {/* 变更列表 */}
            <Tabs defaultActiveKey="added">
              <Tabs.TabPane tab={`新增 (${currentRecord.diff_data.added?.length || 0})`} key="added">
                <Table
                  dataSource={currentRecord.diff_data.added || []}
                  rowKey={(record: any) => `${record.method}:${record.path}`}
                  pagination={false}
                  size="small"
                  columns={[
                    {
                      title: '操作',
                      dataIndex: 'method',
                      key: 'method',
                      width: 80,
                      render: (method: string) => <Tag color="green">{method.toUpperCase()}</Tag>
                    },
                    {
                      title: '路径',
                      dataIndex: 'path',
                      key: 'path'
                    },
                    {
                      title: '描述',
                      dataIndex: 'summary',
                      key: 'summary',
                      ellipsis: true
                    },
                    {
                      title: '是否应用',
                      key: 'action',
                      width: 100,
                      render: (_: any, record: any) => (
                        <Checkbox
                          checked={selectedOperations.some(
                            op => op.type === 'add' && op.method === record.method && op.path === record.path
                          )}
                          onChange={(e) => handleOperationToggle('add', record.method, record.path, e.target.checked)}
                        />
                      )
                    }
                  ]}
                />
              </Tabs.TabPane>

              <Tabs.TabPane tab={`更新 (${currentRecord.diff_data.changed?.length || 0})`} key="changed">
                <Table
                  dataSource={currentRecord.diff_data.changed || []}
                  rowKey={(record: any) => `${record.method}:${record.path}`}
                  pagination={false}
                  size="small"
                  columns={[
                    {
                      title: '操作',
                      dataIndex: 'method',
                      key: 'method',
                      width: 80,
                      render: (method: string) => <Tag color="blue">{method.toUpperCase()}</Tag>
                    },
                    {
                      title: '路径',
                      dataIndex: 'path',
                      key: 'path'
                    },
                    {
                      title: '描述',
                      dataIndex: 'summary',
                      key: 'summary',
                      ellipsis: true
                    },
                    {
                      title: '更新策略',
                      key: 'strategy',
                      width: 120,
                      render: (_: any, record: any) => (
                        <Select
                          size="small"
                          style={{ width: '100%' }}
                          value={selectedOperations.find(
                            op => op.type === 'update' && op.method === record.method && op.path === record.path
                          )?.strategy || 'overwrite'}
                          onChange={(value) => {
                            setSelectedOperations(prev => prev.map(op => 
                              (op.type === 'update' && op.method === record.method && op.path === record.path)
                                ? { ...op, strategy: value }
                                : op
                            ));
                          }}
                        >
                          <Select.Option value="overwrite">覆盖</Select.Option>
                          <Select.Option value="merge">合并</Select.Option>
                        </Select>
                      )
                    },
                    {
                      title: '是否应用',
                      key: 'action',
                      width: 100,
                      render: (_: any, record: any) => (
                        <Checkbox
                          checked={selectedOperations.some(
                            op => op.type === 'update' && op.method === record.method && op.path === record.path
                          )}
                          onChange={(e) => handleOperationToggle('update', record.method, record.path, e.target.checked)}
                        />
                      )
                    }
                  ]}
                />
              </Tabs.TabPane>

              <Tabs.TabPane tab={`删除 (${currentRecord.diff_data.removed?.length || 0})`} key="removed">
                <Table
                  dataSource={currentRecord.diff_data.removed || []}
                  rowKey={(record: any) => `${record.method}:${record.path}`}
                  pagination={false}
                  size="small"
                  columns={[
                    {
                      title: '操作',
                      dataIndex: 'method',
                      key: 'method',
                      width: 80,
                      render: (method: string) => <Tag color="red">{method.toUpperCase()}</Tag>
                    },
                    {
                      title: '路径',
                      dataIndex: 'path',
                      key: 'path'
                    },
                    {
                      title: '描述',
                      dataIndex: 'summary',
                      key: 'summary',
                      ellipsis: true
                    },
                    {
                      title: '是否应用',
                      key: 'action',
                      width: 100,
                      render: (_: any, record: any) => (
                        <Checkbox
                          checked={selectedOperations.some(
                            op => op.type === 'remove' && op.method === record.method && op.path === record.path
                          )}
                          onChange={(e) => handleOperationToggle('remove', record.method, record.path, e.target.checked)}
                        />
                      )
                    }
                  ]}
                />
              </Tabs.TabPane>
            </Tabs>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default SyncTasksList;