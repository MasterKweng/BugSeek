import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Space, Tag, message, Modal, Drawer, Form, Input, Select, Spin, Collapse, Divider, Empty, Table, Checkbox, Descriptions, Alert, Skeleton, Tabs, Progress, Row, Col, Statistic, InputNumber, Switch } from 'antd';
import { PlayCircleOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, PlusOutlined, PlusSquareOutlined, EnvironmentOutlined, HistoryOutlined } from '@ant-design/icons';
import { useProjectStore } from '../../store/project';
import { get, post, put, del } from '../../services/request';
import { ExecutionStatus, TestType } from '../../constants/script';
import VirtualScriptList from '../../components/VirtualScriptList';
import { useDebounce } from '../../hooks/useDebounce';
import JsonEditor from '../../components/JsonEditor';

const { Option } = Select;
const { TextArea } = Input;
const { Panel } = Collapse;

const Scripts: React.FC = () => {
  const navigate = useNavigate();
  const { currentProject, currentVersion } = useProjectStore();
  const [groups, setGroups] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [generateVisible, setGenerateVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [editVisible, setEditVisible] = useState(false);
  const [executeVisible, setExecuteVisible] = useState(false);
  const [executionsVisible, setExecutionsVisible] = useState(false);
  const [executionDetailVisible, setExecutionDetailVisible] = useState(false);
  const [selectedScript, setSelectedScript] = useState<any>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<any>(null);
  const [selectedExecution, setSelectedExecution] = useState<any>(null);
  const [editForm] = Form.useForm();
  const [executeForm] = Form.useForm();
  const [editLoading, setEditLoading] = useState(false);
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const [environments, setEnvironments] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filterTestType, setFilterTestType] = useState<string | undefined>(undefined);
  const [selectedEndpointIds, setSelectedEndpointIds] = useState<number[]>([]);
  const [selectedTestTypes, setSelectedTestTypes] = useState<string[]>([TestType.POSITIVE, TestType.NEGATIVE]);
  const [customTypes, setCustomTypes] = useState<any[]>([]);
  const [addCustomTypeVisible, setAddCustomTypeVisible] = useState(false);
  const [customTypeForm] = Form.useForm();
  const [testTypes, setTestTypes] = useState<any>({ preset_types: [], custom_types: [] });
  const [executions, setExecutions] = useState<any[]>([]);
  const [executionsLoading, setExecutionsLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [editedHeaders, setEditedHeaders] = useState<Array<{ key: string; value: string }>>([]);
  const [scriptContent, setScriptContent] = useState<string>('');
  const [variables, setVariables] = useState<string>('');
  const [body, setBody] = useState<string>('');
  const debouncedFilterTestType = useDebounce(filterTestType, 300); // 防抖 300ms

  // 辅助函数：格式化文件大小
  const formatSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  // 辅助函数：计算百分比
  const calculatePercent = (value: number | undefined, total: number | undefined): number => {
    if (!value || !total || total === 0) return 0;
    return Math.round((value / total) * 100);
  };

  // 获取所有接口列表（用于批量选择）
  const fetchAllEndpoints = async () => {
    try {
      setLoading(true);
      let allEndpoints = [];
      let skip = 0;
      const limit = 200; // 后端限制最大值为 200
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

      setEndpoints(allEndpoints);
    } catch (error) {
      console.error('获取接口列表失败:', error);
      message.error('获取接口列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 获取环境列表
  const fetchEnvironments = async () => {
    try {
      const result = await get('/environments');
      setEnvironments(result.environments || []);
    } catch (error) {
      // 静默失败，不显示错误提示
      console.error('获取环境列表失败:', error);
      // 设置为空数组，避免页面崩溃
      setEnvironments([]);
    }
  };

  // 获取测试类型列表
  const fetchTestTypes = async () => {
    try {
      const result = await get('/api-integration/test-types');
      setTestTypes(result);
    } catch (error) {
      console.error('获取测试类型失败:', error);
      message.error('获取测试类型失败');
    }
  };

  // 获取脚本列表（树形结构）
    const fetchScripts = useCallback(async () => {
      setLoading(true);
      try {
        const params: Record<string, any> = {};
  
        if (debouncedFilterTestType) {
          params.test_type = debouncedFilterTestType;
        }
  
        const result = await get('/api-integration/scripts', params);
        setGroups(result?.groups || []);
        setTotal(result?.total_scripts || 0);
      } catch (error) {
        console.error('获取脚本列表失败:', error);
        message.error('获取脚本列表失败，请稍后重试');
      } finally {
        setLoading(false);
      }
    }, [debouncedFilterTestType]);


  // 组件加载时获取数据
  useEffect(() => {
    fetchScripts();
    fetchTestTypes();
    fetchEnvironments();
  }, [debouncedFilterTestType]);

  // 执行单个脚本

    const handleExecuteScript = async (script: any) => {

      // 检查环境列表

      if (environments.length === 0) {

        message.warning('请先添加环境后再执行脚本');

        return;

      }

  

      setSelectedScript(script);

      setSelectedEndpoint(null);

      

      // 初始化编辑器，加载脚本定义的内容

      setVariables('');

      

      // 加载脚本定义的 headers

      const scriptHeaders = script.script_content?.headers || {};

      const headersArray = Object.entries(scriptHeaders).map(([key, value]) => ({

        key,

        value: String(value)

      }));

      setEditedHeaders(headersArray);

      

      // 加载脚本定义的 body

      const scriptBody = script.script_content?.request || {};

      const bodyJson = Object.keys(scriptBody).length > 0 

        ? JSON.stringify(scriptBody, null, 2)

        : '';

      setBody(bodyJson);

      

      setExecuteVisible(true);

    };

  

    // 执行接口的所有脚本

    const handleExecuteAll = async (endpoint: any) => {

      // 检查环境列表

      if (environments.length === 0) {

        message.warning('请先添加环境后再执行脚本');

        return;

      }

  

      setSelectedEndpoint(endpoint);

      

      // 初始化编辑器（接口执行时不加载特定脚本的内容，保持为空）

      setVariables('');

      setEditedHeaders([]);

      setBody('');

      

      setExecuteVisible(true);

    };  // 提交执行
  const handleExecuteSubmit = async () => {
    try {
      const values = await executeForm.validateFields();

      // 处理自定义 headers
      const customHeaders: Record<string, string> = {};
      editedHeaders.forEach(header => {
        if (header.key && header.value) {
          customHeaders[header.key] = header.value;
        }
      });

      // 处理自定义 body
      let customBody = undefined;
      if (body && body.trim()) {
        try {
          customBody = JSON.parse(body);
        } catch (e) {
          message.error('请求 Body JSON 格式错误');
          return;
        }
      }

      setExecuting(true);
      setExecuteVisible(false);

      if (selectedScript) {
        // 执行单个脚本
        const result = await post(`/api-integration/scripts/${selectedScript.id}/execute`, {
          environment_id: values.environment_id,
          variables: values.variables,
          headers: Object.keys(customHeaders).length > 0 ? customHeaders : undefined,
          body: customBody
        }, 60000);
        
        // 后端返回的数据格式：{ code: 0, message: "success", data: {...} }
        const executionData = result.data || result;
        
        message.success('执行成功');
        
        // 重新获取完整的执行详情（确保所有字段都有）
        try {
          const fullDetail = await get(`/api-integration/executions/${executionData.id}`);
          setSelectedExecution(fullDetail);
        } catch (e) {
          // 如果获取详情失败，使用执行返回的数据
          setSelectedExecution(executionData);
        }
        
        setExecutionDetailVisible(true);
        
      } else if (selectedEndpoint) {
        // 执行接口的所有脚本
        const result = await post(`/api-integration/endpoints/${selectedEndpoint.endpoint_id}/execute-all`, {
          environment_id: values.environment_id,
          variables: values.variables,
          headers: Object.keys(customHeaders).length > 0 ? customHeaders : undefined,
          body: customBody
        }, 120000);
        message.success(`执行完成: 成功 ${result.data.success_count} 个, 失败 ${result.data.failed_count} 个`);
        handleViewExecutions(selectedEndpoint);
      }
    } catch (error) {
      console.error('执行失败:', error);
      message.error('执行失败，请稍后重试');
    } finally {
      setExecuting(false);
    }
  };

  // 查看执行记录
  const handleViewExecutions = async (item: any) => {
    setExecutionsVisible(true);
    setExecutionsLoading(true);

    try {
      let result;
      let title = '';

      // 判断是脚本还是接口（优先判断脚本，因为脚本有明确的 id 字段）
      if (item.id) {
        // 脚本
        setSelectedScript(item);
        setSelectedEndpoint(null);
        result = await get(`/api-integration/scripts/${item.id}/executions`, { limit: 50 });
        title = `${item.name} - 执行记录`;
      } else if (item.endpoint_id) {
        // 接口
        setSelectedEndpoint(item);
        setSelectedScript(null);
        result = await get(`/api-integration/endpoints/${item.endpoint_id}/executions`, { limit: 50 });
        title = `${item.method} ${item.path} - 执行记录`;
      }

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
      const result = await get(`/api-integration/executions/${execution.id}`);
      setSelectedExecution(result);
      setExecutionDetailVisible(true);
    } catch (error) {
      console.error('获取执行详情失败:', error);
      message.error('获取执行详情失败');
    }
  };

  // 生成测试脚本（支持自定义类型）
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
      }, 120000); // 2分钟超时
      
      message.success(`成功生成 ${result?.scripts_count || 0} 个测试脚本`);
      setSelectedEndpointIds([]);
      setSelectedTestTypes([TestType.POSITIVE, TestType.NEGATIVE]);
      setCustomTypes([]);
      
      // 等待一下，确保数据库写入完成
      await new Promise(resolve => setTimeout(resolve, 500));
      
      fetchScripts(); // 重新加载列表
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
      fetchTestTypes(); // 重新加载测试类型列表
    } catch (error) {
      console.error('添加失败:', error);
      message.error('添加失败，请稍后重试');
    }
  };

  // 查看详情
  const handleViewDetail = (script: any) => {
    setSelectedScript(script);
    setDetailVisible(true);
  };

  // 编辑脚本
  const handleEdit = (script: any) => {
    setSelectedScript(script);
    const scriptContentJson = JSON.stringify(script.script_content || {}, null, 2);
    editForm.setFieldsValue({
      name: script.name,
      description: script.description,
      script_content: scriptContentJson
    });
    setScriptContent(scriptContentJson);
    setEditVisible(true);
  };

  // 提交编辑
  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      setEditLoading(true);
      
      const result = await put(`/api-integration/scripts/${selectedScript.id}`, {
        name: values.name,
        description: values.description,
        script_content: JSON.parse(values.script_content)
      });
      
      if (result.code === 0) {
        message.success('更新成功');
        setEditVisible(false);
        fetchScripts(); // 重新加载列表
      } else {
        message.error(result.message || '更新失败');
      }
    } catch (error: any) {
      console.error('更新失败:', error);
      message.error('更新失败，请稍后重试');
    } finally {
      setEditLoading(false);
    }
  };

  // 删除脚本
  const handleDelete = async (scriptId: number, scriptName: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除脚本 "${scriptName}" 吗？此操作不可恢复。`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          const result = await del(`/api-integration/scripts/${scriptId}`);
          
          if (result.code === 0) {
            message.success('删除成功');
            fetchScripts(); // 重新加载列表
          } else {
            message.error(result.message || '删除失败');
          }
        } catch (error: any) {
          console.error('删除失败:', error);
          message.error('删除失败，请稍后重试');
        }
      },
    });
  };

  // 树节点选择处理
  const handleTreeSelect = (selectedKeys: any[], info: any) => {
    const { node } = info;
    if (node.isLeaf && node.script) {
      // 选中了脚本节点
      setSelectedScript(node.script);
      setDetailVisible(true);
    }
  };

  // 如果没有选择项目或版本，显示骨架屏
  if (!currentProject || !currentVersion) {
    return (
      <div style={{ padding: '24px' }}>
        <Card>
          <Skeleton active paragraph={{ rows: 6 }} />
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
            <Button icon={<PlusOutlined />} onClick={() => {
              if (endpoints.length === 0) {
                fetchAllEndpoints();
              }
              setGenerateVisible(true);
            }}>
              生成测试脚本
            </Button>
            <Select
              placeholder="筛选测试类型"
              style={{ width: 120 }}
              allowClear
              value={filterTestType}
              onChange={(value) => {
                setFilterTestType(value);
              }}
            >
              <Option value={TestType.POSITIVE}>正向测试</Option>
              <Option value={TestType.NEGATIVE}>逆向测试</Option>
              <Option value={TestType.BOUNDARY}>边界测试</Option>
              <Option value={TestType.EXCEPTION}>异常测试</Option>
            </Select>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={() => fetchScripts()}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        }
      >
        {groups.length === 0 ? (
          <Empty description="暂无测试脚本" />
        ) : (
          <VirtualScriptList
            groups={groups}
            onExecuteScript={handleExecuteScript}
            onExecuteAll={handleExecuteAll}
            onViewExecutions={handleViewExecutions}
            onViewDetail={handleViewDetail}
            environments={environments}
          />
        )}
      </Card>

      {/* 执行脚本弹窗 */}
      <Modal
        title={selectedScript ? `执行脚本: ${selectedScript.name}` : `执行接口: ${selectedEndpoint?.method} ${selectedEndpoint?.path}`}
        open={executeVisible}
        onCancel={() => {
          setExecuteVisible(false);
          setEditedHeaders([]);
          setEditedBody('');
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
        <Tabs defaultActiveKey="preview">
          {/* Tab 1: 预览 - 显示脚本定义的请求信息（只读） */}
          <Tabs.TabPane tab="预览" key="preview">
            {selectedScript && (
              <>
                <Descriptions bordered column={1} style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="接口路径">
                    <Tag color="blue">{selectedScript.script_content?.method || 'GET'}</Tag>
                    <span>{selectedScript.script_content?.endpoint || selectedScript.endpoint_id}</span>
                  </Descriptions.Item>
                </Descriptions>

                <Collapse defaultActiveKey={['headers', 'body']}>
                  <Collapse.Panel header={`请求 Headers (${Object.keys(selectedScript.script_content?.headers || {}).length})`} key="headers">
                    {Object.keys(selectedScript.script_content?.headers || {}).length > 0 ? (
                      <Table
                        columns={[
                          { title: 'Key', dataIndex: 'key' },
                          { title: 'Value', dataIndex: 'value' }
                        ]}
                        dataSource={Object.entries(selectedScript.script_content?.headers || {}).map(([k, v]) => ({ key: k, value: String(v) }))}
                        pagination={false}
                        size="small"
                      />
                    ) : (
                      <Empty description="无 Headers" />
                    )}
                  </Collapse.Panel>
                  <Collapse.Panel header="请求 Body" key="body">
                    {selectedScript.script_content?.request ? (
                      <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                        {JSON.stringify(selectedScript.script_content.request, null, 2)}
                      </pre>
                    ) : (
                      <Empty description="无 Body" />
                    )}
                  </Collapse.Panel>
                </Collapse>
              </>
            )}
          </Tabs.TabPane>

          {/* Tab 2: 编辑 - 允许用户修改请求参数 */}
          <Tabs.TabPane tab="编辑" key="edit">
            <Form form={executeForm} layout="vertical">
              <Form.Item
                label="执行环境"
                name="environment_id"
                rules={[{ required: true, message: '请选择执行环境' }]}
              >
                <Select
                  placeholder={environments.length === 0 ? '暂无环境，请先添加环境' : '请选择环境'}
                  disabled={environments.length === 0}
                >
                  {(environments || []).map((env: any) => (
                    <Option key={env.id} value={env.id}>
                      <Space>
                        <EnvironmentOutlined />
                        {env.name}
                        <span style={{ color: '#999' }}>{env.base_url}</span>
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              {/* Headers 编辑器 */}
              <Form.Item label="请求 Headers（可选覆盖）">
                <Table
                  columns={[
                    {
                      title: 'Key',
                      dataIndex: 'key',
                      width: 200,
                      render: (text, record, index) => (
                        <Input
                          value={record.key}
                          placeholder="Header Key"
                          onChange={(e) => {
                            const newHeaders = [...editedHeaders];
                            newHeaders[index].key = e.target.value;
                            setEditedHeaders(newHeaders);
                          }}
                        />
                      )
                    },
                    {
                      title: 'Value',
                      dataIndex: 'value',
                      render: (text, record, index) => (
                        <Input
                          value={record.value}
                          placeholder="Header Value"
                          onChange={(e) => {
                            const newHeaders = [...editedHeaders];
                            newHeaders[index].value = e.target.value;
                            setEditedHeaders(newHeaders);
                          }}
                        />
                      )
                    },
                    {
                      title: '操作',
                      width: 80,
                      render: (_, record, index) => (
                        <Button type="link" danger size="small" onClick={() => {
                          const newHeaders = editedHeaders.filter((_, i) => i !== index);
                          setEditedHeaders(newHeaders);
                        }}>
                          删除
                        </Button>
                      )
                    }
                  ]}
                  dataSource={editedHeaders}
                  pagination={false}
                  size="small"
                  rowKey={(record, index) => index}
                />
                <Button
                  type="dashed"
                  block
                  onClick={() => setEditedHeaders([...editedHeaders, { key: '', value: '' }])}
                  style={{ marginTop: 8 }}
                >
                  + 添加 Header
                </Button>
              </Form.Item>

              {/* Body 编辑器 */}
                          <Form.Item label="请求 Body（可选覆盖）">
                            <JsonEditor
                              value={body}
                              onChange={setBody}
                              height="300px"
                              placeholder='{"key": "value"}'
                              label="请求 Body"
                            />
                          </Form.Item>              {/* 变量覆盖 */}
                          <Form.Item label="变量覆盖（可选）" name="variables">
                            <JsonEditor
                              value={variables}
                              onChange={(value) => {
                                setVariables(value);
                                executeForm.setFieldValue('variables', value);
                              }}
                              height="150px"
                              placeholder='{"key1": "value1", "key2": "value2"}'
                              label="变量覆盖"
                            />
                          </Form.Item>            </Form>
          </Tabs.TabPane>

          {/* Tab 3: 设置 - 高级选项 */}
          <Tabs.TabPane tab="设置" key="settings">
            <Form form={executeForm} layout="vertical">
              <Form.Item
                label="执行环境"
                name="environment_id"
                rules={[{ required: true, message: '请选择执行环境' }]}
              >
                <Select
                  placeholder={environments.length === 0 ? '暂无环境，请先添加环境' : '请选择环境'}
                  disabled={environments.length === 0}
                >
                  {(environments || []).map((env: any) => (
                    <Option key={env.id} value={env.id}>
                      <Space>
                        <EnvironmentOutlined />
                        {env.name}
                        <span style={{ color: '#999' }}>{env.base_url}</span>
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>

{/* 变量覆盖 */}
            <Form.Item label="变量覆盖（可选）" name="variables">
              <JsonEditor
                value={variables}
                onChange={(value) => {
                  setVariables(value);
                  executeForm.setFieldValue('variables', value);
                }}
                height="150px"
                placeholder='{"key1": "value1", "key2": "value2"}'
                label="变量覆盖"
              />
            </Form.Item>
            </Form>
          </Tabs.TabPane>
        </Tabs>
      </Modal>

      {/* 执行记录弹窗 */}
      <Modal
        title={
          <Space>
            <HistoryOutlined />
            {selectedScript 
              ? `执行记录 - ${selectedScript.name}`
              : `执行记录 - ${selectedEndpoint?.method} ${selectedEndpoint?.path}`
            }
          </Space>
        }
        open={executionsVisible}
        onCancel={() => setExecutionsVisible(false)}
        footer={null}
        width={1000}
      >
        <Table
          dataSource={executions}
          rowKey="id"
          loading={executionsLoading}
          pagination={{ pageSize: 10 }}
          onRow={(record) => ({
            onClick: () => handleViewExecutionDetail(record),
            style: { cursor: 'pointer' }
          })}
          columns={[
            { title: '执行时间', dataIndex: 'created_at', width: 180 },
            // 仅在查看接口执行记录时显示脚本名称
            ...(selectedEndpoint ? [{
              title: '脚本名称',
              dataIndex: 'script_name',
              width: 200,
              render: (scriptName: string) => scriptName || '未知脚本'
            }] : []),
            {
                          title: '状态',
                          dataIndex: 'status',
                          width: 100,
                          render: (status: string) => (
                            <Tag color={status === ExecutionStatus.SUCCESS ? 'green' : 'red'}>
                              {status === ExecutionStatus.SUCCESS ? '成功' : '失败'}
                            </Tag>
                          )
                        },
            { title: '响应时间', dataIndex: 'response_time_ms', width: 100, render: (v: number) => `${v}ms` },
            { title: '状态码', dataIndex: 'response_status_code', width: 100 },
            {
              title: '请求大小',
              dataIndex: 'request_size',
              width: 100,
              render: (size: number) => formatSize(size || 0)
            },
            {
              title: '响应大小',
              dataIndex: 'response_size',
              width: 100,
              render: (size: number) => formatSize(size || 0)
            },
            { title: '错误信息', dataIndex: 'error_message', ellipsis: true }
          ]}
        />
      </Modal>

      {/* 执行详情抽屉 */}
      <Drawer
        title={
          <Space>
            <HistoryOutlined />
            执行详情
          </Space>
        }
        placement="right"
        width={1000}
        onClose={() => setExecutionDetailVisible(false)}
        open={executionDetailVisible}
      >
        {selectedExecution && (
          <>
            {/* 顶部概览 */}
            <Card size="small" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic
                    title="状态"
                    value={selectedExecution.status === ExecutionStatus.SUCCESS ? '成功' : '失败'}
                    valueStyle={{ color: selectedExecution.status === ExecutionStatus.SUCCESS ? '#3f8600' : '#cf1322' }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic title="状态码" value={selectedExecution.response_status_code || '-'} />
                </Col>
                <Col span={6}>
                  <Statistic title="响应时间" value={selectedExecution.response_time_ms || 0} suffix="ms" />
                </Col>
                <Col span={6}>
                  <Statistic title="总耗时" value={selectedExecution.duration_ms || 0} suffix="ms" />
                </Col>
              </Row>
            </Card>

            {/* Tab 切换 */}
            <Tabs defaultActiveKey="request">
              {/* 请求 Tab */}
              <Tabs.TabPane tab="请求" key="request">
                <Collapse defaultActiveKey={['url', 'headers', 'body']}>
                  <Collapse.Panel header="请求 URL" key="url">
                    <Input value={selectedExecution.request_url} readOnly />
                  </Collapse.Panel>
                  <Collapse.Panel header={`请求方法: ${selectedExecution.request_method}`} key="method">
                    <Tag color="blue">{selectedExecution.request_method}</Tag>
                  </Collapse.Panel>
                  <Collapse.Panel header={`请求 Headers (${Object.keys(selectedExecution.request_headers || {}).length})`} key="headers">
                    <Table
                      columns={[
                        { title: 'Key', dataIndex: 'key', width: 200 },
                        { title: 'Value', dataIndex: 'value', ellipsis: true }
                      ]}
                      dataSource={Object.entries(selectedExecution.request_headers || {}).map(([key, value]) => ({ key, value }))}
                      pagination={false}
                      size="small"
                    />
                  </Collapse.Panel>
                  <Collapse.Panel header={`请求 Body (${formatSize(selectedExecution.request_size || 0)})`} key="body">
                    <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, maxHeight: 400, overflow: 'auto' }}>
                      {JSON.stringify(selectedExecution.request_body || {}, null, 2)}
                    </pre>
                  </Collapse.Panel>
                </Collapse>
              </Tabs.TabPane>

              {/* 响应 Tab */}
              <Tabs.TabPane tab="响应" key="response">
                <Collapse defaultActiveKey={['status', 'headers', 'body']}>
                  <Collapse.Panel header={`状态: ${selectedExecution.response_status_code}`} key="status">
                    <Space>
                      <Tag color={selectedExecution.response_status_code < 400 ? 'green' : 'red'}>
                        {selectedExecution.response_status_code}
                      </Tag>
                      <span>响应时间: {selectedExecution.response_time_ms}ms</span>
                      <span>响应大小: {formatSize(selectedExecution.response_size || 0)}</span>
                    </Space>
                  </Collapse.Panel>
                  <Collapse.Panel header={`响应 Headers (${Object.keys(selectedExecution.response_headers || {}).length})`} key="headers">
                    <Table
                      columns={[
                        { title: 'Key', dataIndex: 'key', width: 200 },
                        { title: 'Value', dataIndex: 'value', ellipsis: true }
                      ]}
                      dataSource={Object.entries(selectedExecution.response_headers || {}).map(([key, value]) => ({ key, value }))}
                      pagination={false}
                      size="small"
                    />
                  </Collapse.Panel>
                  <Collapse.Panel header={`响应 Body (${formatSize(selectedExecution.response_size || 0)})`} key="body">
                    <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, maxHeight: 400, overflow: 'auto' }}>
                      {JSON.stringify(selectedExecution.response_body || {}, null, 2)}
                    </pre>
                  </Collapse.Panel>
                </Collapse>
              </Tabs.TabPane>

              {/* 测试结果 Tab */}
              <Tabs.TabPane
                tab={`测试结果 (${selectedExecution.assertion_results?.filter((a: any) => a.passed).length}/${selectedExecution.assertion_results?.length})`}
                key="test"
              >
                {selectedExecution.assertion_results && selectedExecution.assertion_results.length > 0 ? (
                  <Table
                    columns={[
                      {
                        title: '状态',
                        dataIndex: 'passed',
                        width: 80,
                        render: (passed: boolean) => (
                          <Tag color={passed ? 'green' : 'red'}>
                            {passed ? '✓' : '✗'}
                          </Tag>
                        )
                      },
                      { title: '消息', dataIndex: 'message' },
                      {
                        title: '类型',
                        dataIndex: 'type',
                        width: 120,
                        render: (type: string) => <Tag>{type}</Tag>
                      }
                    ]}
                    dataSource={selectedExecution.assertion_results}
                    pagination={false}
                    size="small"
                  />
                ) : (
                  <Empty description="无测试结果" />
                )}
              </Tabs.TabPane>

              {/* 性能分析 Tab */}
              <Tabs.TabPane tab="性能分析" key="performance">
                <Row gutter={16}>
                  <Col span={12}>
                    <Card title="时间分布" size="small">
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span>DNS 解析</span>
                          <span>{selectedExecution.dns_time_ms || 0}ms</span>
                        </div>
                        <Progress percent={calculatePercent(selectedExecution.dns_time_ms, selectedExecution.duration_ms)} status="active" />
                      </div>
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span>TCP 连接</span>
                          <span>{selectedExecution.tcp_time_ms || 0}ms</span>
                        </div>
                        <Progress percent={calculatePercent(selectedExecution.tcp_time_ms, selectedExecution.duration_ms)} status="active" />
                      </div>
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span>TLS 握手</span>
                          <span>{selectedExecution.tls_time_ms || 0}ms</span>
                        </div>
                        <Progress percent={calculatePercent(selectedExecution.tls_time_ms, selectedExecution.duration_ms)} status="active" />
                      </div>
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span>数据传输</span>
                          <span>{selectedExecution.transfer_time_ms || 0}ms</span>
                        </div>
                        <Progress percent={calculatePercent(selectedExecution.transfer_time_ms, selectedExecution.duration_ms)} status="active" />
                      </div>
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card title="统计信息" size="small">
                      <Statistic title="请求大小" value={formatSize(selectedExecution.request_size || 0)} />
                      <Divider />
                      <Statistic title="响应大小" value={formatSize(selectedExecution.response_size || 0)} />
                    </Card>
                  </Col>
                </Row>
              </Tabs.TabPane>
            </Tabs>

            {/* 错误信息 */}
            {selectedExecution?.error_message && (
              <>
                <Divider orientation="left">错误信息</Divider>
                <pre style={{ background: '#fff2f0', padding: 12, borderRadius: 4, color: '#ff4d4f' }}>
                  {selectedExecution.error_message}
                </pre>
              </>
            )}
          </>
        )}
      </Drawer>

      {/* 生成脚本弹窗 - 支持自定义类型 */}
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
                                    <Button onClick={() => setSelectedEndpointIds((endpoints || []).map((e: any) => e.id))}>
                                      全选
                                    </Button>
                                    <Button onClick={() => setSelectedEndpointIds([])}>
                                      清空
                                    </Button>
                                  </div>                  
                  <Table
                    dataSource={endpoints}
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
            <Input placeholder="例如：性能测试" />
          </Form.Item>
          
          <Form.Item
            label="类型代码"
            name="code"
            rules={[{ required: true, message: '请输入类型代码' }]}
          >
            <Input placeholder="例如：performance" />
          </Form.Item>
          
          <Form.Item label="类型描述" name="description">
            <TextArea 
              rows={4} 
              placeholder="详细描述该测试类型的要求，有助于 AI 生成更准确的脚本"
            />
          </Form.Item>
          
          <div style={{ color: '#999', fontSize: 12 }}>
            提示：详细描述有助于 AI 生成更准确的脚本
          </div>
        </Form>
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
          <>
            <div style={{ marginBottom: 16 }}>
              <strong>脚本名称：</strong>{selectedScript.name}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>测试类型：</strong>
              <Tag color={
                selectedScript.test_type === TestType.POSITIVE ? 'green' :
                selectedScript.test_type === TestType.NEGATIVE ? 'red' :
                selectedScript.test_type === TestType.BOUNDARY ? 'orange' : 'purple'
              }>
                {selectedScript.test_type}
              </Tag>
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>描述：</strong>{selectedScript.description || '-'}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>脚本内容：</strong>
              <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, marginTop: 8 }}>
                {JSON.stringify(selectedScript.script_content || {}, null, 2)}
              </pre>
            </div>
          </>
        )}
      </Drawer>

      {/* 编辑脚本弹窗 */}
      <Modal
        title={`编辑脚本 - ${selectedScript?.name || ''}`}
        open={editVisible}
        onCancel={() => {
          setEditVisible(false);
          setScriptContent('');
        }}
        onOk={handleEditSubmit}
        confirmLoading={editLoading}
        width={800}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            label="脚本名称"
            name="name"
            rules={[{ required: true, message: '请输入脚本名称' }]}
          >
            <Input placeholder="脚本名称" />
          </Form.Item>

          <Form.Item label="描述" name="description">
            <TextArea rows={3} placeholder="脚本描述" />
          </Form.Item>

          <Form.Item
            label="脚本内容 (JSON)"
            name="script_content"
            rules={[{ required: true, message: '请输入脚本内容' }]}
          >
            <JsonEditor
              value={scriptContent}
              onChange={(value) => {
                setScriptContent(value);
                editForm.setFieldValue('script_content', value);
              }}
              height="400px"
              placeholder='{"endpoint": "...", "request": {...}, "assertions": [...]}'
              label="脚本内容"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default React.memo(Scripts);