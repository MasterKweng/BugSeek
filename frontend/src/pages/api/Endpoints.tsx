import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Table, Button, Space, Tag, Input, Select, message, Spin, Modal, Drawer, Descriptions, Form, Skeleton, Row, Col, Collapse, Checkbox, Divider, Alert } from 'antd';
import { ReloadOutlined, PlusOutlined, SearchOutlined, PlusSquareOutlined } from '@ant-design/icons';
import { useProjectStore } from '../../store/project';
import { get, post, put, del } from '../../services/request';
import { useDebounce } from '../../hooks/useDebounce';
import { TestType } from '../../constants/script';
import GroupTree from '../../components/GroupTree';

const { Search } = Input;
const { Option } = Select;
const { TextArea } = Input;

const Endpoints: React.FC = () => {
  const navigate = useNavigate();
  const { currentProject, currentVersion } = useProjectStore();
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const debouncedSearchText = useDebounce(searchText, 300); // 防抖 300ms
  const [filterMethod, setFilterMethod] = useState<string | undefined>(undefined);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [detailVisible, setDetailVisible] = useState(false);
  const [editVisible, setEditVisible] = useState(false);
  const [createVisible, setCreateVisible] = useState(false);
  const [selectedEndpoint, setSelectedEndpoint] = useState<any>(null);
  const [editForm] = Form.useForm();
  const [createForm] = Form.useForm();
  const [editLoading, setEditLoading] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [groups, setGroups] = useState<any[]>([]);
  const [groupModalVisible, setGroupModalVisible] = useState(false);
  const [groupForm] = Form.useForm();
  const [groupLoading, setGroupLoading] = useState(false);
  const [advancedSearchVisible, setAdvancedSearchVisible] = useState(false);
  const [advancedSearchForm] = Form.useForm();
  const [advancedSearchLoading, setAdvancedSearchLoading] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [groupEndpointsCount, setGroupEndpointsCount] = useState<{[key: number]: number}>({});

  // 生成测试脚本相关状态
  const [generateVisible, setGenerateVisible] = useState(false);
  const [selectedEndpointIds, setSelectedEndpointIds] = useState<number[]>([]);
  const [selectedTestTypes, setSelectedTestTypes] = useState<string[]>([TestType.POSITIVE, TestType.NEGATIVE]);
  const [testTypes, setTestTypes] = useState<any>({ preset_types: [], custom_types: [] });
  const [customTypes, setCustomTypes] = useState<any[]>([]);
  const [addCustomTypeVisible, setAddCustomTypeVisible] = useState(false);
  const [customTypeForm] = Form.useForm();
  const [groupEndpointsCache, setGroupEndpointsCache] = useState<{[key: number]: any[]}>({});

  // 获取接口列表
  const fetchEndpoints = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        skip: (page - 1) * pageSize,
        limit: pageSize,
      };

      if (selectedGroupId !== null) {
        params.group_id = selectedGroupId;
      }

      if (filterMethod) {
        params.method = filterMethod;
      }

      if (debouncedSearchText) {
        params.keyword = debouncedSearchText;
      }

      const result = await get('/api-integration/endpoints', params);

      setEndpoints(result.endpoints || []);
      setTotal(result.total || 0);
    } catch (error: any) {
      console.error('获取接口列表失败:', error);
      message.error(error.message || '获取接口列表失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filterMethod, debouncedSearchText, selectedGroupId]);

  // 获取分组列表
  const fetchGroups = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {};
      
      // 传递已选中的接口ID列表
      if (selectedEndpointIds.length > 0) {
        params.selected_endpoint_ids = selectedEndpointIds.join(',');
      }
      
      const result = await get('/api-integration/endpoints/groups', params);
      setGroups(result.groups || []);
    } catch (error) {
      console.error('获取分组列表失败:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedEndpointIds]);

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

      fetchEndpoints();
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

  // 获取某个分组下的所有接口（分页循环获取）
  const fetchGroupEndpoints = async (groupId: number) => {
    // 如果缓存中有数据，直接返回
    if (groupEndpointsCache[groupId]) {
      return groupEndpointsCache[groupId];
    }

    let allEndpoints = [];
    let skip = 0;
    const limit = 200;
    let hasMore = true;

    while (hasMore) {
      const result = await get('/api-integration/endpoints', { 
        group_id: groupId, 
        skip,
        limit 
      });
      const endpoints = result.endpoints || [];
      allEndpoints = [...allEndpoints, ...endpoints];
      
      if (endpoints.length < limit) {
        hasMore = false;
      } else {
        skip += limit;
      }
    }

    // 缓存数据
    setGroupEndpointsCache(prev => ({
      ...prev,
      [groupId]: allEndpoints
    }));

    return allEndpoints;
  };

  // 切换分组的选中状态
  const handleToggleGroup = async (groupId: number, select: boolean) => {
    const groupEndpoints = await fetchGroupEndpoints(groupId);
    const groupEndpointIds = groupEndpoints.map((e: any) => e.id);

    if (select) {
      setSelectedEndpointIds(prev => [...new Set([...prev, ...groupEndpointIds])]);
    } else {
      setSelectedEndpointIds(prev => prev.filter(id => !groupEndpointIds.includes(id)));
    }
  };

  // 组件加载时获取数据
  useEffect(() => {
    fetchGroups();
    fetchTestTypes();
  }, [fetchGroups]);

  // 监听分组切换，重新加载接口列表
  useEffect(() => {
    fetchEndpoints();
  }, [fetchEndpoints]);

  // 监听搜索文本变化
  useEffect(() => {
    if (debouncedSearchText) {
      setPage(1);
    }
  }, [debouncedSearchText]);

  const columns = [
    {
      title: '接口路径',
      dataIndex: 'path',
      key: 'path',
    },
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      render: (method: string) => {
        const colorMap: Record<string, string> = {
          GET: 'green',
          POST: 'blue',
          PUT: 'orange',
          DELETE: 'red',
          PATCH: 'purple',
        };
        return <Tag color={colorMap[method] || 'default'}>{method}</Tag>;
      },
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      render: (summary: string) => summary || '-',
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[]) => {
        if (!tags || tags.length === 0) return '-';
        return (
          <>
            {tags.map((tag: string) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space size="small">
          <Button type="link" size="small" onClick={() => handleViewDetail(record)}>
            查看
          </Button>
          <Button type="link" size="small" onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Button type="link" size="small" danger onClick={() => handleDelete(record.id, record.path)}>
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
          <Skeleton active paragraph={{ rows: 6 }} />
        </Card>
      </div>
    );
  }

  // 查看详情
  const handleViewDetail = (endpoint: any) => {
    setSelectedEndpoint(endpoint);
    setDetailVisible(true);
  };

  // 编辑接口
  const handleEdit = (endpoint: any) => {
    setSelectedEndpoint(endpoint);
    editForm.setFieldsValue({
      path: endpoint.path,
      method: endpoint.method,
      summary: endpoint.summary || '',
      description: endpoint.description || '',
      group_id: endpoint.group_id,
      tags: endpoint.tags || [],
      request_schema: endpoint.request_schema ? JSON.stringify(endpoint.request_schema, null, 2) : '',
      response_schema: endpoint.response_schema ? JSON.stringify(endpoint.response_schema, null, 2) : '',
    });
    setEditVisible(true);
  };

  // 删除接口
  const handleDelete = async (id: number, path: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除接口 "${path}" 吗？此操作不可恢复。`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await del(`/api-integration/endpoints/${id}`);
          message.success('删除成功');
          setPage(1); // 重新加载第一页
        } catch (error: any) {
          console.error('删除失败:', error);
          message.error(error.message || '删除失败，请稍后重试');
        }
      },
    });
  };

  // 提交编辑
  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();

      // 解析 JSON 字段
      if (values.request_schema && typeof values.request_schema === 'string') {
        try {
          const parsed = JSON.parse(values.request_schema);
          values.request_schema = parsed;
        } catch (e) {
          message.error('请求参数 JSON 格式错误');
          return;
        }
      } else if (!values.request_schema) {
        values.request_schema = null;
      }

      if (values.response_schema && typeof values.response_schema === 'string') {
        try {
          const parsed = JSON.parse(values.response_schema);
          values.response_schema = parsed;
        } catch (e) {
          message.error('响应参数 JSON 格式错误');
          return;
        }
      } else if (!values.response_schema) {
        values.response_schema = null;
      }

      // 处理 group_id
      if (values.group_id === 0) {
        values.group_id = null;
      }

      setEditLoading(true);

      await put(`/api-integration/endpoints/${selectedEndpoint.id}`, values);
      message.success('更新成功');
      setEditVisible(false);
      setPage(1); // 重新加载第一页
    } catch (error: any) {
      console.error('更新失败:', error);
      message.error(error.message || '更新失败，请稍后重试');
    } finally {
      setEditLoading(false);
    }
  };

  // 创建接口
  const handleCreate = () => {
    createForm.resetFields();
    setCreateVisible(true);
  };

  // 提交创建
  const handleCreateSubmit = async () => {
    try {
      const values = await createForm.validateFields();

      // 解析 JSON 字段
      if (values.request_schema && typeof values.request_schema === 'string') {
        try {
          const parsed = JSON.parse(values.request_schema);
          values.request_schema = parsed;
        } catch (e) {
          message.error('请求参数 JSON 格式错误');
          return;
        }
      } else if (!values.request_schema) {
        values.request_schema = null;
      }

      if (values.response_schema && typeof values.response_schema === 'string') {
        try {
          const parsed = JSON.parse(values.response_schema);
          values.response_schema = parsed;
        } catch (e) {
          message.error('响应参数 JSON 格式错误');
          return;
        }
      } else if (!values.response_schema) {
        values.response_schema = null;
      }

      // 处理 group_id
      if (values.group_id === 0) {
        values.group_id = null;
      }

      setCreateLoading(true);

      await post('/api-integration/endpoints', values);
      message.success('创建成功');
      setCreateVisible(false);
      setPage(1); // 重新加载第一页
    } catch (error: any) {
      console.error('创建失败:', error);
      message.error(error.message || '创建失败，请稍后重试');
    } finally {
      setCreateLoading(false);
    }
  };

  // 管理分组
  const handleManageGroups = () => {
    setGroupModalVisible(true);
  };

  // 创建分组
  const handleCreateGroup = async (values: any) => {
    try {
      await post('/api-integration/endpoints/groups', values);
      message.success('创建分组成功');
      fetchGroups(); // 重新加载分组列表
    } catch (error: any) {
      console.error('创建分组失败:', error);
      message.error(error.message || '创建分组失败，请稍后重试');
    }
  };

  // 高级搜索
  const handleAdvancedSearch = async () => {
    try {
      const values = await advancedSearchForm.validateFields();
      setAdvancedSearchLoading(true);

      const result = await post('/api-integration/endpoints/search', values);
      setEndpoints(result.endpoints || []);
      setTotal(result.total || 0);
      setAdvancedSearchVisible(false);
      message.success(`找到 ${result.total} 个接口`);
    } catch (error: any) {
      console.error('高级搜索失败:', error);
      message.error(error.message || '高级搜索失败，请稍后重试');
    } finally {
      setAdvancedSearchLoading(false);
    }
  };

// 处理分组选择
  const handleGroupSelect = (groupId: number | null) => {
    setSelectedGroupId(groupId);
    setPage(1);
  };

  // 处理分组编辑
  const handleGroupUpdate = async (groupId: number, values: any) => {
    try {
      await put(`/api-integration/endpoints/groups/${groupId}`, values);
      message.success('分组更新成功');
      fetchGroups(); // 重新加载分组列表
    } catch (error: any) {
      console.error('更新分组失败:', error);
      message.error(error.message || '更新分组失败');
    }
  };

  // 处理分组删除
  const handleGroupDelete = async (groupId: number) => {
    try {
      await del(`/api-integration/endpoints/groups/${groupId}`);
      message.success('分组删除成功');
      fetchGroups(); // 重新加载分组列表
      if (selectedGroupId === groupId) {
        setSelectedGroupId(null);
      }
    } catch (error: any) {
      console.error('删除分组失败:', error);
      message.error(error.message || '删除分组失败');
    }
  };

  return (
    <div>
      <Card
        title={
          <Space>
            <span>接口定义</span>
            <Tag color="blue">{currentProject.name}</Tag>
            <Tag color="green">{currentVersion.version_number}</Tag>
          </Space>
        }
        extra={
          <Button
            icon={<PlusOutlined />}
            onClick={() => {
              setGenerateVisible(true);
            }}
          >
            生成测试脚本
          </Button>
        }
      >
        <Row>
          {/* 左侧分组树 */}
          <Col 
            span={5}
            style={{ 
              borderRight: '1px solid #f0f0f0', 
              padding: '16px', 
              backgroundColor: '#fafafa'
            }}
          >
            <div style={{ height: 500, overflowY: 'auto' }}>
              <GroupTree
                groups={groups}
                selectedGroupId={selectedGroupId}
                onGroupSelect={handleGroupSelect}
                onGroupCreate={handleCreateGroup}
                onGroupUpdate={handleGroupUpdate}
                onGroupDelete={handleGroupDelete}
                selectedEndpointIds={selectedEndpointIds}
                onToggleGroup={handleToggleGroup}
              />
            </div>
          </Col>

          {/* 右侧接口列表 */}
          <Col span={19}>
            <div style={{ padding: '16px' }}>
              {/* 搜索和筛选栏 */}
              <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Space>
                  <span style={{ fontSize: 16, fontWeight: 500, color: '#333' }}>
                    {selectedGroupId
                      ? `${groups.find(g => g.id === selectedGroupId)?.name || '接口'} 共 (${total}) 个`
                      : '全部接口'
                    }
                  </span>
                  {selectedEndpointIds.length > 0 && (
                    <span style={{ fontSize: 14, color: '#666' }}>
                      已选 {selectedEndpointIds.length}/{total}
                    </span>
                  )}
                </Space>
                <Space>
                  <Input
                    placeholder="搜索接口路径、摘要、标签..."
                    prefix={<SearchOutlined />}
                    style={{ width: 150 }}
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    onPressEnter={() => setPage(1)}
                    allowClear
                  />
                  <Select
                    placeholder="筛选方法"
                    style={{ width: 120 }}
                    allowClear
                    value={filterMethod}
                    onChange={(value) => {
                      setFilterMethod(value);
                      setPage(1);
                    }}
                  >
                    <Option value="GET">GET</Option>
                    <Option value="POST">POST</Option>
                    <Option value="PUT">PUT</Option>
                    <Option value="DELETE">DELETE</Option>
                    <Option value="PATCH">PATCH</Option>
                  </Select>
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={() => {
                      setPage(1);
                      fetchEndpoints();
                    }}
                    loading={loading}
                  >
                    刷新
                  </Button>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => setCreateVisible(true)}
                  >
                    新建接口
                  </Button>
                  <Button
                    icon={<PlusOutlined />}
                    onClick={() => setImportVisible(true)}
                  >
                    导入接口
                  </Button>
                  {selectedEndpointIds.length > 0 && (
                    <Button
                      type="primary"
                      icon={<ReloadOutlined />}
                      onClick={() => {
                        setGenerateVisible(true);
                      }}
                    >
                      生成脚本
                    </Button>
                  )}
                </Space>
              </div>

              {/* 接口列表 */}
              <div>
                <Table
                  columns={columns}
                  dataSource={endpoints}
                  rowKey="id"
                  loading={loading}
                  scroll={{ y: 500 }}
                  rowSelection={{
                    selectedRowKeys: selectedEndpointIds,
                    onChange: (selectedRowKeys) => setSelectedEndpointIds(selectedRowKeys as number[]),
                    preserveSelectedRowKeys: true,  // 关键：保留分页时的选中状态
                  }}
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
              </div>
            </div>
          </Col>
        </Row>
      </Card>

      {/* 接口详情抽屉 */}
      <Drawer
        title={`接口详情 - ${selectedEndpoint?.method || ''} ${selectedEndpoint?.path || ''}`}
        placement="right"
        width={720}
        onClose={() => setDetailVisible(false)}
        open={detailVisible}
      >
        {selectedEndpoint && (
          <>
            <Descriptions title="基本信息" bordered column={1}>
              <Descriptions.Item label="接口路径">{selectedEndpoint.path}</Descriptions.Item>
              <Descriptions.Item label="请求方法">
                <Tag color="blue">{selectedEndpoint.method}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="摘要">{selectedEndpoint.summary || '-'}</Descriptions.Item>
              <Descriptions.Item label="描述">{selectedEndpoint.description || '-'}</Descriptions.Item>
              <Descriptions.Item label="标签">
                {selectedEndpoint.tags && selectedEndpoint.tags.length > 0 ? (
                  selectedEndpoint.tags.map((tag: string) => (
                    <Tag key={tag}>{tag}</Tag>
                  ))
                ) : (
                  '-'
                )}
              </Descriptions.Item>
            </Descriptions>

            <Descriptions title="请求参数" bordered column={1} style={{ marginTop: 24 }}>
              <Descriptions.Item label="Request Schema">
                <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                  {JSON.stringify(selectedEndpoint.request_schema, null, 2) || '-'}
                </pre>
              </Descriptions.Item>
            </Descriptions>

            <Descriptions title="响应示例" bordered column={1} style={{ marginTop: 24 }}>
              <Descriptions.Item label="Response Schema">
                <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                  {JSON.stringify(selectedEndpoint.response_schema, null, 2) || '-'}
                </pre>
              </Descriptions.Item>
            </Descriptions>
          </>
        )}
      </Drawer>

      {/* 接口编辑弹窗 */}
      <Modal
        title={`编辑接口 - ${selectedEndpoint?.method || ''} ${selectedEndpoint?.path || ''}`}
        open={editVisible}
        onCancel={() => setEditVisible(false)}
        onOk={handleEditSubmit}
        confirmLoading={editLoading}
        width={600}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            label="接口路径"
            name="path"
            rules={[{ required: true, message: '请输入接口路径' }]}
          >
            <Input placeholder="/api/users" />
          </Form.Item>
          
          <Form.Item
            label="请求方法"
            name="method"
            rules={[{ required: true, message: '请选择请求方法' }]}
          >
            <Select placeholder="请选择">
              <Option value="GET">GET</Option>
              <Option value="POST">POST</Option>
              <Option value="PUT">PUT</Option>
              <Option value="DELETE">DELETE</Option>
              <Option value="PATCH">PATCH</Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="摘要" name="summary">
            <Input placeholder="接口摘要" />
          </Form.Item>
          
          <Form.Item label="描述" name="description">
            <TextArea rows={3} placeholder="接口描述" />
          </Form.Item>
          
          <Form.Item label="分组" name="group_id">
            <Select placeholder="请选择分组" allowClear>
              {groups.map(group => (
                <Option key={group.id} value={group.id}>{group.name}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item label="请求参数 (JSON)" name="request_schema">
            <TextArea 
              rows={6} 
              placeholder='{"type": "object", "properties": {...}}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item label="响应参数 (JSON)" name="response_schema">
            <TextArea 
              rows={6} 
              placeholder='{"type": "object", "properties": {...}}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 接口创建弹窗 */}
      <Modal
        title="新建接口"
        open={createVisible}
        onCancel={() => setCreateVisible(false)}
        onOk={handleCreateSubmit}
        confirmLoading={createLoading}
        width={600}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            label="接口路径"
            name="path"
            rules={[{ required: true, message: '请输入接口路径' }]}
          >
            <Input placeholder="/api/users" />
          </Form.Item>
          
          <Form.Item
            label="请求方法"
            name="method"
            rules={[{ required: true, message: '请选择请求方法' }]}
          >
            <Select placeholder="请选择">
              <Option value="GET">GET</Option>
              <Option value="POST">POST</Option>
              <Option value="PUT">PUT</Option>
              <Option value="DELETE">DELETE</Option>
              <Option value="PATCH">PATCH</Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="摘要" name="summary">
            <Input placeholder="接口摘要" />
          </Form.Item>
          
          <Form.Item label="描述" name="description">
            <TextArea rows={3} placeholder="接口描述" />
          </Form.Item>
          
          <Form.Item label="分组" name="group_id">
            <Select placeholder="请选择分组" allowClear>
              {groups.map(group => (
                <Option key={group.id} value={group.id}>{group.name}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item label="请求参数 (JSON)" name="request_schema">
            <TextArea 
              rows={6} 
              placeholder='{"type": "object", "properties": {...}}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item label="响应参数 (JSON)" name="response_schema">
            <TextArea 
              rows={6} 
              placeholder='{"type": "object", "properties": {...}}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 分组管理弹窗 */}
      <Modal
        title="管理分组"
        open={groupModalVisible}
        onCancel={() => setGroupModalVisible(false)}
        footer={null}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Form form={groupForm} layout="inline" style={{ width: '100%' }}>
            <Form.Item name="name" rules={[{ required: true, message: '请输入分组名称' }]}>
              <Input placeholder="分组名称" style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="description">
              <Input placeholder="分组描述" style={{ width: 200 }} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" onClick={handleCreateGroup} loading={groupLoading}>
                添加分组
              </Button>
            </Form.Item>
          </Form>
          
          <div>
            <h4>现有分组：</h4>
            {groups.length === 0 ? (
              <p style={{ color: '#999' }}>暂无分组</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {groups.map(group => (
                  <li key={group.id} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                    <Space>
                      <span>{group.name}</span>
                      <span style={{ color: '#999' }}>{group.description || '无描述'}</span>
                    </Space>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Space>
      </Modal>

      {/* 高级搜索弹窗 */}
      <Modal
        title="高级搜索"
        open={advancedSearchVisible}
        onCancel={() => setAdvancedSearchVisible(false)}
        onOk={handleAdvancedSearch}
        confirmLoading={advancedSearchLoading}
        width={600}
      >
        <Form form={advancedSearchForm} layout="vertical">
          <Form.Item label="关键词" name="keyword">
            <Input placeholder="搜索路径、摘要、描述" />
          </Form.Item>
          
          <Form.Item label="请求方法" name="methods">
            <Select mode="multiple" placeholder="选择请求方法" allowClear>
              <Option value="GET">GET</Option>
              <Option value="POST">POST</Option>
              <Option value="PUT">PUT</Option>
              <Option value="DELETE">DELETE</Option>
              <Option value="PATCH">PATCH</Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="标签" name="tags">
            <Select mode="tags" placeholder="选择或输入标签" allowClear />
          </Form.Item>
          
          <Form.Item label="分组" name="group_id">
            <Select placeholder="选择分组" allowClear>
              {groups.map(group => (
                <Option key={group.id} value={group.id}>{group.name}</Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item label="路径模式（正则表达式）" name="path_pattern">
            <Input placeholder="例如：/api/users/.*" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 生成测试脚本弹窗 */}
      <Modal
        title="生成测试脚本"
        open={generateVisible}
        onCancel={() => setGenerateVisible(false)}
        footer={null}
        width={700}
      >
        <Alert
          message={`已选择 ${selectedEndpointIds.length} 个接口`}
          description="将在主页面上选中的接口生成测试脚本"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        
        <Collapse
          defaultActiveKey={['preset']}
          items={[
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

export default React.memo(Endpoints);