/**
 * 用例列表页面（V2.0 层级一 - API 资产库）
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
  Popconfirm,
  Drawer,
  Typography,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  RobotOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useDebounce } from '../../hooks/useDebounce';
import api from '../../services/api';
import WorkspaceModuleHero from '../../components/WorkspaceModuleHero'

const { Text } = Typography;

interface ApiCase {
  id: number;
  definition_id: number;
  project_id: number;
  name: string;
  description: string | null;
  priority: string;
  case_type: string;
  request_data: any;
  environment_id: number | null;
  environment_name: string | null;
  assertion_rules: any[];
  extraction_rules: any[];
  pre_sql: string | null;
  post_sql: string | null;
  ai_generated: boolean;
  ai_confidence: number | null;
  status: string;
  fix_status: string;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  updated_by: number | null;
}

interface ApiDefinition {
  id: number;
  method: string;
  path: string;
  summary: string | null;
  response_schema?: Record<string, unknown> | null;
}

interface Environment {
  id: number;
  name: string;
}

const CasesList: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const definitionIdParam = searchParams.get('definition_id');

  // 状态管理
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<ApiCase[]>([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // 筛选条件
  const [filters, setFilters] = useState({
    definition_id: definitionIdParam ? Number(definitionIdParam) : undefined,
    priority: undefined as string | undefined,
    case_type: undefined as string | undefined,
    ai_generated: undefined as boolean | undefined,
    keyword: '',
  });

  const debouncedKeyword = useDebounce(filters.keyword, 300);

  // 下拉数据
  const [definitions, setDefinitions] = useState<ApiDefinition[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);

  // 弹窗状态
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [aiGenerateModalVisible, setAiGenerateModalVisible] = useState(false);
  const [batchExecuteModalVisible, setBatchExecuteModalVisible] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [executionResults, setExecutionResults] = useState<any>(null);
  const [currentRecord, setCurrentRecord] = useState<ApiCase | null>(null);
  const [aiGeneratedCase, setAiGeneratedCase] = useState<any>(null);
  const [aiGenerating, setAiGenerating] = useState(false);

  const [form] = Form.useForm();

  // 获取测试用例列表
  const fetchCases = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        skip: String((pagination.current - 1) * pagination.pageSize),
        limit: String(pagination.pageSize),
      });

      if (filters.definition_id) params.append('definition_id', String(filters.definition_id));
      if (filters.priority) params.append('priority', filters.priority);
      if (filters.case_type) params.append('case_type', filters.case_type);
      if (filters.ai_generated !== undefined) params.append('ai_generated', String(filters.ai_generated));
      if (debouncedKeyword) params.append('keyword', debouncedKeyword);

      const response = await api.get(`/api-cases?${params}`);

      if (response.code === 0) {
        setDataSource(response.data.items || []);
        setTotal(response.data.total || 0);
      } else {
        message.error(response.message || '获取数据失败');
      }
    } catch (error) {
      console.error('获取测试用例列表失败:', error);
      message.error('获取数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [pagination, filters.definition_id, filters.priority, filters.case_type, filters.ai_generated, debouncedKeyword]);

  // 获取接口定义列表（用于筛选）
  const fetchDefinitions = async () => {
    try {
      const response = await api.get('/api-definitions?limit=200');

      if (response.code === 0) {
        setDefinitions(response.data.items || []);
      }
    } catch (error) {
      console.error('获取接口定义失败:', error);
    }
  };

  // 获取环境列表
  const fetchEnvironments = async () => {
    try {
      const response = await api.get('/environments');

      if (response.code === 0) {
        setEnvironments(response.data.environments || []);
      }
    } catch (error) {
      console.error('获取环境列表失败:', error);
    }
  };

  useEffect(() => {
    fetchDefinitions();
    fetchEnvironments();
  }, []);

  // 创建测试用例
  const handleCreate = async (values: any) => {
    try {
      const response = await api.post(`/api-definitions/${values.definition_id}/cases`, values);

      if (response.code === 0) {
        message.success('创建成功');
        setCreateModalVisible(false);
        form.resetFields();
        fetchCases();
      } else {
        message.error(response.message || '创建失败');
      }
    } catch (error) {
      console.error('创建失败:', error);
      message.error('创建失败，请稍后重试');
    }
  };

  // 更新测试用例
  const handleUpdate = async (values: any) => {
    if (!currentRecord) return;

    setLoading(true);
    try {
      const response = await api.put(`/api-cases/${currentRecord.id}`, values);

      if (response.code === 0) {
        message.success('更新成功');
        setEditModalVisible(false);
        form.resetFields();
        fetchCases();
      } else {
        message.error(response.message || '更新失败');
      }
    } catch (error) {
      console.error('更新失败:', error);
      message.error('更新失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 删除测试用例
  const handleDelete = async (record: ApiCase) => {
    try {
      const response = await api.delete(`/api-cases/${record.id}`);

      if (response.code === 0) {
        message.success('删除成功');
        fetchCases();
      } else {
        message.error(response.message || '删除失败');
      }
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请稍后重试');
    }
  };

  // 打开编辑弹窗
  const openEditModal = (record: ApiCase) => {
    setCurrentRecord(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      priority: record.priority,
      case_type: record.case_type,
      environment_id: record.environment_id,
      status: record.status,
      fix_status: record.fix_status,
    });
    setEditModalVisible(true);
  };

  // AI 生成基准用例
  const handleAIGenerateBaseCase = async () => {
    if (!filters.definition_id) {
      message.warning('请先选择接口');
      return;
    }

    setAiGenerating(true);
    try {
      const response = await api.post(`/api-definitions/${filters.definition_id}/ai-generate-case`);

      if (response.code === 0) {
        setAiGeneratedCase(response.data);
        setAiGenerateModalVisible(true);
        message.success('AI 生成成功，请审核');
      } else {
        message.error(response.message || 'AI 生成失败');
      }
    } catch (error) {
      console.error('AI 生成失败:', error);
      message.error('AI 生成失败，请稍后重试');
    } finally {
      setAiGenerating(false);
    }
  };

  // 确认保存 AI 生成的用例
  const handleSaveAICase = async () => {
    if (!aiGeneratedCase) return;

    try {
      const response = await api.post(`/api-definitions/${filters.definition_id}/cases`, {
        ...aiGeneratedCase,
        ai_generated: true,
        ai_confidence: aiGeneratedCase.ai_confidence,
        case_type: 'base',
        priority: 'P0'
      });

      if (response.code === 0) {
        message.success('保存成功');
        setAiGenerateModalVisible(false);
        setAiGeneratedCase(null);
        fetchCases();
      } else {
        message.error(response.message || '保存失败');
      }
    } catch (error) {
      console.error('保存失败:', error);
      message.error('保存失败，请稍后重试');
    }
  };

  // AI 生成断言
  const handleAIGenerateAssertions = async () => {
    if (!filters.definition_id) {
      message.warning('请先选择接口');
      return;
    }

    setAiGenerating(true);
    try {
      // 获取接口定义
      const definition = definitions.find(d => d.id === filters.definition_id);
      if (!definition) {
        message.error('接口定义不存在');
        return;
      }

      const response = await api.post('/ai-generate-assertions', {
        response_schema: definition.response_schema || {}
      });

      if (response.code === 0) {
        // 将生成的断言规则添加到表单中
        const existingAssertions = form.getFieldValue('assertion_rules') || [];
        form.setFieldValue('assertion_rules', [...existingAssertions, ...(response.data.assertion_rules || [])]);
        message.success('AI 生成断言成功');
      } else {
        message.error(response.message || 'AI 生成失败');
      }
    } catch (error) {
      console.error('AI 生成断言失败:', error);
      message.error('AI 生成失败，请稍后重试');
    } finally {
      setAiGenerating(false);
    }
  };

  // 批量执行用例
  const handleBatchExecute = async (values: any) => {
    setLoading(true);
    setExecutionResults(null);

    try {
      const response = await api.post('/api-cases/batch-execute', {
        case_ids: selectedRowKeys,
        environment_id: values.environment_id,
        variables: {},
        max_concurrent: 5,
      });

      if (response.code === 0) {
        setExecutionResults(response.data);
        message.success(`批量执行完成：成功 ${response.data.success}，失败 ${response.data.failed}`);
      } else {
        message.error(response.message || '批量执行失败');
      }
    } catch (error) {
      console.error('批量执行失败:', error);
      message.error('批量执行失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 优先级标签颜色
  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      P0: 'red',
      P1: 'orange',
      P2: 'blue',
      P3: 'default',
    };
    return colors[priority] || 'default';
  };

  // 用例类型标签
  const getCaseTypeTag = (caseType: string) => {
    const typeMap: Record<string, { text: string; color: string }> = {
      base: { text: '基准用例', color: 'green' },
      business: { text: '业务测试', color: 'blue' },
      performance: { text: '性能测试', color: 'orange' },
      security: { text: '安全测试', color: 'red' },
      corner: { text: '边界测试', color: 'purple' },
    };
    const type = typeMap[caseType] || { text: caseType, color: 'default' };
    return <Tag color={type.color}>{type.text}</Tag>;
  };

  // 表格列定义
  const columns: ColumnsType<ApiCase> = [
    {
      title: '用例名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string, record: ApiCase) => (
        <div>
          <div style={{ fontWeight: 'bold' }}>{name}</div>
          {record.ai_generated && (
            <div style={{ marginTop: '4px' }}>
              <Tag icon={<RobotOutlined />} color="blue">AI 生成</Tag>
              {record.ai_confidence && (
                <span style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginLeft: '4px' }}>
                  {Math.round(record.ai_confidence * 100)}%
                </span>
              )}
            </div>
          )}
        </div>
      ),
    },
    {
      title: '所属接口',
      dataIndex: 'definition_id',
      key: 'definition_id',
      width: 150,
      render: (definitionId: number) => {
        const def = definitions.find(d => d.id === definitionId);
        if (!def) return '-';
        return (
          <div>
            <Tag color={def.method === 'GET' ? 'green' : def.method === 'POST' ? 'blue' : 'orange'}>
              {def.method}
            </Tag>
            <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
              {def.path}
            </div>
          </div>
        );
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (priority: string) => (
        <Tag color={getPriorityColor(priority)}>{priority}</Tag>
      ),
      filters: [
        { text: 'P0', value: 'P0' },
        { text: 'P1', value: 'P1' },
        { text: 'P2', value: 'P2' },
        { text: 'P3', value: 'P3' },
      ],
    },
    {
      title: '用例类型',
      dataIndex: 'case_type',
      key: 'case_type',
      width: 100,
      render: getCaseTypeTag,
    },
    {
      title: '环境',
      dataIndex: 'environment_name',
      key: 'environment_name',
      width: 100,
      render: (envName: string | null) => envName || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={status === 'active' ? 'success' : 'default'}>
          {status === 'active' ? '活跃' : '归档'}
        </Tag>
      ),
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
      width: 220,
      fixed: 'right',
      render: (_: any, record: ApiCase) => (
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
          <Tooltip title="编辑">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEditModal(record)}
            />
          </Tooltip>
          <Tooltip title="查看执行记录">
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => navigate(`/operations/executions?case_id=${record.id}&definition_id=${record.definition_id}`)}
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
        </Space>
      ),
    },
  ];

  return (
    <div className="workspace-page workspace-list-page">
      <WorkspaceModuleHero
        eyebrow="API Hub"
        title="测试用例"
        description="基于接口定义维护测试用例并执行验证。"
        metrics={[
          { label: '当前页用例', value: dataSource.length },
          { label: '用例总数', value: total },
          { label: '已选择', value: selectedRowKeys.length },
        ]}
      />
      <Card className="workspace-table-card workspace-list-page__card" bordered={false}>
        {/* 顶部操作栏 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Input
              placeholder="搜索用例名称"
              prefix={<SearchOutlined />}
              value={filters.keyword}
              onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
              allowClear
            />
          </Col>
          <Col span={4}>
            <Select
              placeholder="所属接口"
              style={{ width: '100%' }}
              value={filters.definition_id}
              onChange={(value) => setFilters({ ...filters, definition_id: value })}
              allowClear
              showSearch
              optionFilterProp="children"
            >
              {definitions.map((def) => (
                <Select.Option key={def.id} value={def.id}>
                  {def.method} {def.path} - {def.summary || ''}
                </Select.Option>
              ))}
            </Select>
          </Col>
          <Col span={3}>
            <Select
              placeholder="优先级"
              style={{ width: '100%' }}
              value={filters.priority}
              onChange={(value) => setFilters({ ...filters, priority: value })}
              allowClear
            >
              <Select.Option value="P0">P0</Select.Option>
              <Select.Option value="P1">P1</Select.Option>
              <Select.Option value="P2">P2</Select.Option>
              <Select.Option value="P3">P3</Select.Option>
            </Select>
          </Col>
          <Col span={11} style={{ textAlign: 'right' }}>
            <Space>
              {filters.definition_id && (
                <Button
                  type="primary"
                  icon={<RobotOutlined />}
                  onClick={handleAIGenerateBaseCase}
                  loading={aiGenerating}
                >
                  AI 生成基准用例
                </Button>
              )}
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchCases}
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
                新建用例
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
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys),
          }}
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
          scroll={{ x: 1200, y: 'calc(100vh - 420px)' }}
          title={() => (
            selectedRowKeys.length > 0 && (
              <Space>
                <span>已选择 {selectedRowKeys.length} 个用例</span>
                <Button
                  type="primary"
                  size="small"
                  icon={<PlayCircleOutlined />}
                  onClick={() => setBatchExecuteModalVisible(true)}
                >
                  批量执行
                </Button>
              </Space>
            )
          )}
        />
      </Card>

      {/* 创建弹窗 */}
      <Modal
        title="新建测试用例"
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
            name="definition_id"
            label="所属接口"
            rules={[{ required: true, message: '请选择所属接口' }]}
          >
            <Select
              placeholder="请选择所属接口"
              showSearch
              optionFilterProp="children"
            >
              {definitions.map((def) => (
                <Select.Option key={def.id} value={def.id}>
                  {def.method} {def.path} - {def.summary || ''}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="name"
            label="用例名称"
            rules={[{ required: true, message: '请输入用例名称' }]}
          >
            <Input placeholder="例如: 正常获取用户列表" />
          </Form.Item>
          <Form.Item
            name="description"
            label="用例描述"
          >
            <Input.TextArea rows={3} placeholder="用例的详细描述" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="priority"
                label="优先级"
                initialValue="P2"
              >
                <Select>
                  <Select.Option value="P0">P0</Select.Option>
                  <Select.Option value="P1">P1</Select.Option>
                  <Select.Option value="P2">P2</Select.Option>
                  <Select.Option value="P3">P3</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="case_type"
                label="用例类型"
                initialValue="business"
              >
                <Select>
                  <Select.Option value="base">基准用例</Select.Option>
                  <Select.Option value="business">业务测试</Select.Option>
                  <Select.Option value="performance">性能测试</Select.Option>
                  <Select.Option value="security">安全测试</Select.Option>
                  <Select.Option value="corner">边界测试</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="environment_id"
            label="执行环境"
          >
            <Select placeholder="请选择执行环境" allowClear>
              {environments.map((env) => (
                <Select.Option key={env.id} value={env.id}>
                  {env.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* AI 生成结果弹窗 */}
      <Modal
        title={
          <span>
            <RobotOutlined /> AI 生成基准用例
          </span>
        }
        open={aiGenerateModalVisible}
        onCancel={() => setAiGenerateModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setAiGenerateModalVisible(false)}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            onClick={handleSaveAICase}
          >
            确认保存
          </Button>,
        ]}
        width={800}
      >
        {aiGeneratedCase && (
          <div>
<Row gutter={[16, 16]}>
              <Col span={24}>
                <div style={{ fontWeight: 'bold', marginBottom: 8 }}>用例名称</div>
                <div>{aiGeneratedCase.name}</div>
              </Col>
              <Col span={24}>
                <div style={{ fontWeight: 'bold', marginBottom: 8 }}>用例描述</div>
                <div>{aiGeneratedCase.description || '-'}</div>
              </Col>
              <Col span={24}>
                <div style={{ fontWeight: 'bold', marginBottom: 8 }}>入参</div>
                <pre style={{ background: 'var(--bg-tertiary)', padding: 12, borderRadius: 4 }}>
                  {JSON.stringify(aiGeneratedCase.request_data, null, 2)}
                </pre>
              </Col>
              <Col span={24}>
                <div style={{ fontWeight: 'bold', marginBottom: 8 }}>断言规则</div>
                <div style={{ background: 'var(--bg-tertiary)', padding: 12, borderRadius: 4 }}>
                  {aiGeneratedCase.assertion_rules?.map((rule: any, index: number) => (
                    <div key={index} style={{ marginBottom: 4 }}>
                      <Tag color="blue">{rule.operator}</Tag>
                      <span>{rule.property || rule.source}</span>
                      {rule.value !== undefined && <span> = {JSON.stringify(rule.value)}</span>}
                    </div>
                  )) || '-'}
                </div>
              </Col>
              {aiGeneratedCase.extraction_rules && aiGeneratedCase.extraction_rules.length > 0 && (
                <Col span={24}>
                  <div style={{ fontWeight: 'bold', marginBottom: 8 }}>变量提取</div>
                  <div style={{ background: 'var(--bg-tertiary)', padding: 12, borderRadius: 4 }}>
                    {aiGeneratedCase.extraction_rules.map((rule: any, index: number) => (
                      <div key={index}>
                        <span>{rule.var_name || rule.variable_name} = {rule.field || rule.json_path}</span>
                      </div>
                    ))}
                  </div>
                </Col>
              )}
            </Row>
          </div>
        )}
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        title="编辑测试用例"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
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
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleUpdate}
        >
          <Form.Item
            name="name"
            label="用例名称"
            rules={[{ required: true, message: '请输入用例名称' }]}
          >
            <Input placeholder="例如: 正常获取用户列表" />
          </Form.Item>
          <Form.Item
            name="description"
            label="用例描述"
          >
            <Input.TextArea rows={3} placeholder="用例的详细描述" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="priority"
                label="优先级"
              >
                <Select>
                  <Select.Option value="P0">P0</Select.Option>
                  <Select.Option value="P1">P1</Select.Option>
                  <Select.Option value="P2">P2</Select.Option>
                  <Select.Option value="P3">P3</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="case_type"
                label="用例类型"
              >
                <Select>
                  <Select.Option value="base">基准用例</Select.Option>
                  <Select.Option value="business">业务测试</Select.Option>
                  <Select.Option value="performance">性能测试</Select.Option>
                  <Select.Option value="security">安全测试</Select.Option>
                  <Select.Option value="corner">边界测试</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="environment_id"
            label="执行环境"
          >
            <Select placeholder="请选择执行环境" allowClear>
              {environments.map((env) => (
                <Select.Option key={env.id} value={env.id}>
                  {env.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Row gutter={16}>
            <Col span={24}>
              <Form.Item
                name="assertion_rules"
                label="断言规则"
              >
                <div>
                  <Button
                    type="link"
                    icon={<RobotOutlined />}
                    onClick={handleAIGenerateAssertions}
                    loading={aiGenerating}
                    size="small"
                  >
                    AI 生成断言
                  </Button>
                </div>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="status"
                label="状态"
              >
                <Select>
                  <Select.Option value="active">活跃</Select.Option>
                  <Select.Option value="archived">归档</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="fix_status"
                label="修复状态"
              >
                <Select>
                  <Select.Option value="normal">正常</Select.Option>
                  <Select.Option value="fix_required">需要修复</Select.Option>
                  <Select.Option value="fixed">已修复</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 详情抽屉 */}
      <Drawer
        title="测试用例详情"
        placement="right"
        width={720}
        open={detailDrawerVisible}
        onClose={() => setDetailDrawerVisible(false)}
      >
        {currentRecord && (
          <div>
            <Row gutter={[16, 16]}>
              <Col span={24}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>用例名称</div>
                <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{currentRecord.name}</div>
                {currentRecord.ai_generated && (
                  <div style={{ marginTop: '8px' }}>
                    <Tag icon={<RobotOutlined />} color="blue">AI 生成</Tag>
                    {currentRecord.ai_confidence && (
                      <span style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginLeft: '4px' }}>
                        置信度: {Math.round(currentRecord.ai_confidence * 100)}%
                      </span>
                    )}
                  </div>
                )}
              </Col>
              <Col span={24}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>用例描述</div>
                <div>{currentRecord.description || '-'}</div>
              </Col>
              {currentRecord.request_data && (
                <Col span={24}>
                  <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>请求数据</div>
                  <div style={{ background: 'var(--bg-tertiary)', padding: '12px', borderRadius: '4px' }}>
                    {currentRecord.request_data.path_params && (
                      <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>路径参数 (Path Parameters)</div>
                        <pre style={{ margin: 0, fontSize: '12px', background: 'var(--bg-elevated)', padding: '8px', borderRadius: '4px' }}>
                          {JSON.stringify(currentRecord.request_data.path_params, null, 2)}
                        </pre>
                      </div>
                    )}
                    {currentRecord.request_data.headers && (
                      <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>请求头 (Headers)</div>
                        <pre style={{ margin: 0, fontSize: '12px', background: 'var(--bg-elevated)', padding: '8px', borderRadius: '4px' }}>
                          {JSON.stringify(currentRecord.request_data.headers, null, 2)}
                        </pre>
                      </div>
                    )}
                    {currentRecord.request_data.body && (
                      <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>请求体 (Body)</div>
                        <pre style={{ margin: 0, fontSize: '12px', background: 'var(--bg-elevated)', padding: '8px', borderRadius: '4px' }}>
                          {JSON.stringify(currentRecord.request_data.body, null, 2)}
                        </pre>
                      </div>
                    )}
                    {!currentRecord.request_data.path_params && !currentRecord.request_data.headers && !currentRecord.request_data.body && (
                      <div>
                        <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>查询参数 (Query Parameters)</div>
                        <pre style={{ margin: 0, fontSize: '12px', background: 'var(--bg-elevated)', padding: '8px', borderRadius: '4px' }}>
                          {JSON.stringify(currentRecord.request_data, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </Col>
              )}
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>所属接口</div>
                <div>
                  {(() => {
                    const def = definitions.find(d => d.id === currentRecord.definition_id);
                    return def ? `${def.method} ${def.path}` : '-';
                  })()}
                </div>
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>执行环境</div>
                <div>{currentRecord.environment_name || '-'}</div>
              </Col>
              <Col span={8}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>优先级</div>
                <Tag color={getPriorityColor(currentRecord.priority)}>{currentRecord.priority}</Tag>
              </Col>
              <Col span={8}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>用例类型</div>
                {getCaseTypeTag(currentRecord.case_type)}
              </Col>
              <Col span={8}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>状态</div>
                <Tag color={currentRecord.status === 'active' ? 'success' : 'default'}>
                  {currentRecord.status === 'active' ? '活跃' : '归档'}
                </Tag>
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>创建时间</div>
                <div>{new Date(currentRecord.created_at).toLocaleString('zh-CN')}</div>
              </Col>
              <Col span={12}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>更新时间</div>
                <div>{new Date(currentRecord.updated_at).toLocaleString('zh-CN')}</div>
              </Col>
              {currentRecord.assertion_rules && currentRecord.assertion_rules.length > 0 && (
                <Col span={24}>
                  <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>断言规则</div>
                  <div style={{ background: 'var(--bg-tertiary)', padding: '12px', borderRadius: '4px' }}>
                    {currentRecord.assertion_rules.map((rule: any, index: number) => (
                      <div key={index} style={{ marginBottom: '4px' }}>
                        <Tag color="blue">{rule.operator}</Tag>
                        <span>{rule.field}</span>
                        {rule.value !== undefined && <span> = {JSON.stringify(rule.value)}</span>}
                      </div>
                    ))}
                  </div>
                </Col>
              )}
              {currentRecord.extraction_rules && currentRecord.extraction_rules.length > 0 && (
                <Col span={24}>
                  <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>变量提取规则</div>
                  <div style={{ background: 'var(--bg-tertiary)', padding: '12px', borderRadius: '4px' }}>
                    {currentRecord.extraction_rules.map((rule: any, index: number) => (
                      <div key={index} style={{ marginBottom: '4px' }}>
                        <span>提取 {rule.field} → {rule.var_name}</span>
                      </div>
                    ))}
                  </div>
                </Col>
              )}
            </Row>
          </div>
        )}
      </Drawer>

      {/* 批量执行弹窗 */}
      <Modal
        title="批量执行用例"
        open={batchExecuteModalVisible}
        onCancel={() => {
          setBatchExecuteModalVisible(false);
          setExecutionResults(null);
        }}
        footer={null}
        width={800}
      >
        {!executionResults ? (
          <Form
            layout="vertical"
            onFinish={handleBatchExecute}
          >
<Form.Item
              name="environment_id"
              label="执行环境"
              rules={[{ required: true, message: '请选择执行环境' }]}
            >
              <Select placeholder="请选择环境">
                {environments.map((env) => (
                  <Select.Option key={env.id} value={env.id}>
                    {env.name}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={loading}
                  htmlType="submit"
                >
                  开始执行
                </Button>
                <Button onClick={() => setBatchExecuteModalVisible(false)}>
                  取消
                </Button>
              </Space>
            </Form.Item>
          </Form>
        ) : (
          <div>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              {/* 执行统计 */}
              <Row gutter={16}>
                <Col span={6}>
                  <Card>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 24, fontWeight: 'bold' }}>{executionResults.total}</div>
                      <div style={{ color: 'var(--text-tertiary)' }}>总数</div>
                    </div>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 24, fontWeight: 'bold', color: '#52c41a' }}>{executionResults.success}</div>
                      <div style={{ color: 'var(--text-tertiary)' }}>成功</div>
                    </div>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 24, fontWeight: 'bold', color: '#f5222d' }}>{executionResults.failed}</div>
                      <div style={{ color: 'var(--text-tertiary)' }}>失败</div>
                    </div>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 24, fontWeight: 'bold' }}>{executionResults.total_time}ms</div>
                      <div style={{ color: 'var(--text-tertiary)' }}>总耗时</div>
                    </div>
                  </Card>
                </Col>
              </Row>

              {/* 执行结果列表 */}
              <div>
                <Text strong>执行结果</Text>
                <div style={{ marginTop: 8, maxHeight: 400, overflow: 'auto' }}>
                  {executionResults.cases.map((result: any, index: number) => (
                    <Card key={index} size="small" style={{ marginBottom: 8 }}>
                      <Space>
                        <Tag color={result.status === 'success' ? 'success' : 'error'}>
                          {result.status === 'success' ? '成功' : '失败'}
                        </Tag>
                        <Text>{result.case_name}</Text>
                        <Text type="secondary">{result.response_time}ms</Text>
                      </Space>
                      {result.error && (
                        <div style={{ marginTop: 4, color: '#f5222d' }}>
                          {result.error}
                        </div>
                      )}
                      {result.assertions && result.assertions.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          {result.assertions.map((assertion: any, aIndex: number) => (
                            <div key={aIndex} style={{ fontSize: 12 }}>
                              <Tag color={assertion.passed ? 'success' : 'error'}>
                                {assertion.passed ? '通过' : '失败'}
                              </Tag>
                              <span>{assertion.message}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              </div>

              <Button onClick={() => setBatchExecuteModalVisible(false)}>
                关闭
              </Button>
            </Space>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default CasesList;

