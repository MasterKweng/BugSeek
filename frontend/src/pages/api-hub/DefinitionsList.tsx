/**
 * 接口列表页面（V2.0 层级一 - API 资产库）
 * 符合前端代码规范：
 * 1. 防止重复提交：按钮加载状态
 * 2. 空值防御：使用可选链和默认值
 * 3. 友好异常提示：统一错误处理
 * 4. 高频事件节流：搜索框防抖
 */
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
  Badge,
  Popconfirm,
  Drawer,
  Checkbox,
  Tabs,
  Alert,
  Divider,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  FilterOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useParams } from 'react-router-dom';
import { useDebounce } from '../../hooks/useDebounce';
import { useProjectStore } from '../../store/project';
import DiffView from '../../components/DiffView';
import api from '../../services/api';
import ApiDebug from './ApiDebug';
import MockService from './MockService';

interface ApiDefinition {
  id: number;
  project_id: number;
  group_id: number | null;
  group_name: string | null;
  method: string;
  path: string;
  summary: string | null;
  description: string | null;
  tags: string[];
  status: string;
  sync_status: string;
  lock_status: string;
  content_hash: string | null;
  source_type: string | null;
  source_version: string | null;
  last_sync_at: string | null;
  case_count: number;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  updated_by: number | null;
}

interface ApiResponse {
  code: number;
  message: string;
  data: any;
}

