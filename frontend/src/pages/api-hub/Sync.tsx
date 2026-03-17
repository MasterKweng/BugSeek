import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Space,
  Input,
  Select,
  Tag,
  Modal,
  Form,
  message,
  Card,
  Row,
  Col,
  Tooltip,
  Popconfirm,
  Drawer,
  Progress,
  Badge,
  Descriptions,
  Checkbox,
} from 'antd';
import {
  SearchOutlined,
  ReloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  SyncOutlined,
  StopOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useDebounce } from '../../hooks/useDebounce';

interface SyncTask {
  id: number;
  project_id: number;
  version_id: number | null;
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
  diff_data: any | null;  // 变更数据
  impact_analysis: any | null;  // 影响分析
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  created_by: number | null;
}

interface ApiResponse {
  code: number;
  message: string;
  data: any;
}

const Sync: React.FC = () => {
  // 状态管理
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<SyncTask[]>([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // 筛选条件
  const [filters, setFilters] = useState({
    status: undefined as string | undefined,
    source_type: undefined as string | undefined,
    keyword: '',
  });

  const debouncedKeyword = useDebounce(filters.keyword, 300);

  // 弹窗状态
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [reviewModalVisible, setReviewModalVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<SyncTask | null>(null);

  // 变更审核状态
  const [selectedOperations, setSelectedOperations] = useState<any[]>([]);
  const [applyingChanges, setApplyingChanges] = useState(false);

  const [form] = Form.useForm();

  // 获取同步任务列表
  const fetchSyncTasks = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        skip: String((pagination.current - 1) * pagination.pageSize),
        limit: String(pagination.pageSize),
      });

      if (filters.status) params.append('status', filters.status);
      if (filters.source_type) params.append('source_type', filters.source_type);
      if (debouncedKeyword) params.append('keyword', debouncedKeyword);

      const response = await fetch(`/api/v1/sync-tasks?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        setDataSource(result.data.items || []);
        setTotal(result.data.total || 0);
      } else {
        message.error(result.message || '获取数据失败');
      }
    } catch (error) {
      console.error('获取同步任务列表失败:', error);
      message.error('获取数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSyncTasks();
  }, [pagination, filters.status, filters.source_type, debouncedKeyword]);

  // 轮询进行中的任务
  useEffect(() => {
    const runningTasks = dataSource.filter(task => task.status === 'running');
    if (runningTasks.length > 0) {
      const interval = setInterval(() => {
        fetchSyncTasks();
      }, 3000); // 每3秒轮询一次

      return () => clearInterval(interval);
    }
  }, [dataSource]);

  // 创建同步任务
  const handleCreate = async (values: any) => {
    try {
      const response = await fetch('/api/v1/sync-tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(values),
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        message.success('同步任务创建成功');
        setCreateModalVisible(false);
        form.resetFields();
        fetchSyncTasks();
      } else {
        message.error(result.message || '创建失败');
      }
    } catch (error) {
      console.error('创建失败:', error);
      message.error('创建失败，请稍后重试');
    }
  };

  // 删除同步任务
  const handleDelete = async (record: SyncTask) => {
    try {
      const response = await fetch(`/api/v1/sync-tasks/${record.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        message.success('删除成功');
        fetchSyncTasks();
      } else {
        message.error(result.message || '删除失败');
      }
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请稍后重试');
    }
  };

  // 取消同步任务
  const handleCancel = async (record: SyncTask) => {
    try {
      const response = await fetch(`/api/v1/sync-tasks/${record.id}/cancel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        message.success('任务已取消');
        fetchSyncTasks();
      } else {
        message.error(result.message || '取消失败');
      }
    } catch (error) {
      console.error('取消失败:', error);
      message.error('取消失败，请稍后重试');
    }
  };

  // 处理变更操作选择
  const handleOperationToggle = (type: string, record: any, checked: boolean, strategy?: string) => {
    setSelectedOperations(prev => {
      const existingIndex = prev.findIndex(
        op => op.type === type && op.method === record.method && op.path === record.path
      );

      if (checked) {
        // 添加或更新操作
        if (existingIndex >= 0) {
          const updated = [...prev];
          updated[existingIndex] = {
            ...updated[existingIndex],
            strategy: strategy || updated[existingIndex].strategy
          };
          return updated;
        } else {
          return [...prev, {
            type,
            method: record.method,
            path: record.path,
            strategy: strategy || undefined
          }];
        }
      } else {
        // 移除操作
        return prev.filter(op =>
          !(op.type === type && op.method === record.method && op.path === record.path)
        );
      }
    });
  };

  // 应用变更
  const handleApplyChanges = async () => {
    if (!currentRecord) return;

    if (selectedOperations.length === 0) {
      message.warning('请至少选择一个变更操作');
      return;
    }

    setApplyingChanges(true);

    try {
      const response = await fetch(`/api/v1/sync-tasks/${currentRecord.id}/apply`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          operations: selectedOperations
        }),
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        message.success(`成功应用 ${result.data.applied_count} 个变更`);
        setReviewModalVisible(false);
        setSelectedOperations([]);
        fetchSyncTasks();
      } else {
        message.error(result.message || '应用变更失败');
      }
    } catch (error) {
      console.error('应用变更失败:', error);
      message.error('应用变更失败，请稍后重试');
    } finally {
      setApplyingChanges(false);
    }
  };

  // 状态标签
  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { text: string; color: string; icon?: React.ReactNode }> = {
      pending: { text: '待处理', color: 'default' },
      running: { text: '运行中', color: 'processing', icon: <SyncOutlined spin /> },
      completed: { text: '已完成', color: 'success' },
      failed: { text: '失败', color: 'error' },
      cancelled: { text: '已取消', color: 'default' },
    };
    const statusInfo = statusMap[status] || { text: status, color: 'default' };
    return (
      <Tag color={statusInfo.color} icon={statusInfo.icon}>
        {statusInfo.text}
      </Tag>
    );
  };

  // 来源类型标签
  const getSourceTypeTag = (sourceType: string) => {
    const typeMap: Record<string, { text: string; color: string }> = {
      swagger: { text: 'Swagger', color: 'green' },
      yapi: { text: 'YApi', color: 'blue' },
      postman: { text: 'Postman', color: 'orange' },
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
      render: (name: string, record: SyncTask) => (
        <div>
          <div style={{ fontWeight: 'bold' }}>{name}</div>
          {record.source_url && (
            <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
              {record.source_url}
            </div>
          )}
        </div>
      ),
    },
    {
      title: '来源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 100,
      render: getSourceTypeTag,
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
        { text: '已取消', value: 'cancelled' },
      ],
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 150,
      render: (progress: number) => (
        <Progress
          percent={progress}
          size="small"
          status={progress === 100 ? 'success' : 'active'}
        />
      ),
    },
    {
      title: '统计',
      key: 'stats',
      width: 150,
      render: (_: any, record: SyncTask) => (
        <div style={{ fontSize: '12px' }}>
          <div>总数: {record.total_count}</div>
          <div style={{ color: '#52c41a' }}>新增: {record.added_count}</div>
          <div style={{ color: '#1890ff' }}>更新: {record.updated_count}</div>
          <div style={{ color: '#ff4d4f' }}>删除: {record.deleted_count}</div>
          {record.conflict_count > 0 && (
            <div style={{ color: '#fa8c16' }}>冲突: {record.conflict_count}</div>
          )}
        </div>
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
      width: 240,
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
                onClick={() => {
                  setCurrentRecord(record);
                  setReviewModalVisible(true);
                }}
              >
                处理变更
              </Button>
            </Tooltip>
          )}
          {record.status === 'running' && (
            <Popconfirm
              title="确定要取消此任务吗？"
              onConfirm={() => handleCancel(record)}
              okText="确定"
              cancelText="取消"
            >
              <Tooltip title="取消任务">
                <Button
                  type="link"
                  size="small"
                  danger
                  icon={<StopOutlined />}
                />
              </Tooltip>
            </Popconfirm>
          )}
          {record.status !== 'pending' && record.status !== 'running' && (
            <Popconfirm
              title="确定要删除此任务吗？"
              onConfirm={() => handleDelete(record)}
              okText="确定"
              cancelText="取消"
            >
              <Tooltip title="删除任务">
                <Button
                  type="link"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                />
              </Tooltip>
            </Popconfirm>
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
          <Col span={6}>
            <Input
              placeholder="搜索任务名称"
              prefix={<SearchOutlined />}
              value={filters.keyword}
              onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
              allowClear
            />
          </Col>
          <Col span={3}>
            <Select
              placeholder="状态"
              style={{ width: '100%' }}
              value={filters.status}
              onChange={(value) => setFilters({ ...filters, status: value })}
              allowClear
            >
              <Select.Option value="pending">待处理</Select.Option>
              <Select.Option value="running">运行中</Select.Option>
              <Select.Option value="completed">已完成</Select.Option>
              <Select.Option value="failed">失败</Select.Option>
              <Select.Option value="cancelled">已取消</Select.Option>
            </Select>
          </Col>
          <Col span={3}>
            <Select
              placeholder="来源类型"
              style={{ width: '100%' }}
              value={filters.source_type}
              onChange={(value) => setFilters({ ...filters, source_type: value })}
              allowClear
            >
              <Select.Option value="swagger">Swagger</Select.Option>
              <Select.Option value="yapi">YApi</Select.Option>
              <Select.Option value="postman">Postman</Select.Option>
            </Select>
          </Col>
          <Col span={12} style={{ textAlign: 'right' }}>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchSyncTasks}
                loading={loading}
              >
                刷新
              </Button>
              <Button
                type="primary"
                icon={<CloudUploadOutlined />}
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
            创建任务
          </Button>,
        ]}
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
            <Input placeholder="例如: 同步用户服务接口文档" />
          </Form.Item>
          <Form.Item
            name="source_type"
            label="文档来源"
            rules={[{ required: true, message: '请选择文档来源' }]}
          >
            <Select placeholder="请选择文档来源">
              <Select.Option value="swagger">Swagger / OpenAPI</Select.Option>
              <Select.Option value="yapi">YApi</Select.Option>
              <Select.Option value="postman">Postman</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="source_url"
            label="文档URL"
            rules={[{ required: true, message: '请输入文档URL' }]}
          >
            <Input placeholder="例如: https://api.example.com/swagger.json" />
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
            <Descriptions bordered column={2} style={{ marginBottom: 24 }}>
              <Descriptions.Item label="任务名称" span={2}>{currentRecord.name}</Descriptions.Item>
              <Descriptions.Item label="来源类型">{getSourceTypeTag(currentRecord.source_type)}</Descriptions.Item>
              <Descriptions.Item label="状态">{getStatusTag(currentRecord.status)}</Descriptions.Item>
              <Descriptions.Item label="文档URL" span={2}>{currentRecord.source_url || '-'}</Descriptions.Item>
              <Descriptions.Item label="来源版本">{currentRecord.source_version || '-'}</Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(currentRecord.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              {currentRecord.started_at && (
                <Descriptions.Item label="开始时间">
                  {new Date(currentRecord.started_at).toLocaleString('zh-CN')}
                </Descriptions.Item>
              )}
              {currentRecord.completed_at && (
                <Descriptions.Item label="完成时间">
                  {new Date(currentRecord.completed_at).toLocaleString('zh-CN')}
                </Descriptions.Item>
              )}
            </Descriptions>

            <Card title="同步统计" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                <Col span={6}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{currentRecord.total_count}</div>
                    <div style={{ color: 'var(--text-tertiary)' }}>总数</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>{currentRecord.added_count}</div>
                    <div style={{ color: 'var(--text-tertiary)' }}>新增</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>{currentRecord.updated_count}</div>
                    <div style={{ color: 'var(--text-tertiary)' }}>更新</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ff4d4f' }}>{currentRecord.deleted_count}</div>
                    <div style={{ color: 'var(--text-tertiary)' }}>删除</div>
                  </div>
                </Col>
              </Row>
              {currentRecord.conflict_count > 0 && (
                <div style={{ marginTop: 16, padding: '12px', background: 'var(--bg-elevated)', borderRadius: '4px' }}>
                  <Badge count={currentRecord.conflict_count} style={{ backgroundColor: '#fa8c16', marginRight: 8 }} />
                  <span style={{ color: '#fa8c16' }}>接口存在冲突，需要手动处理</span>
                </div>
              )}
            </Card>

            {currentRecord.error_message && (
              <Card title="错误信息" style={{ marginBottom: 16 }}>
                <div style={{ color: '#ff4d4f' }}>{currentRecord.error_message}</div>
              </Card>
            )}

            {currentRecord.execution_log && currentRecord.execution_log.length > 0 && (
              <Card title="执行日志">
                <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                  {currentRecord.execution_log.map((log: any, index: number) => (
                    <div key={index} style={{ marginBottom: '8px', padding: '8px', background: 'var(--bg-tertiary)', borderRadius: '4px' }}>
                      <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '4px' }}>
                        {log.timestamp && new Date(log.timestamp).toLocaleString('zh-CN')}
                      </div>
                      <div style={{ color: log.level === 'error' ? '#ff4d4f' : '#333' }}>
                        {log.message}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}
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
        width={1000}
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
          >
            确认应用变更
          </Button>,
        ]}
      >
        {currentRecord && currentRecord.diff_data && (
          <div>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Card size="small">
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#52c41a' }}>
                    {currentRecord.diff_data.added?.length || 0}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)' }}>新增</div>
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1890ff' }}>
                    {currentRecord.diff_data.changed?.length || 0}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)' }}>更新</div>
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#ff4d4f' }}>
                    {currentRecord.diff_data.removed?.length || 0}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)' }}>删除</div>
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--text-tertiary)' }}>
                    {(currentRecord.diff_data.added?.length || 0) +
                     (currentRecord.diff_data.changed?.length || 0) +
                     (currentRecord.diff_data.removed?.length || 0)}
                  </div>
                  <div style={{ color: 'var(--text-tertiary)' }}>总计</div>
                </Card>
              </Col>
            </Row>

            {/* 新增接口 */}
            {currentRecord.diff_data.added && currentRecord.diff_data.added.length > 0 && (
              <Card title={`新增接口 (${currentRecord.diff_data.added.length})`} size="small" style={{ marginBottom: 16 }}>
                <Table
                  dataSource={currentRecord.diff_data.added}
                  rowKey={(record: any) => `${record.method}-${record.path}`}
                  size="small"
                  pagination={false}
                  columns={[
                    { title: '方法', dataIndex: 'method', width: 80, render: (method: string) => <Tag color="green">{method}</Tag> },
                    { title: '路径', dataIndex: 'path', ellipsis: true },
                    { title: '描述', dataIndex: 'summary', ellipsis: true },
                    {
                      title: '操作',
                      width: 120,
                      render: (_: any, record: any) => (
                        <Checkbox
                          checked={selectedOperations.some(op =>
                            op.type === 'add' && op.method === record.method && op.path === record.path
                          )}
                          onChange={(e) => handleOperationToggle('add', record, e.target.checked)}
                        >
                          {selectedOperations.some(op =>
                            op.type === 'add' && op.method === record.method && op.path === record.path
                          ) ? '已选择' : '添加'}
                        </Checkbox>
                      )
                    }
                  ]}
                />
              </Card>
            )}

            {/* 更新接口 */}
            {currentRecord.diff_data.changed && currentRecord.diff_data.changed.length > 0 && (
              <Card title={`更新接口 (${currentRecord.diff_data.changed.length})`} size="small" style={{ marginBottom: 16 }}>
                <Table
                  dataSource={currentRecord.diff_data.changed}
                  rowKey={(record: any) => `${record.method}-${record.path}`}
                  size="small"
                  pagination={false}
                  columns={[
                    { title: '方法', dataIndex: 'method', width: 80, render: (method: string) => <Tag color="blue">{method}</Tag> },
                    { title: '路径', dataIndex: 'path', ellipsis: true },
                    { title: '描述', dataIndex: 'summary', ellipsis: true },
                    {
                      title: '更新策略',
                      width: 180,
                      render: (_: any, record: any) => {
                        const op = selectedOperations.find(op =>
                          op.type === 'update' && op.method === record.method && op.path === record.path
                        );
                        return (
                          <Select
                            size="small"
                            style={{ width: '100%' }}
                            value={op?.strategy || ''}
                            onChange={(value) => handleOperationToggle('update', record, true, value)}
                            options={[
                              { label: '请选择', value: '' },
                              { label: '覆盖', value: 'overwrite' },
                              { label: '合并', value: 'merge' }
                            ]}
                          />
                        );
                      }
                    }
                  ]}
                />
              </Card>
            )}

            {/* 删除接口 */}
            {currentRecord.diff_data.removed && currentRecord.diff_data.removed.length > 0 && (
              <Card title={`删除接口 (${currentRecord.diff_data.removed.length})`} size="small">
                <Table
                  dataSource={currentRecord.diff_data.removed}
                  rowKey={(record: any) => `${record.method}-${record.path}`}
                  size="small"
                  pagination={false}
                  columns={[
                    { title: '方法', dataIndex: 'method', width: 80, render: (method: string) => <Tag color="red">{method}</Tag> },
                    { title: '路径', dataIndex: 'path', ellipsis: true },
                    { title: '描述', dataIndex: 'summary', ellipsis: true },
                    {
                      title: '操作',
                      width: 120,
                      render: (_: any, record: any) => (
                        <Checkbox
                          checked={selectedOperations.some(op =>
                            op.type === 'deprecate' && op.method === record.method && op.path === record.path
                          )}
                          onChange={(e) => handleOperationToggle('deprecate', record, e.target.checked)}
                        >
                          {selectedOperations.some(op =>
                            op.type === 'deprecate' && op.method === record.method && op.path === record.path
                          ) ? '已选择' : '废弃'}
                        </Checkbox>
                      )
                    }
                  ]}
                />
              </Card>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Sync;
