import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Space, Tag, message, Modal, Form, Select, Spin, Empty, Table, Tabs, Row, Col, Input, Drawer, Descriptions, Alert, Progress, Collapse, Checkbox, Divider } from 'antd';
import { PlayCircleOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, PlusOutlined, EnvironmentOutlined, HistoryOutlined, PlusSquareOutlined } from '@ant-design/icons';
import { useProjectStore } from '../../store/project';
import { get, post, del } from '../../services/request';
import { ExecutionStatus, TestType } from '../../constants/script';
import JsonEditor from '../../components/JsonEditor';
import GroupEndpointTree from '../../components/GroupEndpointTree';

const { Option } = Select;
const { TextArea } = Input;

const Scripts: React.FC = () => {
  const navigate = useNavigate();
  const { currentProject, currentVersion } = useProjectStore();
  const [groups, setGroups] = useState<any[]>([]);
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const [scripts, setScripts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [scriptsLoading, setScriptsLoading] = useState(false);
  const [generateVisible, setGenerateVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [executeVisible, setExecuteVisible] = useState(false);
  const [executionsVisible, setExecutionsVisible] = useState(false);
  const [executionDetailVisible, setExecutionDetailVisible] = useState(false);
  const [selectedScript, setSelectedScript] = useState<any>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<any>(null);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [selectedEndpointId, setSelectedEndpointId] = useState<number | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<any>(null);
  const [executeForm] = Form.useForm();
  const [environments, setEnvironments] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filterTestType, setFilterTestType] = useState<string | undefined>(undefined);
  const [executions, setExecutions] = useState<any[]>([]);
  const [executionsLoading, setExecutionsLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [editedHeaders, setEditedHeaders] = useState<Array<{ key: string; value: string }>>([]);
  const [body, setBody] = useState<string>('');
  const [allEndpoints, setAllEndpoints] = useState<any[]>([]);
  const [selectedEndpointIds, setSelectedEndpointIds] = useState<number[]>([]);
  const [selectedTestTypes, setSelectedTestTypes] = useState<string[]>([TestType.POSITIVE, TestType.NEGATIVE]);
  const [testTypes, setTestTypes] = useState<any>({ preset_types: [], custom_types: [] });
  const [customTypes, setCustomTypes] = useState<any[]>([]);
  const [addCustomTypeVisible, setAddCustomTypeVisible] = useState(false);
  const [customTypeForm] = Form.useForm();

  // 获取分组列表
  const fetchGroups = useCallback(async () => {
    try {
      const result = await get('/api-integration/endpoints/groups', {
        count_type: 'script'  // 统计脚本数量
      });
      setGroups(result.groups || []);
    } catch (error) {
      console.error('获取分组列表失败:', error);
    }
  }, []);

  // 获取接口列表
  const fetchEndpoints = useCallback(async (groupId?: number) => {
    try {
      let allEndpoints = [];
      let skip = 0;
      const limit = 200;
      let hasMore = true;

      while (hasMore) {
        const params: Record<string, any> = {
          skip,
          limit,
        };
        if (groupId !== undefined && groupId !== null) {
          params.group_id = groupId;
        }
        const result = await get('/api-integration/endpoints', params);
        allEndpoints = [...allEndpoints, ...(result.endpoints || [])];
        
        if (result.endpoints.length < limit) {
          hasMore = false;
        } else {
          skip += limit;
        }
      }
      
      return allEndpoints;
    } catch (error) {
      console.error('获取接口列表失败:', error);
      return [];
    }
  }, []);

  // 获取脚本列表
  const fetchScripts = useCallback(async (endpointId?: number) => {
    setScriptsLoading(true);
    try {
      const params: Record<string, any> = {};
      if (endpointId) {
        params.endpoint_id = endpointId;
      }
      if (filterTestType) {
        params.test_type = filterTestType;
      }
      const result = await get('/api-integration/scripts', params);
      setScripts(result.scripts || []);
      setTotal(result.total || 0);
    } catch (error) {
      console.error('获取脚本列表失败:', error);
      message.error('获取脚本列表失败');
    } finally {
      setScriptsLoading(false);
    }
  }, [filterTestType]);

  // 获取环境列表
  const fetchEnvironments = useCallback(async () => {
    try {
      const result = await get('/environments');
      setEnvironments(result.environments || []);
    } catch (error) {
      console.error('获取环境列表失败:', error);
    }
  }, []);

  // 获取所有有脚本的接口列表
  const fetchAllEndpoints = async () => {
    try {
      setLoading(true);
      let allEndpoints = [];
      let skip = 0;
      const limit = 200;
      let hasMore = true;

      while (hasMore) {
        const result = await get('/api-integration/endpoints', { skip, limit });
        allEndpoints = [...allEndpoints, ...(result.endpoints || [])];
        if (result.endpoints.length < limit) {
          hasMore = false;
        } else {
          skip += limit;
        }
      }

      setAllEndpoints(allEndpoints);
      return allEndpoints;
    } catch (error) {
      console.error('获取接口列表失败:', error);
      message.error('获取接口列表失败');
      return [];
    } finally {
      setLoading(false);
    }
  };

  // 获取测试类型列表
  const fetchTestTypes = async () => {
    try {
      const result = await get('/api-integration/test-types');
      setTestTypes(result || { preset_types: [], custom_types: [] });
    } catch (error) {
      console.error('获取测试类型失败:', error);
    }
  };

  // 生成测试脚本
  const handleGenerate = async () => {
    if (selectedEndpointIds.length === 0) {
      message.warning('请至少选择一个接口');
      return;
    }

    if (selectedTestTypes.length === 0) {
      message.warning('请至少选择一种测试类型');
      return;
    }

    setLoading(true);
    setGenerateVisible(false);
    try {
      // 构建自定义类型描述
      const customTypeDescriptions: Record<string, string> = {};
      customTypes.forEach(ct => {
        if (selectedTestTypes.includes(ct.code)) {
          customTypeDescriptions[ct.code] = ct.description;
        }
      });

      const result = await post('/api-integration/scripts/generate', {
        endpoint_ids: selectedEndpointIds,
        test_types: selectedTestTypes,
        custom_type_descriptions: customTypeDescriptions
      }, 120000);

      message.success(`成功生成 ${result?.scripts_count || 0} 个测试脚本`);
      setSelectedEndpointIds([]);
      setSelectedTestTypes([TestType.POSITIVE, TestType.NEGATIVE]);
      setCustomTypes([]);

      await new Promise(resolve => setTimeout(resolve, 500));

      if (selectedEndpointId) {
        fetchScripts(selectedEndpointId);
      }
    } catch (error) {
      console.error('生成失败:', error);
      message.error('生成失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 添加自定义测试类型
  const handleAddCustomType = async () => {
    try {
      const values = await customTypeForm.validateFields();

      const result = await post('/api-integration/test-types', values);

      message.success('添加成功');
      customTypeForm.resetFields();
      setAddCustomTypeVisible(false);
      fetchTestTypes();
    } catch (error) {
      console.error('添加失败:', error);
      message.error('添加失败，请稍后重试');
    }
  };

  // 组件加载时获取数据
  useEffect(() => {
    const initializeData = async () => {
      // 并行获取所有基础数据
      await Promise.all([
        fetchGroups(),
        fetchEnvironments(),
        fetchTestTypes()
      ]);
      
      // 获取所有接口（包含脚本数量）
      const allEndpoints = await fetchAllEndpoints();
      
      // 过滤出有脚本的接口，并设置到 endpoints 状态
      const endpointsWithScripts = allEndpoints.filter(e => e.script_count > 0);
      setEndpoints(endpointsWithScripts);
    };
    
    initializeData();
  }, [fetchGroups, fetchEnvironments]);

  // 处理分组选择
  const handleGroupSelect = async (groupId: number | null) => {
    setSelectedGroupId(groupId);
    setSelectedEndpointId(null);
    setSelectedEndpoint(null);
    setPage(1);
    if (groupId !== null) {
      const endpointList = await fetchEndpoints(groupId);
      setEndpoints(endpointList);
    } else {
      setEndpoints([]);
    }
    setScripts([]);
  };

  // 处理接口选择
  const handleEndpointSelect = async (endpointId: number | null) => {
    setSelectedEndpointId(endpointId);
    setPage(1);
    if (endpointId !== null) {
      const endpoint = endpoints.find(e => e.id === endpointId);
      setSelectedEndpoint(endpoint);
      await fetchScripts(endpointId);
    } else {
      setSelectedEndpoint(null);
      setScripts([]);
    }
  };

  // 执行脚本
  const handleExecuteScript = async (script: any) => {
    if (environments.length === 0) {
      message.warning('请先添加环境后再执行脚本');
      return;
    }
    setSelectedScript(script);
    setSelectedEndpoint(endpoints.find(e => e.id === script.endpoint_id));
    setExecuteVisible(true);

    // 预加载脚本定义的内容
    const scriptHeaders = script.script_content?.headers || {};
    const headersArray = Object.entries(scriptHeaders).map(([key, value]) => ({
      key,
      value: String(value),
    }));
    setEditedHeaders(headersArray);

    const scriptBody = script.script_content?.request || {};
    const bodyJson = Object.keys(scriptBody).length > 0
      ? JSON.stringify(scriptBody, null, 2)
      : '';
    setBody(bodyJson);
  };

  // 提交执行
  const handleExecuteSubmit = async () => {
    try {
      const values = await executeForm.validateFields();
      setExecuting(true);

      const customHeaders = editedHeaders.reduce((acc, item) => {
        if (item.key) {
          acc[item.key] = item.value;
        }
        return acc;
      }, {} as Record<string, string>);

      const customBody = body && body.trim() ? JSON.parse(body) : undefined;

      const result = await post(`/api-integration/scripts/${selectedScript.id}/execute`, {
        environment_id: values.environment_id,
        variables: values.variables ? JSON.parse(values.variables) : undefined,
        headers: customHeaders,
        body: customBody,
      });

      message.success('执行成功');
      setExecuteVisible(false);
      setEditedHeaders([]);
      setBody('');
    } catch (error: any) {
      console.error('执行失败:', error);
      message.error(error.message || '执行失败');
    } finally {
      setExecuting(false);
    }
  };

  // 查看执行记录
  const handleViewExecutions = async (item: any) => {
    setSelectedScript(item);
    setExecutionsVisible(true);
    setExecutionsLoading(true);
    try {
      const result = await get(`/api-integration/scripts/${item.id}/executions`, { limit: 50 });
      setExecutions(result.executions || []);
    } catch (error) {
      console.error('获取执行记录失败:', error);
      message.error('获取执行记录失败');
    } finally {
      setExecutionsLoading(false);
    }
  };

  // 查看执行详情
  const handleViewExecutionDetail = async (execution: any) => {
    try {
      const fullDetail = await get(`/api-integration/executions/${execution.id}`);
      setSelectedExecution(fullDetail);
      setExecutionDetailVisible(true);
    } catch (error) {
      setSelectedExecution(execution);
      setExecutionDetailVisible(true);
    }
  };

  // 查看脚本详情
  const handleViewDetail = (script: any) => {
    setSelectedScript(script);
    setSelectedEndpoint(endpoints.find(e => e.id === script.endpoint_id));
    setDetailVisible(true);
  };

  // 删除脚本
  const handleDeleteScript = async (id: number) => {
    try {
      await del(`/api-integration/scripts/${id}`);
      message.success('删除成功');
      if (selectedEndpointId) {
        fetchScripts(selectedEndpointId);
      }
    } catch (error: any) {
      message.error(error.message || '删除失败');
    }
  };

  // 脚本表格列
  const columns = [
    {
      title: '脚本名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <a onClick={() => handleViewDetail(record)}>{text}</a>
      ),
    },
    {
      title: '测试类型',
      dataIndex: 'test_type',
      key: 'test_type',
      render: (type: string) => {
        const typeMap: Record<string, { color: string; text: string }> = {
          [TestType.POSITIVE]: { color: 'green', text: '正向测试' },
          [TestType.NEGATIVE]: { color: 'red', text: '逆向测试' },
          [TestType.BOUNDARY]: { color: 'orange', text: '边界测试' },
          [TestType.EXCEPTION]: { color: 'purple', text: '异常测试' },
        };
        const { color, text } = typeMap[type] || { color: 'default', text: type };
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          [ExecutionStatus.PASSED]: { color: 'success', text: '通过' },
          [ExecutionStatus.FAILED]: { color: 'error', text: '失败' },
          [ExecutionStatus.SKIPPED]: { color: 'default', text: '跳过' },
          [ExecutionStatus.RUNNING]: { color: 'processing', text: '运行中' },
        };
        const { color, text } = statusMap[status] || { color: 'default', text: status };
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => handleExecuteScript(record)}
          >
            执行
          </Button>
          <Button
            type="link"
            size="small"
            icon={<HistoryOutlined />}
            onClick={() => handleViewExecutions(record)}
          >
            记录
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteScript(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  // 如果没有选择项目或版本，显示骨架屏
  if (!currentProject || !currentVersion) {
    return (
      <div style={{ padding: '24px' }}>
        <Card>
          <Spin spinning={true}>
            <div style={{ height: 400 }} />
          </Spin>
        </Card>
      </div>
    );
  }


  return (
    <div>
      <Card
        title={
          <Space>
            <span>测试脚本</span>
            <Tag color="blue">{currentProject.name}</Tag>
            <Tag color="green">{currentVersion.version_number}</Tag>
          </Space>
        }
        extra={
          <Space>
            <Button
              icon={<PlusOutlined />}
              onClick={() => {
                navigate('/api/endpoints');
              }}
            >
              生成测试脚本
            </Button>
          </Space>
        }
      >
        <Row>
          {/* 左侧分组接口树 */}
          <Col 
            span={5}
            style={{ 
              borderRight: '1px solid #f0f0f0', 
              padding: '16px', 
              backgroundColor: '#fafafa'
            }}
          >
            <div style={{ height: 500, overflowY: 'auto' }}>
              <GroupEndpointTree
                groups={groups}
                endpoints={endpoints}
                selectedGroupId={selectedGroupId}
                selectedEndpointId={selectedEndpointId}
                onGroupSelect={handleGroupSelect}
                onEndpointSelect={handleEndpointSelect}
                showOnlyWithScripts={true}
              />
            </div>
          </Col>

          {/* 右侧脚本列表 */}
          <Col span={19}>
            <div style={{ padding: '16px' }}>
              {/* 标题和工具栏 */}
              <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 16, fontWeight: 500, color: '#333' }}>
                  {selectedEndpoint
                    ? `${selectedEndpoint.method} ${selectedEndpoint.path} 的脚本 共 (${total}) 条`
                    : selectedGroupId
                    ? '请选择接口查看脚本'
                    : '请选择分组'
                  }
                </span>
                <Space>
                  {selectedEndpoint && (
                    <Select
                      placeholder="筛选测试类型"
                      style={{ width: 120 }}
                      allowClear
                      value={filterTestType}
                      onChange={(value) => {
                        setFilterTestType(value);
                        setPage(1);
                      }}
                    >
                      <Option value={TestType.POSITIVE}>正向测试</Option>
                      <Option value={TestType.NEGATIVE}>逆向测试</Option>
                      <Option value={TestType.BOUNDARY}>边界测试</Option>
                      <Option value={TestType.EXCEPTION}>异常测试</Option>
                    </Select>
                  )}
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={() => {
                      if (selectedEndpointId) {
                        fetchScripts(selectedEndpointId);
                      }
                    }}
                    loading={scriptsLoading}
                  >
                    刷新
                  </Button>
                </Space>
              </div>

              {/* 脚本列表 */}
              <div>
                {scripts.length === 0 ? (
                  <Empty
                    description={selectedEndpoint ? '该接口暂无测试脚本' : '请选择接口查看脚本'}
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                ) : (
                  <Table
                    columns={columns}
                    dataSource={scripts}
                    rowKey="id"
                    loading={scriptsLoading}
                    scroll={{ y: 500 }}
                    pagination={{
                      current: page,
                      pageSize,
                      total,
                      showSizeChanger: true,
                      showTotal: (total) => `共 ${total} 条`,
                      onChange: (page, pageSize) => {
                        setPage(page);
                        setPageSize(pageSize);
                      },
                    }}
                  />
                )}
              </div>
              </div>
            </Col>
        </Row>
      </Card>

      {/* 执行脚本弹窗 */}
      <Modal
        title={selectedScript ? `执行脚本: ${selectedScript.name}` : `执行接口: ${selectedEndpoint?.method} ${selectedEndpoint?.path}`}
        open={executeVisible}
        onCancel={() => {
          setExecuteVisible(false);
          setEditedHeaders([]);
          setBody('');
        }}
        onOk={handleExecuteSubmit}
        confirmLoading={executing}
        width={1000}
      >
        {environments.length === 0 && (
          <Alert
            message="暂无环境"
            description="请先前往项目管理页面添加环境后再执行脚本"
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            action={
              <Button type="link" size="small" onClick={() => navigate('/projects')}>
                前往添加环境
              </Button>
            }
          />
        )}
        <Tabs defaultActiveKey="edit">
          <Tabs.TabPane tab="编辑参数" key="edit">
            <Form form={executeForm} layout="vertical">
              <Form.Item
                label="环境"
                name="environment_id"
                rules={[{ required: true, message: '请选择环境' }]}
              >
                <Select placeholder="选择环境">
                  {environments.map((env) => (
                    <Option key={env.id} value={env.id}>
                      {env.name} ({env.base_url})
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item label="变量 (JSON)" name="variables">
                <JsonEditor
                  value={selectedScript?.script_content?.variables ? JSON.stringify(selectedScript.script_content.variables, null, 2) : ''}
                  height="100px"
                  label=""
                />
              </Form.Item>

              <Form.Item label="请求头">
                <div style={{ maxHeight: 200, overflow: 'auto' }}>
                  {editedHeaders.map((header, index) => (
                    <div key={index} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                      <Input
                        placeholder="Header Key"
                        value={header.key}
                        onChange={(e) => {
                          const newHeaders = [...editedHeaders];
                          newHeaders[index].key = e.target.value;
                          setEditedHeaders(newHeaders);
                        }}
                        style={{ flex: 1 }}
                      />
                      <Input
                        placeholder="Header Value"
                        value={header.value}
                        onChange={(e) => {
                          const newHeaders = [...editedHeaders];
                          newHeaders[index].value = e.target.value;
                          setEditedHeaders(newHeaders);
                        }}
                        style={{ flex: 1 }}
                      />
                      <Button
                        type="text"
                        danger
                        onClick={() => {
                          const newHeaders = editedHeaders.filter((_, i) => i !== index);
                          setEditedHeaders(newHeaders);
                        }}
                      >
                        删除
                      </Button>
                    </div>
                  ))}
                  <Button type="dashed" block onClick={() => setEditedHeaders([...editedHeaders, { key: '', value: '' }])}>
                    添加请求头
                  </Button>
                </div>
              </Form.Item>

              <Form.Item label="请求体">
                <JsonEditor
                  value={body}
                  onChange={setBody}
                  height="200px"
                  label=""
                />
              </Form.Item>
            </Form>
          </Tabs.TabPane>
        </Tabs>
      </Modal>

      {/* 脚本详情抽屉 */}
      <Drawer
        title={`脚本详情 - ${selectedScript?.name || ''}`}
        placement="right"
        width={720}
        onClose={() => setDetailVisible(false)}
        open={detailVisible}
      >
        {selectedScript && (
          <Descriptions title="基本信息" bordered column={1}>
            <Descriptions.Item label="脚本名称">{selectedScript.name}</Descriptions.Item>
            <Descriptions.Item label="测试类型">
              <Tag color="blue">{selectedScript.test_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="描述">{selectedScript.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="请求方法">
              <Tag color="green">{selectedEndpoint?.method}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="请求路径">{selectedEndpoint?.path}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>

      {/* 执行记录抽屉 */}
      <Drawer
        title="执行记录"
        placement="right"
        width={800}
        onClose={() => setExecutionsVisible(false)}
        open={executionsVisible}
      >
        <Table
          columns={[
            { title: '执行时间', dataIndex: 'created_at', key: 'created_at', render: (time: string) => new Date(time).toLocaleString() },
            { title: '状态', dataIndex: 'status', key: 'status', render: (status: string) => <Tag color={status === 'passed' ? 'success' : 'error'}>{status}</Tag> },
            { title: '响应时间', dataIndex: 'response_time_ms', key: 'response_time_ms', render: (time: number) => `${time}ms` },
            {
              title: '操作',
              key: 'action',
              render: (_: any, record: any) => (
                <Button type="link" size="small" onClick={() => handleViewExecutionDetail(record)}>
                  查看详情
                </Button>
              ),
            },
          ]}
          dataSource={executions}
          rowKey="id"
          loading={executionsLoading}
          pagination={{ pageSize: 10 }}
        />
      </Drawer>

      {/* 执行详情抽屉 */}
      <Drawer
        title="执行详情"
        placement="right"
        width={800}
        onClose={() => setExecutionDetailVisible(false)}
        open={executionDetailVisible}
      >
        {selectedExecution && (
          <Descriptions bordered column={1}>
            <Descriptions.Item label="请求URL">{selectedExecution.request_url}</Descriptions.Item>
            <Descriptions.Item label="请求方法">
              <Tag color="blue">{selectedExecution.request_method}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态码">
              <Tag color={selectedExecution.status_code >= 200 && selectedExecution.status_code < 300 ? 'success' : 'error'}>
                {selectedExecution.status_code}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="响应时间">{selectedExecution.response_time_ms}ms</Descriptions.Item>
            <Descriptions.Item label="请求体">
              <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                {JSON.stringify(selectedExecution.request_body, null, 2) || '-'}
              </pre>
            </Descriptions.Item>
            <Descriptions.Item label="响应体">
              <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                {JSON.stringify(selectedExecution.response_body, null, 2) || '-'}
              </pre>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>

      {/* 生成测试脚本弹窗 */}
      <Modal
        title="生成测试脚本"
        open={generateVisible}
        onCancel={() => setGenerateVisible(false)}
        footer={null}
        width={800}
      >
        <Collapse
          defaultActiveKey={['endpoints', 'preset']}
          items={[
            {
              key: 'endpoints',
              label: `选择接口 (已选择 ${selectedEndpointIds.length} 个)`,
              children: (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <Button onClick={() => setSelectedEndpointIds(allEndpoints.map((e: any) => e.id))}>
                      全选
                    </Button>
                    <Button onClick={() => setSelectedEndpointIds([])}>
                      清空
                    </Button>
                  </div>
                  <Table
                    dataSource={allEndpoints}
                    rowKey="id"
                    size="small"
                    loading={loading}
                    pagination={{ pageSize: 10 }}
                    rowSelection={{
                      selectedRowKeys: selectedEndpointIds,
                      onChange: (selectedRowKeys) => setSelectedEndpointIds(selectedRowKeys as number[]),
                    }}
                    columns={[
                      { title: '方法', dataIndex: 'method', width: 80 },
                      { title: '路径', dataIndex: 'path', width: 200 },
                      { title: '摘要', dataIndex: 'summary' },
                    ]}
                  />
                </>
              )
            },
            {
              key: 'preset',
              label: '预设测试类型',
              children: (
                <Checkbox.Group
                  value={selectedTestTypes}
                  onChange={(values) => setSelectedTestTypes(values as string[])}
                >
                  <Space direction="vertical">
                    {testTypes.preset_types?.map((type: any) => (
                      <Checkbox key={type.code} value={type.code}>
                        {type.name} - {type.description}
                      </Checkbox>
                    ))}
                  </Space>
                </Checkbox.Group>
              )
            },
            {
              key: 'custom',
              label: '自定义测试类型',
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Button
                    icon={<PlusSquareOutlined />}
                    onClick={() => setAddCustomTypeVisible(true)}
                  >
                    添加自定义类型
                  </Button>

                  {customTypes.length > 0 && (
                    <div>
                      <Checkbox.Group
                        value={selectedTestTypes}
                        onChange={(values) => setSelectedTestTypes(values as string[])}
                      >
                        <Space direction="vertical">
                          {customTypes.map((type: any) => (
                            <div key={type.code} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <Checkbox value={type.code}>
                                {type.name}
                              </Checkbox>
                              <span style={{ color: '#999', fontSize: 12 }}>
                                {type.description}
                              </span>
                            </div>
                          ))}
                        </Space>
                      </Checkbox.Group>
                    </div>
                  )}

                  {testTypes.custom_types?.map((type: any) => (
                    <div key={type.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Checkbox
                        checked={selectedTestTypes.includes(type.code)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedTestTypes([...selectedTestTypes, type.code]);
                          } else {
                            setSelectedTestTypes(selectedTestTypes.filter(t => t !== type.code));
                          }
                        }}
                      >
                        {type.name}
                      </Checkbox>
                      <span style={{ color: '#999', fontSize: 12 }}>
                        {type.description}
                      </span>
                    </div>
                  ))}
                </Space>
              )
            }
          ]}
        />

        <Divider />

        <div style={{ textAlign: 'right' }}>
          <span style={{ marginRight: 16, color: '#999' }}>
            预计生成：{selectedEndpointIds.length} 个接口 × {selectedTestTypes.length} 种类型 = {selectedEndpointIds.length * selectedTestTypes.length} 个脚本
          </span>
          <Button onClick={() => setGenerateVisible(false)}>
            取消
          </Button>
          <Button
            type="primary"
            onClick={handleGenerate}
            loading={loading}
            disabled={selectedEndpointIds.length === 0 || selectedTestTypes.length === 0}
          >
            开始生成
          </Button>
        </div>
      </Modal>

      {/* 添加自定义类型弹窗 */}
      <Modal
        title="添加自定义测试类型"
        open={addCustomTypeVisible}
        onCancel={() => setAddCustomTypeVisible(false)}
        onOk={handleAddCustomType}
        width={600}
      >
        <Form form={customTypeForm} layout="vertical">
          <Form.Item
            label="类型名称"
            name="name"
            rules={[{ required: true, message: '请输入类型名称' }]}
          >
            <Input placeholder="类型名称" />
          </Form.Item>
          <Form.Item
            label="类型代码"
            name="code"
            rules={[{ required: true, message: '请输入类型代码' }]}
          >
            <Input placeholder="类型代码" />
          </Form.Item>
          <Form.Item
            label="类型描述"
            name="description"
            rules={[{ required: true, message: '请输入类型描述' }]}
          >
            <Input.TextArea rows={3} placeholder="类型描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Scripts;