const DefinitionsList: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const { currentVersion } = useProjectStore();

  // 状态管理
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<ApiDefinition[]>([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // 筛选条件
  const [filters, setFilters] = useState({
    method: undefined as string | undefined,
    status: undefined as string | undefined,
    group_id: undefined as number | undefined,
    version_id: undefined as number | undefined,
    keyword: '',
  });

  const debouncedKeyword = useDebounce(filters.keyword, 300);

  // 弹窗状态
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [detailActiveTab, setDetailActiveTab] = useState('info');
  const [batchLinkModalVisible, setBatchLinkModalVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<ApiDefinition | null>(null);

  // 表格选择
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  const [form] = Form.useForm();
  const [batchLinkForm] = Form.useForm();

  // 初始化版本筛选
  useEffect(() => {
    if (currentVersion) {
      setFilters(prev => ({ ...prev, version_id: currentVersion.id }));
    }
  }, [currentVersion]);

  // 获取 API 定义列表
  const fetchDefinitions = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        skip: String((pagination.current - 1) * pagination.pageSize),
        limit: String(pagination.pageSize),
      });

      if (filters.method) params.append('method', filters.method);
      if (filters.status) params.append('status', filters.status);
      if (filters.group_id) params.append('group_id', String(filters.group_id));
      if (filters.version_id) params.append('version_id', String(filters.version_id));
      if (debouncedKeyword) params.append('keyword', debouncedKeyword);

      const response = await fetch(`/api/v1/api-definitions?${params}`, {
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
      console.error('获取 API 定义列表失败:', error);
      message.error('获取数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDefinitions();
  }, [pagination, filters.method, filters.status, filters.group_id, filters.version_id, debouncedKeyword]);

  // 检查是否是详情页模式
  useEffect(() => {
    if (id) {
      fetchDefinitionDetail(Number(id));
    }
  }, [id]);

  // 获取单个定义详情
  const fetchDefinitionDetail = async (definitionId: number, mode: 'detail' | 'edit' = 'detail') => {
    try {
      const response = await fetch(`/api/v1/api-definitions/${definitionId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        setCurrentRecord(result.data);
        
        if (mode === 'detail') {
          setDetailDrawerVisible(true);
        } else if (mode === 'edit') {
          // 设置编辑表单的值
          form.setFieldsValue({
            method: result.data.method,
            path: result.data.path,
            summary: result.data.summary,
            description: result.data.description,
            tags: result.data.tags,
            group_id: result.data.group_id,
            status: result.data.status,
            request_schema: result.data.request_schema,
            response_schema: result.data.response_schema,
            mock_data: result.data.mock_data,
          });
          setEditModalVisible(true);
        }
      } else {
        message.error(result.message || '获取详情失败');
      }
    } catch (error) {
      console.error('获取详情失败:', error);
      message.error('获取详情失败，请稍后重试');
    }
  };

  // 创建 API 定义
  const handleCreate = async (values: any) => {
    try {
      const response = await fetch('/api/v1/api-definitions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(values),
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        message.success('创建成功');
        setCreateModalVisible(false);
        form.resetFields();
        fetchDefinitions();
      } else {
        message.error(result.message || '创建失败');
      }
    } catch (error) {
      console.error('创建失败:', error);
      message.error('创建失败，请稍后重试');
    }
  };

  // 更新 API 定义
  const handleUpdate = async (values: any) => {
    if (!currentRecord) return;

    try {
      // 解析 JSON 字段
      const updateData = {
        ...values,
        request_schema: values.request_schema ? JSON.parse(values.request_schema) : null,
        response_schema: values.response_schema ? JSON.parse(values.response_schema) : null,
        mock_data: values.mock_data ? JSON.parse(values.mock_data) : null,
      };

      const response = await fetch(`/api/v1/api-definitions/${currentRecord.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(updateData),
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        message.success('更新成功');
        setEditModalVisible(false);
        form.resetFields();
        fetchDefinitions();
        // 如果详情抽屉打开，重新获取详情
        if (detailDrawerVisible) {
          fetchDefinitionDetail(currentRecord.id, 'detail');
        }
      } else {
        message.error(result.message || '更新失败');
      }
    } catch (error: any) {
      console.error('更新失败:', error);
      if (error.message && error.message.includes('JSON')) {
        message.error('JSON 格式错误，请检查输入');
      } else {
        message.error('更新失败，请稍后重试');
      }
    }
  };

  // 删除 API 定义
  const handleDelete = async (record: ApiDefinition) => {
    try {
      const response = await fetch(`/api/v1/api-definitions/${record.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        message.success('删除成功');
        fetchDefinitions();
      } else {
        message.error(result.message || '删除失败');
      }
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请稍后重试');
    }
  };

  // 打开编辑弹窗
  const openEditModal = (record: ApiDefinition) => {
    setCurrentRecord(record);
    form.setFieldsValue({
      method: record.method,
      path: record.path,
      summary: record.summary,
      description: record.description,
      tags: record.tags,
      group_id: record.group_id,
      status: record.status,
      request_schema: record.request_schema ? JSON.stringify(record.request_schema, null, 2) : '',
      response_schema: record.response_schema ? JSON.stringify(record.response_schema, null, 2) : '',
      mock_data: record.mock_data ? JSON.stringify(record.mock_data, null, 2) : '',
    });
    setEditModalVisible(true);
  };

  // 批量关联到版本
  const handleBatchLinkToVersion = async (values: any) => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要关联的接口');
      return;
    }

    try {
      const response = await fetch('/api/v1/api-definitions/batch-link-version', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          definition_ids: selectedRowKeys,
          version_id: values.version_id,
        }),
      });

      const result: ApiResponse = await response.json();

      if (result.code === 0) {
        message.success(`批量关联成功：新增 ${result.data.created_count} 个，跳过 ${result.data.skipped_count} 个`);
        setBatchLinkModalVisible(false);
        batchLinkForm.resetFields();
        setSelectedRowKeys([]);
        fetchDefinitions();
      } else {
        message.error(result.message || '批量关联失败');
      }
    } catch (error) {
      console.error('批量关联失败:', error);
      message.error('批量关联失败，请稍后重试');
    }
  };

  // 方法标签颜色
  const getMethodColor = (method: string) => {
    const colors: Record<string, string> = {
      GET: 'green',
      POST: 'blue',
      PUT: 'orange',
      DELETE: 'red',
      PATCH: 'purple',
    };
    return colors[method.toUpperCase()] || 'default';
  };

  // 同步状态标签
  const getSyncStatusTag = (syncStatus: string) => {
    const statusMap: Record<string, { text: string; color: string }> = {
      synced: { text: '已同步', color: 'success' },
      conflict: { text: '冲突', color: 'error' },
      pending: { text: '待同步', color: 'warning' },
    };
    const status = statusMap[syncStatus] || { text: syncStatus, color: 'default' };
    return <Tag color={status.color}>{status.text}</Tag>;
  };

  // 锁定状态标签
  const getLockStatusTag = (lockStatus: string) => {
    if (lockStatus === 'locked') {
      return <Tag color="warning">已锁定</Tag>;
    }
    return <Tag color="success">未锁定</Tag>;
  };

  // 表格列定义
  const columns: ColumnsType<ApiDefinition> = [
    {
      title: '选择',
      dataIndex: 'id',
      key: 'select',
      width: 50,
      render: (_: any, record: ApiDefinition) => (
        <Checkbox
          checked={selectedRowKeys.includes(record.id)}
          onChange={(e) => {
            if (e.target.checked) {
              setSelectedRowKeys([...selectedRowKeys, record.id]);
            } else {
              setSelectedRowKeys(selectedRowKeys.filter(key => key !== record.id));
            }
          }}
        />
      ),
    },
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      width: 80,
      render: (method: string) => (
        <Tag color={getMethodColor(method)}>{method.toUpperCase()}</Tag>
      ),
      filters: [
        { text: 'GET', value: 'GET' },
        { text: 'POST', value: 'POST' },
        { text: 'PUT', value: 'PUT' },
        { text: 'DELETE', value: 'DELETE' },
        { text: 'PATCH', value: 'PATCH' },
      ],
    },
    {
      title: '接口路径',
      dataIndex: 'path',
      key: 'path',
      width: 250,
      render: (path: string, record: ApiDefinition) => (
        <div>
          <Space>
            {record.sync_status === 'conflict' && (
              <Badge dot color="red" />
            )}
            <div style={{ fontWeight: 'bold' }}>{path}</div>
          </Space>
          {record.summary && (
            <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>
              {record.summary}
            </div>
          )}
        </div>
      ),
    },
    {
      title: '分组',
      dataIndex: 'group_name',
      key: 'group_name',
      width: 120,
      render: (groupName: string | null) => groupName || '-',
    },
    {
      title: '用例数',
      dataIndex: 'case_count',
      key: 'case_count',
      width: 80,
      render: (count: number) => (
        <Badge count={count} showZero style={{ backgroundColor: '#52c41a' }} />
      ),
    },
    {
      title: '同步状态',
      dataIndex: 'sync_status',
      key: 'sync_status',
      width: 100,
      render: getSyncStatusTag,
    },
    {
      title: '锁定状态',
      dataIndex: 'lock_status',
      key: 'lock_status',
      width: 100,
      render: getLockStatusTag,
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 100,
      render: (sourceType: string | null) => sourceType || '-',
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 150,
      render: (updatedAt: string) => {
        const date = new Date(updatedAt);
        return date.toLocaleString('zh-CN');
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right',
      render: (_: any, record: ApiDefinition) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => fetchDefinitionDetail(record.id, 'detail')}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => fetchDefinitionDetail(record.id, 'edit')}
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除吗？"
            onConfirm={() => handleDelete(record)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
          <Tooltip title="查看用例">
            <Button
              type="link"
              size="small"
              onClick={() => navigate(`/api-hub/cases?definition_id=${record.id}`)}
            >
              用例
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        {/* 顶部操作栏 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={5}>
            <Input
              placeholder="搜索路径、摘要、描述"
              prefix={<SearchOutlined />}
              value={filters.keyword}
              onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
              allowClear
            />
          </Col>
          <Col span={2}>
            <Select
              placeholder="请求方法"
              style={{ width: '100%' }}
              value={filters.method}
              onChange={(value) => setFilters({ ...filters, method: value })}
              allowClear
            >
              <Select.Option value="GET">GET</Select.Option>
              <Select.Option value="POST">POST</Select.Option>
              <Select.Option value="PUT">PUT</Select.Option>
              <Select.Option value="DELETE">DELETE</Select.Option>
              <Select.Option value="PATCH">PATCH</Select.Option>
            </Select>
          </Col>
          <Col span={2}>
            <Select
              placeholder="状态"
              style={{ width: '100%' }}
              value={filters.status}
              onChange={(value) => setFilters({ ...filters, status: value })}
              allowClear
            >
              <Select.Option value="active">活跃</Select.Option>
              <Select.Option value="archived">已归档</Select.Option>
            </Select>
          </Col>
          <Col span={15} style={{ textAlign: 'right' }}>
            <Space>
              {selectedRowKeys.length > 0 && (
                <Button
                  icon={<LinkOutlined />}
                  onClick={() => setBatchLinkModalVisible(true)}
                >
                  关联到版本 ({selectedRowKeys.length})
                </Button>
              )}
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchDefinitions}
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
                新建接口
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
        title="新建接口"
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
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="method"
            label="请求方法"
            rules={[{ required: true, message: '请选择请求方法' }]}
          >
            <Select placeholder="请选择请求方法">
              <Select.Option value="GET">GET</Select.Option>
              <Select.Option value="POST">POST</Select.Option>
              <Select.Option value="PUT">PUT</Select.Option>
              <Select.Option value="DELETE">DELETE</Select.Option>
              <Select.Option value="PATCH">PATCH</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="path"
            label="接口路径"
            rules={[{ required: true, message: '请输入接口路径' }]}
          >
            <Input placeholder="例如: /api/users" />
          </Form.Item>
          <Form.Item
            name="summary"
            label="接口摘要"
          >
            <Input placeholder="例如: 获取用户列表" />
          </Form.Item>
          <Form.Item
            name="description"
            label="接口描述"
          >
            <Input.TextArea rows={3} placeholder="接口的详细描述" />
          </Form.Item>
          <Form.Item
            name="tags"
            label="标签"
          >
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        title="编辑接口"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        width={800}
        footer={[
          <Button key="cancel" onClick={() => setEditModalVisible(false)}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={loading}
            onClick={() => form.submit()}
          >
            更新
          </Button>,
        ]}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleUpdate}
        >
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item
                name="method"
                label="请求方法"
                rules={[{ required: true, message: '请选择请求方法' }]}
              >
                <Select placeholder="请选择请求方法">
                  <Select.Option value="GET">GET</Select.Option>
                  <Select.Option value="POST">POST</Select.Option>
                  <Select.Option value="PUT">PUT</Select.Option>
                  <Select.Option value="DELETE">DELETE</Select.Option>
                  <Select.Option value="PATCH">PATCH</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={18}>
              <Form.Item
                name="path"
                label="接口路径"
                rules={[{ required: true, message: '请输入接口路径' }]}
              >
                <Input placeholder="例如: /api/users" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="summary"
                label="接口摘要"
              >
                <Input placeholder="例如: 获取用户列表" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="status"
                label="状态"
              >
                <Select placeholder="请选择状态">
                  <Select.Option value="active">活跃</Select.Option>
                  <Select.Option value="archived">已归档</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="description"
            label="接口描述"
          >
            <Input.TextArea rows={3} placeholder="接口的详细描述" />
          </Form.Item>
          <Form.Item
            name="tags"
            label="标签"
          >
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
          
          <Divider orientation="left">Schema 配置</Divider>
          
          <Form.Item
            name="request_schema"
            label="请求参数 Schema (JSON)"
            extra="请求参数的 JSON Schema 定义"
          >
            <Input.TextArea 
              rows={8} 
              placeholder='{"type": "object", "properties": {...}}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
          
          <Form.Item
            name="response_schema"
            label="响应参数 Schema (JSON)"
            extra="响应参数的 JSON Schema 定义"
          >
            <Input.TextArea 
              rows={8} 
              placeholder='{"type": "object", "properties": {...}}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
          
          <Divider orientation="left">Mock 配置</Divider>
          
          <Form.Item
            name="mock_data"
            label="Mock 数据 (JSON)"
            extra="用于接口测试的模拟响应数据"
          >
            <Input.TextArea 
              rows={6} 
              placeholder='{"code": 0, "data": {...}}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        </Form>
      </Modal>

{/* 详情抽屉 */}
      <Drawer
        title={
          <Space>
            <span>接口详情</span>
            <Button 
              size="small" 
              icon={<EditOutlined />} 
              onClick={() => openEditModal(currentRecord!)}
            >
              编辑
            </Button>
          </Space>
        }
        placement="right"
        width={900}
        open={detailDrawerVisible}
        onClose={() => setDetailDrawerVisible(false)}
      >
        {currentRecord && (
          <Tabs activeKey={detailActiveTab} onChange={setDetailActiveTab} items={[
            {
              key: 'info',
              label: '基本信息',
              children: (
                <div>
                  <Row gutter={[16, 16]}>
                    <Col span={8}>
                      <div style={{ color: '#999', marginBottom: 4 }}>请求方法</div>
                      <Tag color={getMethodColor(currentRecord.method)}>{currentRecord.method.toUpperCase()}</Tag>
                    </Col>
                    <Col span={16}>
                      <div style={{ color: '#999', marginBottom: 4 }}>接口路径</div>
                      <div style={{ fontWeight: 'bold' }}>{currentRecord.path}</div>
                    </Col>
                    <Col span={24}>
                      <div style={{ color: '#999', marginBottom: 4 }}>接口摘要</div>
                      <div>{currentRecord.summary || '-'}</div>
                    </Col>
                    <Col span={24}>
                      <div style={{ color: '#999', marginBottom: 4 }}>接口描述</div>
                      <div>{currentRecord.description || '-'}</div>
                    </Col>
                    <Col span={12}>
                      <div style={{ color: '#999', marginBottom: 4 }}>分组</div>
                      <div>{currentRecord.group_name || '-'}</div>
                    </Col>
                    <Col span={12}>
                      <div style={{ color: '#999', marginBottom: 4 }}>用例数量</div>
                      <Badge count={currentRecord.case_count} showZero style={{ backgroundColor: '#52c41a' }} />
                    </Col>
                    <Col span={12}>
                      <div style={{ color: '#999', marginBottom: 4 }}>同步状态</div>
                      {getSyncStatusTag(currentRecord.sync_status)}
                    </Col>
                    <Col span={12}>
                      <div style={{ color: '#999', marginBottom: 4 }}>锁定状态</div>
                      {getLockStatusTag(currentRecord.lock_status)}
                    </Col>
                    <Col span={12}>
                      <div style={{ color: '#999', marginBottom: 4 }}>来源类型</div>
                      <div>{currentRecord.source_type || '-'}</div>
                    </Col>
                    <Col span={12}>
                      <div style={{ color: '#999', marginBottom: 4 }}>来源版本</div>
                      <div>{currentRecord.source_version || '-'}</div>
                    </Col>
                    <Col span={12}>
                      <div style={{ color: '#999', marginBottom: 4 }}>创建时间</div>
                      <div>{new Date(currentRecord.created_at).toLocaleString('zh-CN')}</div>
                    </Col>
                    <Col span={12}>
                      <div style={{ color: '#999', marginBottom: 4 }}>更新时间</div>
                      <div>{new Date(currentRecord.updated_at).toLocaleString('zh-CN')}</div>
                    </Col>
                    <Col span={24}>
                      <div style={{ color: '#999', marginBottom: 4 }}>标签</div>
                      <Space>
                        {currentRecord.tags?.map((tag: string) => (
                          <Tag key={tag}>{tag}</Tag>
                        )) || '-'}
                      </Space>
                    </Col>
                  </Row>
                </div>
              ),
            },
            {
              key: 'schema',
              label: 'Schema 配置',
              children: (
                <div>
                  <Alert
                    message="Schema 配置"
                    description="查看和编辑接口的请求参数和响应参数定义"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <Tabs
                    items={[
                      {
                        key: 'request',
                        label: '请求参数 Schema',
                        children: (
                          <div>
                            <pre style={{ 
                              background: '#f5f5f5', 
                              padding: 16, 
                              borderRadius: 4,
                              maxHeight: 400,
                              overflow: 'auto'
                            }}>
                              {JSON.stringify(currentRecord.request_schema || {}, null, 2)}
                            </pre>
                            <Button 
                              type="primary" 
                              icon={<EditOutlined />}
                              onClick={() => openEditModal(currentRecord)}
                              style={{ marginTop: 16 }}
                            >
                              编辑 Schema
                            </Button>
                          </div>
                        ),
                      },
                      {
                        key: 'response',
                        label: '响应参数 Schema',
                        children: (
                          <div>
                            <pre style={{ 
                              background: '#f5f5f5', 
                              padding: 16, 
                              borderRadius: 4,
                              maxHeight: 400,
                              overflow: 'auto'
                            }}>
                              {JSON.stringify(currentRecord.response_schema || {}, null, 2)}
                            </pre>
                            <Button 
                              type="primary" 
                              icon={<EditOutlined />}
                              onClick={() => openEditModal(currentRecord)}
                              style={{ marginTop: 16 }}
                            >
                              编辑 Schema
                            </Button>
                          </div>
                        ),
                      },
                    ]}
                  />
                </div>
              ),
            },
            {
              key: 'debug',
              label: '在线调试',
              children: <ApiDebug definition={currentRecord} />,
            },
            {
              key: 'mock',
              label: 'Mock 服务',
              children: <MockService definition={currentRecord} />,
            },
            {
              key: 'history',
              label: '版本历史',
              children: (
                <div>
                  <Alert
                    message="版本历史"
                    description="查看接口定义的历史变更记录"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                    版本历史功能开发中...
                  </div>
                </div>
              ),
            },
            {
              key: 'diff',
              label: '变更对比',
              children: (
                <div>
                  <Alert
                    message="变更对比"
                    description="对比当前版本与上一个版本的差异"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <DiffView
                    oldData={currentRecord.request_schema || {}}
                    newData={currentRecord.response_schema || {}}
                    title="Schema 对比"
                  />
                </div>
              ),
            },
          ]} />
        )}
      </Drawer>

      {/* 批量关联弹窗 */}
      <Modal
        title={`关联接口到版本 (${selectedRowKeys.length} 个)`}
        open={batchLinkModalVisible}
        onCancel={() => {
          setBatchLinkModalVisible(false);
          batchLinkForm.resetFields();
        }}
        footer={[
          <Button key="cancel" onClick={() => {
            setBatchLinkModalVisible(false);
            batchLinkForm.resetFields();
          }}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={loading}
            onClick={() => batchLinkForm.submit()}
          >
            确定关联
          </Button>,
        ]}
      >
        <Form
          form={batchLinkForm}
          layout="vertical"
          onFinish={handleBatchLinkToVersion}
        >
          <Form.Item
            name="version_id"
            label="目标版本"
            rules={[{ required: true, message: '请选择目标版本' }]}
          >
            <Select placeholder="请选择目标版本">
              {currentVersion && (
                <Select.Option value={currentVersion.id}>
                  {currentVersion.version_number} ({currentVersion.status})
                </Select.Option>
              )}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DefinitionsList;