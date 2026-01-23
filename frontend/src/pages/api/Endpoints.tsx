import React, { useState, useEffect, useCallback } from 'react';
import { Card, Table, Button, Space, Tag, Input, Select, message, Spin, Modal, Drawer, Descriptions, Form } from 'antd';
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons';
import { useProjectStore } from '../../store/project';

const { Search } = Input;
const { Option } = Select;
const { TextArea } = Input;

const Endpoints: React.FC = () => {
  const { currentProject, currentVersion } = useProjectStore();
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
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

  // 获取接口列表
  const fetchEndpoints = useCallback(async () => {
    setLoading(true);
    try {
      // 从 localStorage 获取 token
      const token = localStorage.getItem('token');
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      // 不再传递 project_id 和 version_id，后端会自动从用户上下文获取
      const params = new URLSearchParams({
        skip: ((page - 1) * pageSize).toString(),
        limit: pageSize.toString(),
      });
      
      if (filterMethod) {
        params.append('method', filterMethod);
      }
      
      if (searchText) {
        params.append('keyword', searchText);
      }
      
      const response = await fetch(`/api/v1/api-integration/endpoints?${params}`, {
        method: 'GET',
        headers,
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.code === 0) {
        setEndpoints(result.data.endpoints || []);
        setTotal(result.data.total || 0);
      } else {
        message.error(result.message || '获取接口列表失败');
      }
    } catch (error: any) {
      console.error('获取接口列表失败:', error);
      message.error('获取接口列表失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filterMethod, searchText]);

  // 获取分组列表
  const fetchGroups = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/api-integration/endpoints/groups', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });
      
      const result = await response.json();
      if (result.code === 0) {
        setGroups(result.data.groups || []);
      }
    } catch (error) {
      console.error('获取分组列表失败:', error);
    }
  }, []);

  // 组件加载时获取数据
  useEffect(() => {
    fetchEndpoints();
    fetchGroups();
  }, [fetchEndpoints, fetchGroups]);

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

  // 如果没有选择项目或版本，显示提示
  if (!currentProject || !currentVersion) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Spin size="large" tip="加载中..." />
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
          const token = localStorage.getItem('token');
          const response = await fetch(`/api/v1/api-integration/endpoints/${id}`, {
            method: 'DELETE',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
            },
          });
          
          const result = await response.json();
          if (result.code === 0) {
            message.success('删除成功');
            setPage(1); // 重新加载第一页
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

  // 提交编辑
  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      setEditLoading(true);
      
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/v1/api-integration/endpoints/${selectedEndpoint.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(values),
      });
      
      const result = await response.json();
      if (result.code === 0) {
        message.success('更新成功');
        setEditVisible(false);
        setPage(1); // 重新加载第一页
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

  // 创建接口
  const handleCreate = () => {
    createForm.resetFields();
    setCreateVisible(true);
  };

  // 提交创建
  const handleCreateSubmit = async () => {
    try {
      const values = await createForm.validateFields();
      setCreateLoading(true);
      
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/api-integration/endpoints', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(values),
      });
      
      const result = await response.json();
      if (result.code === 0) {
        message.success('创建成功');
        setCreateVisible(false);
        setPage(1); // 重新加载第一页
      } else {
        message.error(result.message || '创建失败');
      }
    } catch (error: any) {
      console.error('创建失败:', error);
      message.error('创建失败，请稍后重试');
    } finally {
      setCreateLoading(false);
    }
  };

  // 管理分组
  const handleManageGroups = () => {
    setGroupModalVisible(true);
  };

  // 创建分组
  const handleCreateGroup = async () => {
    try {
      const values = await groupForm.validateFields();
      setGroupLoading(true);
      
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/api-integration/endpoints/groups', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(values),
      });
      
      const result = await response.json();
      if (result.code === 0) {
        message.success('创建分组成功');
        groupForm.resetFields();
        fetchGroups(); // 重新加载分组列表
      } else {
        message.error(result.message || '创建分组失败');
      }
    } catch (error: any) {
      console.error('创建分组失败:', error);
      message.error('创建分组失败，请稍后重试');
    } finally {
      setGroupLoading(false);
    }
  };

  // 高级搜索
  const handleAdvancedSearch = async () => {
    try {
      const values = await advancedSearchForm.validateFields();
      setAdvancedSearchLoading(true);
      
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/api-integration/endpoints/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(values),
      });
      
      const result = await response.json();
      if (result.code === 0) {
        setEndpoints(result.data.endpoints || []);
        setTotal(result.data.total || 0);
        setAdvancedSearchVisible(false);
        message.success(`找到 ${result.data.total} 个接口`);
      } else {
        message.error(result.message || '搜索失败');
      }
    } catch (error: any) {
      console.error('高级搜索失败:', error);
      message.error('高级搜索失败，请稍后重试');
    } finally {
      setAdvancedSearchLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <Space>
            <span>接口定义</span>
            <Tag color="blue">{currentProject.name}</Tag>
            <Tag color="green">{currentVersion.version_number}</Tag>
          </Space>
        }
        extra={
          <Space>
            <Button onClick={() => setAdvancedSearchVisible(true)}>
              高级搜索
            </Button>
            <Button icon={<PlusOutlined />} onClick={handleManageGroups}>
              管理分组
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              新建接口
            </Button>
            <Search
              placeholder="搜索接口"
              style={{ width: 200 }}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onSearch={() => setPage(1)}
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
              onClick={() => setPage(1)}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={endpoints}
          rowKey="id"
          loading={loading}
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
    </div>
  );
};

export default Endpoints;