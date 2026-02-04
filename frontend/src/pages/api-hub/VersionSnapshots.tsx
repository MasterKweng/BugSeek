/**
 * 版本快照列表页面（V2.0 层级一 - API 资产库）
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
  Tag,
  Modal,
  message,
  Card,
  Row,
  Col,
  Tooltip,
  Drawer,
  Timeline,
  Descriptions,
  Popconfirm,
  Select,
} from 'antd';
import {
  PlusOutlined,
  EyeOutlined,
  DeleteOutlined,
  SwapOutlined,
  ClockCircleOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import api from '../../services/api';

interface VersionSnapshot {
  id: number;
  definition_id: number | null;
  project_id: number;
  version_id: number | null;
  version_hash: string | null;
  version_tag: string | null;
  source_version: string | null;
  name: string | null;
  description: string | null;
  snapshot_type: string;
  schema_snapshot: any;
  total_count: number;
  created_at: string;
  created_by: number | null;
  created_by_name: string | null;
}

interface ApiResponse {
  code: number;
  message: string;
  data: any;
}

const VersionSnapshots: React.FC = () => {
  // 状态管理
  const [loading, setLoading] = useState(false);
  const [snapshots, setSnapshots] = useState<VersionSnapshot[]>([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [selectedDefinitionId, setSelectedDefinitionId] = useState<number | null>(null);
  const [definitions, setDefinitions] = useState<any[]>([]);
  
  // 弹窗状态
  const [compareModalVisible, setCompareModalVisible] = useState(false);
  const [compareData, setCompareData] = useState<any>(null);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [currentSnapshot, setCurrentSnapshot] = useState<VersionSnapshot | null>(null);
  
  // 创建快照状态
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [createFormValues, setCreateFormValues] = useState({ version_tag: '', description: '' });
  const [creating, setCreating] = useState(false);

  // 获取接口定义列表
  const fetchDefinitions = async () => {
    try {
      const response = await api.get('/api-definitions');
      if (response.code === 0) {
        setDefinitions(response.data.items || []);
      }
    } catch (error) {
      console.error('获取接口列表失败:', error);
    }
  };

  // 获取快照列表
  const fetchSnapshots = async () => {
    if (!selectedDefinitionId) {
      setSnapshots([]);
      setTotal(0);
      return;
    }
    
    setLoading(true);
    try {
      const params = new URLSearchParams({
        skip: String((pagination.current - 1) * pagination.pageSize),
        limit: String(pagination.pageSize),
      });

      const response = await api.get(`/api-definitions/${selectedDefinitionId}/snapshots?${params}`);

      if (response.code === 0) {
        setSnapshots(response.data.items || []);
        setTotal(response.data.total || 0);
      } else {
        message.error(response.message || '获取数据失败');
      }
    } catch (error) {
      console.error('获取快照列表失败:', error);
      message.error('获取数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDefinitions();
  }, []);

  useEffect(() => {
    fetchSnapshots();
  }, [pagination, selectedDefinitionId]);

  // 创建快照
  const handleCreateSnapshot = async () => {
    setCreating(true);
    try {
      const response = await api.post('/version-snapshots', createFormValues);

      if (response.code === 0) {
        message.success('快照创建成功');
        setCreateModalVisible(false);
        setCreateFormValues({ version_tag: '', description: '' });
        fetchSnapshots();
      } else {
        message.error(response.message || '创建失败');
      }
    } catch (error) {
      console.error('创建快照失败:', error);
      message.error('创建失败，请稍后重试');
    } finally {
      setCreating(false);
    }
  };

  // 删除快照
  const handleDelete = async (record: VersionSnapshot) => {
    try {
      const response = await api.delete(`/snapshots/${record.id}`);

      if (response.code === 0) {
        message.success('删除成功');
        fetchSnapshots();
      } else {
        message.error(response.message || '删除失败');
      }
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请稍后重试');
    }
  };

  // 查看详情
  const handleViewDetail = (record: VersionSnapshot) => {
    setCurrentSnapshot(record);
    setDetailDrawerVisible(true);
  };

  // 版本对比
  const handleCompare = (record: VersionSnapshot) => {
    // 这里简化处理，实际应该让用户选择两个快照进行对比
    // 暂时跳过，因为需要实现选择两个快照的界面
    message.info('版本对比功能开发中，请稍后使用');
  };

  // 快照类型标签
  const getSnapshotTypeTag = (type: string) => {
    const typeMap: Record<string, { text: string; color: string }> = {
      manual: { text: '手动', color: 'blue' },
      auto: { text: '自动', color: 'green' },
    };
    const typeInfo = typeMap[type] || { text: type, color: 'default' };
    return <Tag color={typeInfo.color}>{typeInfo.text}</Tag>;
  };

  // 表格列定义
  const columns: ColumnsType<VersionSnapshot> = [
    {
      title: '版本标签',
      dataIndex: 'version_tag',
      key: 'version_tag',
      width: 120,
      render: (tag: string) => tag ? <Tag color="blue">{tag}</Tag> : '-',
    },
    {
      title: '版本哈希',
      dataIndex: 'version_hash',
      key: 'version_hash',
      width: 150,
      render: (hash: string) => hash ? (
        <Tooltip title={hash}>
          <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>
            {hash.substring(0, 8)}...
          </span>
        </Tooltip>
      ) : '-',
    },
    {
      title: '来源版本',
      dataIndex: 'source_version',
      key: 'source_version',
      width: 120,
      render: (version: string) => version || '-',
    },
    {
      title: '类型',
      dataIndex: 'snapshot_type',
      key: 'snapshot_type',
      width: 100,
      render: getSnapshotTypeTag,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (desc: string) => desc || '-',
    },
    {
      title: '创建人',
      dataIndex: 'created_by_name',
      key: 'created_by_name',
      width: 100,
      render: (name: string) => name || '-',
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
      render: (_: any, record: VersionSnapshot) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record)}
            />
          </Tooltip>
          <Tooltip title="版本对比">
            <Button
              type="link"
              size="small"
              icon={<SwapOutlined />}
              onClick={() => handleCompare(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除此快照吗？"
            onConfirm={() => handleDelete(record)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除快照">
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
    <div style={{ padding: '24px' }}>
      <Card>
        {/* 顶部操作栏 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={18}>
            <h2>版本快照</h2>
          </Col>
          <Col span={6} style={{ textAlign: 'right' }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
              disabled={!selectedDefinitionId}
            >
              创建快照
            </Button>
          </Col>
        </Row>

        {/* 接口定义选择器 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={24}>
            <Card size="small">
              <Space style={{ width: '100%' }}>
                <span style={{ marginRight: 8 }}>选择接口：</span>
                <Select
                  style={{ width: '400px' }}
                  placeholder="请选择要查看快照的接口"
                  value={selectedDefinitionId}
                  onChange={(value) => {
                    setSelectedDefinitionId(value);
                    setPagination({ current: 1, pageSize: 20 });
                  }}
                  showSearch
                  filterOption={(input, option) => {
                    const searchText = (option?.method + ' ' + option?.path || '').toLowerCase();
                    return searchText.includes(input.toLowerCase());
                  }}
                  >
                  {definitions.map((def) => (
                    <Select.Option key={def.id} value={def.id}>
                      {def.method} {def.path}
                    </Select.Option>
                  ))}
                </Select>
              </Space>
            </Card>
          </Col>
        </Row>

        {/* 数据表格 */}
        <Table
          columns={columns}
          dataSource={snapshots}
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
          locale={{
            emptyText: selectedDefinitionId ? '暂无快照数据' : '请先选择接口定义'
          }}
        />
      </Card>

      {/* 创建快照弹窗 */}
      <Modal
        title="创建版本快照"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
          setCreateFormValues({ version_tag: '', description: '' });
        }}
        footer={[
          <Button key="cancel" onClick={() => {
            setCreateModalVisible(false);
            setCreateFormValues({ version_tag: '', description: '' });
          }}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={creating}
            onClick={handleCreateSnapshot}
          >
            创建
          </Button>,
        ]}
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 8 }}>版本标签：</label>
          <input
            type="text"
            placeholder="例如：v1.2.3"
            value={createFormValues.version_tag}
            onChange={(e) => setCreateFormValues({ ...createFormValues, version_tag: e.target.value })}
            style={{ width: '100%', padding: '8px', border: '1px solid #d9d9d9', borderRadius: '4px' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 8 }}>描述：</label>
          <textarea
            placeholder="请输入快照描述"
            value={createFormValues.description}
            onChange={(e) => setCreateFormValues({ ...createFormValues, description: e.target.value })}
            rows={4}
            style={{ width: '100%', padding: '8px', border: '1px solid #d9d9d9', borderRadius: '4px' }}
          />
        </div>
      </Modal>

      {/* 详情抽屉 */}
      <Drawer
        title="版本快照详情"
        placement="right"
        width={720}
        open={detailDrawerVisible}
        onClose={() => setDetailDrawerVisible(false)}
      >
        {currentSnapshot && (
          <div>
            <Descriptions bordered column={2} style={{ marginBottom: 24 }}>
              <Descriptions.Item label="版本标签" span={2}>
                {currentSnapshot.version_tag || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="版本哈希" span={2}>
                {currentSnapshot.version_hash || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="来源版本" span={2}>
                {currentSnapshot.source_version || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="快照类型" span={1}>
                {getSnapshotTypeTag(currentSnapshot.snapshot_type)}
              </Descriptions.Item>
              <Descriptions.Item label="接口数量" span={1}>
                {currentSnapshot.total_count}
              </Descriptions.Item>
              <Descriptions.Item label="描述" span={2}>
                {currentSnapshot.description || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="创建人" span={1}>
                <span>{currentSnapshot.created_by_name || '-'}</span>
              </Descriptions.Item>
              <Descriptions.Item label="创建时间" span={1}>
                {new Date(currentSnapshot.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
            </Descriptions>

            {currentSnapshot.schema_snapshot && (
              <Card title="Schema 数据" style={{ marginBottom: 16 }}>
                <pre style={{ 
                  maxHeight: '400px', 
                  overflow: 'auto', 
                  fontSize: '12px', 
                  padding: '12px', 
                  background: '#f5f5f5', 
                  borderRadius: '4px' 
                }}>
                  {JSON.stringify(currentSnapshot.schema_snapshot, null, 2)}
                </pre>
              </Card>
            )}
          </div>
        )}
      </Drawer>

      {/* 版本对比弹窗 */}
      <Modal
        title="版本对比"
        open={compareModalVisible}
        onCancel={() => setCompareModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setCompareModalVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
      >
        {compareData && (
          <div>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={12}>
                <Card size="small" title="源版本">
                  <Tag color="blue">{compareData.source?.version_tag}</Tag>
                  <div style={{ marginTop: 8, fontSize: '12px', color: '#999' }}>
                    {compareData.source?.version_hash?.substring(0, 16)}...
                  </div>
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" title="目标版本">
                  <Tag color="green">{compareData.target?.version_tag}</Tag>
                  <div style={{ marginTop: 8, fontSize: '12px', color: '#999' }}>
                    {compareData.target?.version_hash?.substring(0, 16)}...
                  </div>
                </Card>
              </Col>
            </Row>
            <p style={{ textAlign: 'center', color: '#999' }}>
              版本对比功能开发中...
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default VersionSnapshots;