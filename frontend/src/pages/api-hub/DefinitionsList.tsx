import React, { useEffect, useState } from 'react';
import {
  Badge, Button, Card, Checkbox, Col, Divider, Drawer, Form, Input, Modal,
  Popconfirm, Row, Select, Space, Table, Tabs, Tag, Tooltip, message,
} from 'antd';
import {
  DeleteOutlined, EditOutlined, EyeOutlined, LinkOutlined,
  PlusOutlined, ReloadOutlined, SearchOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useParams } from 'react-router-dom';
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero';
import DiffView from '../../components/DiffView';
import { useDebounce } from '../../hooks/useDebounce';
import { useProjectStore } from '../../store/project';
import ApiDebug from './ApiDebug';
import MockService from './MockService';

interface ApiDefinition {
  id: number;
  project_id: number;
  module_id?: number | null;
  module_name?: string | null;
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
  request_schema?: Record<string, unknown> | null;
  response_schema?: Record<string, unknown> | null;
  mock_data?: Record<string, unknown> | null;
}

interface ApiModule {
  id: number;
  name: string;
  description?: string | null;
  sort_order?: number;
}

interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

const methodOptions = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

const DefinitionsList: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const { currentProject, currentVersion } = useProjectStore();
  const [loading, setLoading] = useState(false);
  const [modulesLoading, setModulesLoading] = useState(false);
  const [moduleSubmitting, setModuleSubmitting] = useState(false);
  const [dataSource, setDataSource] = useState<ApiDefinition[]>([]);
  const [modules, setModules] = useState<ApiModule[]>([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [filters, setFilters] = useState({
    method: undefined as string | undefined,
    status: undefined as string | undefined,
    module_id: undefined as number | undefined,
    version_id: undefined as number | undefined,
    keyword: '',
  });
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [detailActiveTab, setDetailActiveTab] = useState('info');
  const [batchLinkModalVisible, setBatchLinkModalVisible] = useState(false);
  const [moduleManageVisible, setModuleManageVisible] = useState(false);
  const [moduleModalVisible, setModuleModalVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<ApiDefinition | null>(null);
  const [editingModule, setEditingModule] = useState<ApiModule | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [form] = Form.useForm();
  const [batchLinkForm] = Form.useForm();
  const [moduleForm] = Form.useForm();
  const debouncedKeyword = useDebounce(filters.keyword, 300);
  const moduleOptions = modules.map((item) => ({ label: item.name, value: item.id }));
  const resolveModuleName = (item?: ApiDefinition | null) => item?.module_name ?? item?.group_name ?? '-';

  useEffect(() => {
    if (currentVersion) setFilters((prev) => ({ ...prev, version_id: currentVersion.id }));
  }, [currentVersion]);

  const fetchModules = async () => {
    if (!currentProject?.id) return setModules([]);
    setModulesLoading(true);
    try {
      const response = await fetch(`/api/v1/api-modules?project_id=${currentProject.id}`, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
      const result: ApiResponse<{ items?: ApiModule[] }> = await response.json();
      if (result.code === 0) setModules(result.data?.items || []);
      else message.error(result.message || '获取模块失败');
    } catch (error) {
      console.error('获取模块失败:', error);
      message.error('获取模块失败，请稍后重试');
    } finally {
      setModulesLoading(false);
    }
  };

  const fetchDefinitions = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ skip: String((pagination.current - 1) * pagination.pageSize), limit: String(pagination.pageSize) });
      if (filters.method) params.append('method', filters.method);
      if (filters.status) params.append('status', filters.status);
      if (filters.module_id) params.append('module_id', String(filters.module_id));
      if (filters.version_id) params.append('version_id', String(filters.version_id));
      if (currentProject?.id) params.append('project_id', String(currentProject.id));
      if (debouncedKeyword) params.append('keyword', debouncedKeyword);
      const response = await fetch(`/api/v1/api-definitions?${params.toString()}`, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
      const result: ApiResponse<{ items?: ApiDefinition[]; total?: number }> = await response.json();
      if (result.code === 0) {
        setDataSource(result.data?.items || []);
        setTotal(result.data?.total || 0);
      } else message.error(result.message || '获取数据失败');
    } catch (error) {
      console.error('获取 API 定义列表失败:', error);
      message.error('获取数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchModules(); }, [currentProject?.id]);
  useEffect(() => { fetchDefinitions(); }, [pagination, filters.method, filters.status, filters.module_id, filters.version_id, debouncedKeyword, currentProject?.id]);
  useEffect(() => { if (id) fetchDefinitionDetail(Number(id)); }, [id]);

  const fillEditForm = (item: ApiDefinition) => {
    form.setFieldsValue({
      method: item.method,
      path: item.path,
      summary: item.summary,
      description: item.description,
      tags: item.tags,
      module_id: item.module_id ?? item.group_id ?? null,
      status: item.status,
      request_schema: item.request_schema ? JSON.stringify(item.request_schema, null, 2) : '',
      response_schema: item.response_schema ? JSON.stringify(item.response_schema, null, 2) : '',
      mock_data: item.mock_data ? JSON.stringify(item.mock_data, null, 2) : '',
    });
  };

  const fetchDefinitionDetail = async (definitionId: number, mode: 'detail' | 'edit' = 'detail') => {
    try {
      const response = await fetch(`/api/v1/api-definitions/${definitionId}`, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
      const result: ApiResponse<ApiDefinition> = await response.json();
      if (result.code !== 0) return message.error(result.message || '获取详情失败');
      setCurrentRecord(result.data);
      if (mode === 'detail') setDetailDrawerVisible(true);
      else {
        fillEditForm(result.data);
        setEditModalVisible(true);
      }
    } catch (error) {
      console.error('获取详情失败:', error);
      message.error('获取详情失败，请稍后重试');
    }
  };

  const submitDefinition = async (url: string, method: 'POST' | 'PUT', values: any, successMessage: string) => {
    try {
      const payload = {
        ...values,
        request_schema: typeof values.request_schema === 'string' ? (values.request_schema ? JSON.parse(values.request_schema) : null) : values.request_schema,
        response_schema: typeof values.response_schema === 'string' ? (values.response_schema ? JSON.parse(values.response_schema) : null) : values.response_schema,
        mock_data: typeof values.mock_data === 'string' ? (values.mock_data ? JSON.parse(values.mock_data) : null) : values.mock_data,
      };
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('token')}` },
        body: JSON.stringify(payload),
      });
      const result: ApiResponse = await response.json();
      if (result.code !== 0) return message.error(result.message || `${successMessage}失败`);
      message.success(successMessage);
      setCreateModalVisible(false);
      setEditModalVisible(false);
      form.resetFields();
      fetchDefinitions();
      if (detailDrawerVisible && currentRecord && method === 'PUT') fetchDefinitionDetail(currentRecord.id, 'detail');
    } catch (error: any) {
      console.error(`${successMessage}失败:`, error);
      message.error(error?.message?.includes('JSON') ? 'JSON 格式错误，请检查输入' : `${successMessage}失败，请稍后重试`);
    }
  };

  const handleDelete = async (record: ApiDefinition) => {
    try {
      const response = await fetch(`/api/v1/api-definitions/${record.id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
      const result: ApiResponse = await response.json();
      if (result.code === 0) {
        message.success('删除成功');
        fetchDefinitions();
      } else message.error(result.message || '删除失败');
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请稍后重试');
    }
  };

  const handleBatchLinkToVersion = async (values: any) => {
    if (!selectedRowKeys.length) return message.warning('请先选择要关联的接口');
    try {
      const response = await fetch('/api/v1/api-definitions/batch-link-version', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('token')}` },
        body: JSON.stringify({ definition_ids: selectedRowKeys, version_id: values.version_id }),
      });
      const result: ApiResponse<{ created_count: number; skipped_count: number }> = await response.json();
      if (result.code === 0) {
        message.success(`批量关联成功：新增 ${result.data.created_count} 个，跳过 ${result.data.skipped_count} 个`);
        setBatchLinkModalVisible(false);
        batchLinkForm.resetFields();
        setSelectedRowKeys([]);
        fetchDefinitions();
      } else message.error(result.message || '批量关联失败');
    } catch (error) {
      console.error('批量关联失败:', error);
      message.error('批量关联失败，请稍后重试');
    }
  };

  const openModuleModal = (item?: ApiModule) => {
    setEditingModule(item || null);
    moduleForm.setFieldsValue({ name: item?.name ?? '', description: item?.description ?? '', sort_order: item?.sort_order ?? 0 });
    setModuleModalVisible(true);
  };
  const closeModuleModal = () => {
    setEditingModule(null);
    setModuleModalVisible(false);
    moduleForm.resetFields();
  };

  const saveModule = async (values: any) => {
    setModuleSubmitting(true);
    try {
      const isEditing = Boolean(editingModule);
      const url = isEditing ? `/api/v1/api-modules/${editingModule?.id}?project_id=${currentProject?.id}` : `/api/v1/api-modules?project_id=${currentProject?.id}`;
      const response = await fetch(url, {
        method: isEditing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('token')}` },
        body: JSON.stringify(values),
      });
      const result: ApiResponse = await response.json();
      if (result.code === 0) {
        message.success(isEditing ? '模块更新成功' : '模块创建成功');
        closeModuleModal();
        fetchModules();
        fetchDefinitions();
      } else message.error(result.message || '保存模块失败');
    } catch (error) {
      console.error('保存模块失败:', error);
      message.error('保存模块失败，请稍后重试');
    } finally {
      setModuleSubmitting(false);
    }
  };

  const deleteModule = async (item: ApiModule) => {
    try {
      const response = await fetch(`/api/v1/api-modules/${item.id}?project_id=${currentProject?.id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
      const result: ApiResponse = await response.json();
      if (result.code === 0) {
        message.success('模块删除成功');
        fetchModules();
        fetchDefinitions();
      } else message.error(result.message || '删除模块失败');
    } catch (error) {
      console.error('删除模块失败:', error);
      message.error('删除模块失败，请稍后重试');
    }
  };

  const getMethodColor = (method: string) => ({ GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red', PATCH: 'purple' }[method.toUpperCase()] || 'default');
  const getSyncStatusTag = (syncStatus: string) => <Tag color={({ synced: 'success', conflict: 'error', pending: 'warning' } as Record<string, string>)[syncStatus] || 'default'}>{{ synced: '已同步', conflict: '冲突', pending: '待同步' }[syncStatus] || syncStatus}</Tag>;
  const getLockStatusTag = (lockStatus: string) => lockStatus === 'locked' ? <Tag color="warning">已锁定</Tag> : <Tag color="success">未锁定</Tag>;

  const columns: ColumnsType<ApiDefinition> = [
    { title: '选择', dataIndex: 'id', key: 'select', width: 50, render: (_v, record) => <Checkbox checked={selectedRowKeys.includes(record.id)} onChange={(e) => setSelectedRowKeys(e.target.checked ? [...selectedRowKeys, record.id] : selectedRowKeys.filter((key) => key !== record.id))} /> },
    { title: '方法', dataIndex: 'method', key: 'method', width: 80, render: (method) => <Tag color={getMethodColor(method)}>{method.toUpperCase()}</Tag> },
    { title: '接口路径', dataIndex: 'path', key: 'path', width: 320, render: (path, record) => <div><div className="api-definitions-path-row">{record.sync_status === 'conflict' && <Badge dot color="red" />}<div className="api-definitions-path-text" title={path}>{path}</div></div>{record.summary && <div className="api-definitions-summary-text" title={record.summary}>{record.summary}</div>}</div> },
    { title: '模块', key: 'module_name', width: 140, render: (_v, record) => resolveModuleName(record) },
    { title: '用例数', dataIndex: 'case_count', key: 'case_count', width: 80, render: (count) => <Badge count={count} showZero style={{ backgroundColor: '#52c41a' }} /> },
    { title: '同步状态', dataIndex: 'sync_status', key: 'sync_status', width: 100, render: getSyncStatusTag },
    { title: '锁定状态', dataIndex: 'lock_status', key: 'lock_status', width: 100, render: getLockStatusTag },
    { title: '来源', dataIndex: 'source_type', key: 'source_type', width: 100, render: (value) => value || '-' },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 150, render: (value) => new Date(value).toLocaleString('zh-CN') },
    {
      title: '操作', key: 'action', width: 200, fixed: 'right',
      render: (_v, record) => (
        <Space size="small">
          <Tooltip title="查看详情"><Button type="link" size="small" icon={<EyeOutlined />} onClick={() => fetchDefinitionDetail(record.id, 'detail')} /></Tooltip>
          <Tooltip title="编辑"><Button type="link" size="small" icon={<EditOutlined />} onClick={() => { setCurrentRecord(record); fillEditForm(record); setEditModalVisible(true); }} /></Tooltip>
          <Popconfirm title="确定要删除吗？" onConfirm={() => handleDelete(record)} okText="确定" cancelText="取消"><Tooltip title="删除"><Button type="link" size="small" danger icon={<DeleteOutlined />} /></Tooltip></Popconfirm>
          <Tooltip title="查看用例"><Button type="link" size="small" onClick={() => navigate(`/api-hub/cases?definition_id=${record.id}`)}>用例</Button></Tooltip>
        </Space>
      ),
    },
  ];

  const moduleColumns: ColumnsType<ApiModule> = [
    { title: '模块名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', render: (value) => value || '-' },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80, render: (value) => value ?? 0 },
    { title: '操作', key: 'action', width: 150, render: (_v, record) => <Space size="small"><Button type="link" size="small" icon={<EditOutlined />} onClick={() => openModuleModal(record)}>编辑</Button><Popconfirm title="确定要删除这个模块吗？" onConfirm={() => deleteModule(record)} okText="确定" cancelText="取消"><Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button></Popconfirm></Space> },
  ];

  return (
    <div className="workspace-page api-definitions-page">
      <WorkspaceModuleHero eyebrow="API Hub" title="接口定义" description="管理接口目录、模块归属与版本关联。" metrics={[{ label: '当前页定义', value: dataSource.length }, { label: '定义总数', value: total }, { label: '模块数', value: modules.length }]} />
      <Card className="workspace-table-card api-definitions-page__card" bordered={false}>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={5}><Input placeholder="搜索路径、摘要、描述" prefix={<SearchOutlined />} value={filters.keyword} onChange={(e) => setFilters({ ...filters, keyword: e.target.value })} allowClear /></Col>
          <Col span={3}><Select placeholder="请求方法" style={{ width: '100%' }} value={filters.method} onChange={(value) => setFilters({ ...filters, method: value })} allowClear>{methodOptions.map((item) => <Select.Option key={item} value={item}>{item}</Select.Option>)}</Select></Col>
          <Col span={3}><Select placeholder="状态" style={{ width: '100%' }} value={filters.status} onChange={(value) => setFilters({ ...filters, status: value })} allowClear><Select.Option value="active">活跃</Select.Option><Select.Option value="archived">已归档</Select.Option></Select></Col>
          <Col span={4}><Select placeholder="模块" style={{ width: '100%' }} value={filters.module_id} onChange={(value) => setFilters({ ...filters, module_id: value })} allowClear options={moduleOptions} loading={modulesLoading} /></Col>
          <Col span={9} style={{ textAlign: 'right' }}>
            <Space>
              {selectedRowKeys.length > 0 && <Button icon={<LinkOutlined />} onClick={() => setBatchLinkModalVisible(true)}>关联到版本 ({selectedRowKeys.length})</Button>}
              <Button onClick={() => setModuleManageVisible(true)}>模块管理</Button>
              <Button icon={<ReloadOutlined />} onClick={fetchDefinitions} loading={loading}>刷新</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setCreateModalVisible(true); }}>新建接口</Button>
            </Space>
          </Col>
        </Row>
        <Table columns={columns} dataSource={dataSource} rowKey="id" loading={loading} pagination={{ current: pagination.current, pageSize: pagination.pageSize, total, showSizeChanger: true, showQuickJumper: true, showTotal: (count) => `共 ${count} 条`, onChange: (page, pageSize) => setPagination({ current: page, pageSize: pageSize || 20 }) }} scroll={{ x: 1250, y: 'calc(100vh - 420px)' }} />
      </Card>

      <Modal title="新建接口" open={createModalVisible} onCancel={() => setCreateModalVisible(false)} footer={[<Button key="cancel" onClick={() => setCreateModalVisible(false)}>取消</Button>, <Button key="submit" type="primary" loading={loading} onClick={() => form.submit()}>创建</Button>]}>
        <Form form={form} layout="vertical" onFinish={(values) => submitDefinition('/api/v1/api-definitions', 'POST', values, '创建成功')}>
          <Form.Item name="method" label="请求方法" rules={[{ required: true, message: '请选择请求方法' }]}><Select placeholder="请选择请求方法">{methodOptions.map((item) => <Select.Option key={item} value={item}>{item}</Select.Option>)}</Select></Form.Item>
          <Form.Item name="path" label="接口路径" rules={[{ required: true, message: '请输入接口路径' }]}><Input placeholder="例如: /api/users" /></Form.Item>
          <Form.Item name="summary" label="接口摘要"><Input placeholder="例如: 获取用户列表" /></Form.Item>
          <Form.Item name="description" label="接口描述"><Input.TextArea rows={3} placeholder="接口的详细描述" /></Form.Item>
          <Form.Item name="tags" label="标签"><Select mode="tags" placeholder="输入标签后回车" /></Form.Item>
          <Form.Item name="module_id" label="所属模块"><Select allowClear placeholder="请选择模块" options={moduleOptions} loading={modulesLoading} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="编辑接口" open={editModalVisible} onCancel={() => setEditModalVisible(false)} width={800} footer={[<Button key="cancel" onClick={() => setEditModalVisible(false)}>取消</Button>, <Button key="submit" type="primary" loading={loading} onClick={() => form.submit()}>更新</Button>]}>
        <Form form={form} layout="vertical" onFinish={(values) => currentRecord && submitDefinition(`/api/v1/api-definitions/${currentRecord.id}`, 'PUT', values, '更新成功')}>
          <Row gutter={16}>
            <Col span={6}><Form.Item name="method" label="请求方法" rules={[{ required: true, message: '请选择请求方法' }]}><Select placeholder="请选择请求方法">{methodOptions.map((item) => <Select.Option key={item} value={item}>{item}</Select.Option>)}</Select></Form.Item></Col>
            <Col span={18}><Form.Item name="path" label="接口路径" rules={[{ required: true, message: '请输入接口路径' }]}><Input placeholder="例如: /api/users" /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="summary" label="接口摘要"><Input placeholder="例如: 获取用户列表" /></Form.Item></Col>
            <Col span={12}><Form.Item name="status" label="状态"><Select placeholder="请选择状态"><Select.Option value="active">活跃</Select.Option><Select.Option value="archived">已归档</Select.Option></Select></Form.Item></Col>
          </Row>
          <Form.Item name="description" label="接口描述"><Input.TextArea rows={3} placeholder="接口的详细描述" /></Form.Item>
          <Form.Item name="tags" label="标签"><Select mode="tags" placeholder="输入标签后回车" /></Form.Item>
          <Form.Item name="module_id" label="所属模块"><Select allowClear placeholder="请选择模块" options={moduleOptions} loading={modulesLoading} /></Form.Item>
          <Divider orientation="left">Schema 配置</Divider>
          <Form.Item name="request_schema" label="请求参数 Schema (JSON)" extra="请求参数的 JSON Schema 定义"><Input.TextArea rows={8} placeholder='{"type": "object", "properties": {...}}' style={{ fontFamily: 'monospace' }} /></Form.Item>
          <Form.Item name="response_schema" label="响应参数 Schema (JSON)" extra="响应参数的 JSON Schema 定义"><Input.TextArea rows={8} placeholder='{"type": "object", "properties": {...}}' style={{ fontFamily: 'monospace' }} /></Form.Item>
          <Divider orientation="left">Mock 配置</Divider>
          <Form.Item name="mock_data" label="Mock 数据 (JSON)" extra="用于接口测试的模拟响应数据"><Input.TextArea rows={6} placeholder='{"code": 0, "data": {...}}' style={{ fontFamily: 'monospace' }} /></Form.Item>
        </Form>
      </Modal>

      <Drawer title={<Space><span>接口详情</span><Button size="small" icon={<EditOutlined />} onClick={() => currentRecord && fetchDefinitionDetail(currentRecord.id, 'edit')}>编辑</Button></Space>} placement="right" width={900} open={detailDrawerVisible} onClose={() => setDetailDrawerVisible(false)}>
        {currentRecord && <Tabs activeKey={detailActiveTab} onChange={setDetailActiveTab} items={[
          { key: 'info', label: '基本信息', children: <Row gutter={[16, 16]}><Col span={8}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>请求方法</div><Tag color={getMethodColor(currentRecord.method)}>{currentRecord.method.toUpperCase()}</Tag></Col><Col span={16}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>接口路径</div><div style={{ fontWeight: 'bold' }}>{currentRecord.path}</div></Col><Col span={24}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>接口摘要</div><div>{currentRecord.summary || '-'}</div></Col><Col span={24}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>接口描述</div><div>{currentRecord.description || '-'}</div></Col><Col span={12}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>模块</div><div>{resolveModuleName(currentRecord)}</div></Col><Col span={12}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>用例数量</div><Badge count={currentRecord.case_count} showZero style={{ backgroundColor: '#52c41a' }} /></Col><Col span={12}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>同步状态</div>{getSyncStatusTag(currentRecord.sync_status)}</Col><Col span={12}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>锁定状态</div>{getLockStatusTag(currentRecord.lock_status)}</Col><Col span={12}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>来源类型</div><div>{currentRecord.source_type || '-'}</div></Col><Col span={12}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>来源版本</div><div>{currentRecord.source_version || '-'}</div></Col><Col span={12}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>创建时间</div><div>{new Date(currentRecord.created_at).toLocaleString('zh-CN')}</div></Col><Col span={12}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>更新时间</div><div>{new Date(currentRecord.updated_at).toLocaleString('zh-CN')}</div></Col><Col span={24}><div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>标签</div><Space wrap>{currentRecord.tags.length ? currentRecord.tags.map((tag) => <Tag key={tag}>{tag}</Tag>) : '-'}</Space></Col></Row> },
          { key: 'schema', label: 'Schema 配置', children: <Tabs items={[{ key: 'request', label: '请求参数 Schema', children: <div><pre style={{ background: 'var(--bg-tertiary)', padding: 16, borderRadius: 4, maxHeight: 400, overflow: 'auto' }}>{JSON.stringify(currentRecord.request_schema || {}, null, 2)}</pre><Button type="primary" icon={<EditOutlined />} onClick={() => fetchDefinitionDetail(currentRecord.id, 'edit')} style={{ marginTop: 16 }}>编辑 Schema</Button></div> }, { key: 'response', label: '响应参数 Schema', children: <div><pre style={{ background: 'var(--bg-tertiary)', padding: 16, borderRadius: 4, maxHeight: 400, overflow: 'auto' }}>{JSON.stringify(currentRecord.response_schema || {}, null, 2)}</pre><Button type="primary" icon={<EditOutlined />} onClick={() => fetchDefinitionDetail(currentRecord.id, 'edit')} style={{ marginTop: 16 }}>编辑 Schema</Button></div> }]} /> },
          { key: 'debug', label: '在线调试', children: <ApiDebug definition={currentRecord} /> },
          { key: 'mock', label: 'Mock 服务', children: <MockService definition={currentRecord} /> },
          { key: 'history', label: '版本历史', children: <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>版本历史功能开发中...</div> },
          { key: 'diff', label: '变更对比', children: <DiffView oldData={currentRecord.request_schema || {}} newData={currentRecord.response_schema || {}} title="Schema 对比" /> },
        ]} />}
      </Drawer>

      <Modal title={`关联接口到版本 (${selectedRowKeys.length} 个)`} open={batchLinkModalVisible} onCancel={() => { setBatchLinkModalVisible(false); batchLinkForm.resetFields(); }} footer={[<Button key="cancel" onClick={() => { setBatchLinkModalVisible(false); batchLinkForm.resetFields(); }}>取消</Button>, <Button key="submit" type="primary" loading={loading} onClick={() => batchLinkForm.submit()}>确定关联</Button>]}>
        <Form form={batchLinkForm} layout="vertical" onFinish={handleBatchLinkToVersion}>
          <Form.Item name="version_id" label="目标版本" rules={[{ required: true, message: '请选择目标版本' }]}><Select placeholder="请选择目标版本">{currentVersion && <Select.Option value={currentVersion.id}>{currentVersion.version_number} ({currentVersion.status})</Select.Option>}</Select></Form.Item>
        </Form>
      </Modal>

      <Modal title="模块管理" open={moduleManageVisible} onCancel={() => setModuleManageVisible(false)} width={760} footer={[<Button key="close" onClick={() => setModuleManageVisible(false)}>关闭</Button>, <Button key="create" type="primary" icon={<PlusOutlined />} onClick={() => openModuleModal()}>新建模块</Button>]}>
        <Table columns={moduleColumns} dataSource={modules} rowKey="id" loading={modulesLoading} pagination={false} locale={{ emptyText: currentProject ? '暂无模块' : '请先选择项目' }} />
      </Modal>

      <Modal title={editingModule ? '编辑模块' : '新建模块'} open={moduleModalVisible} onCancel={closeModuleModal} footer={[<Button key="cancel" onClick={closeModuleModal}>取消</Button>, <Button key="submit" type="primary" loading={moduleSubmitting} onClick={() => moduleForm.submit()}>保存</Button>]}>
        <Form form={moduleForm} layout="vertical" onFinish={saveModule}>
          <Form.Item name="name" label="模块名称" rules={[{ required: true, message: '请输入模块名称' }]}><Input placeholder="例如：用户中心" /></Form.Item>
          <Form.Item name="description" label="模块描述"><Input.TextArea rows={3} placeholder="简要描述这个模块的职责" /></Form.Item>
          <Form.Item name="sort_order" label="排序"><Input type="number" placeholder="0" /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DefinitionsList;
