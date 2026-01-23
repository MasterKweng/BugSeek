import React, { useState, useEffect } from 'react';
import { Modal, Table, Button, Space, Tag, message, Input, Drawer, Spin } from 'antd';
import { HistoryOutlined, PlusOutlined, SwapOutlined, EyeOutlined } from '@ant-design/icons';
import * as documentService from '../services/document';

interface DocumentVersionsProps {
  visible: boolean;
  documentId: number;
  documentName: string;
  onCancel: () => void;
}

const DocumentVersions: React.FC<DocumentVersionsProps> = ({
  visible,
  documentId,
  documentName,
  onCancel
}) => {
  const [versions, setVersions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [newVersion, setNewVersion] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [compareModalVisible, setCompareModalVisible] = useState(false);
  const [compareData, setCompareData] = useState<any>(null);

  const fetchVersions = async () => {
    setLoading(true);
    try {
      const response = await documentService.getDocumentVersions(documentId);
      setVersions(response.versions || []);
    } catch (error) {
      message.error('获取版本历史失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      fetchVersions();
    }
  }, [visible, documentId]);

  const handleCreateVersion = async () => {
    if (!newVersion) {
      message.warning('请输入版本号');
      return;
    }

    setCreateLoading(true);
    try {
      await documentService.createDocumentVersion(documentId, newVersion);
      message.success('版本创建成功');
      setCreateModalVisible(false);
      setNewVersion('');
      fetchVersions();
    } catch (error: any) {
      message.error(error.response?.data?.message || '版本创建失败');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleCompareVersions = async (versionId: number) => {
    try {
      const response = await documentService.compareDocumentVersions(documentId, versionId);
      setCompareData(response.data);
      setCompareModalVisible(true);
    } catch (error) {
      message.error('版本对比失败');
    }
  };

  const handleRollbackVersion = async (versionId: number, versionName: string) => {
    Modal.confirm({
      title: '确认回滚',
      content: `确定要回滚到版本 "${versionName}" 吗？此操作将创建一个新版本。`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await documentService.rollbackDocumentVersion(documentId, versionId);
          message.success('回滚成功');
          fetchVersions();
        } catch (error: any) {
          message.error(error.response?.data?.message || '回滚失败');
        }
      },
    });
  };

  const columns = [
    {
      title: '版本号',
      dataIndex: 'version',
      key: 'version',
      render: (version: string, record: any) => (
        <Space>
          <Tag>{version}</Tag>
          {record.is_latest && <Tag color="green">最新</Tag>}
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => date ? new Date(date).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space size="small">
          {!record.is_latest && (
            <Button
              type="link"
              size="small"
              icon={<SwapOutlined />}
              onClick={() => handleRollbackVersion(record.id, record.version)}
            >
              回滚
            </Button>
          )}
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleCompareVersions(record.id)}
          >
            对比
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Drawer
        title={
          <Space>
            <HistoryOutlined />
            <span>版本历史 - {documentName}</span>
          </Space>
        }
        open={visible}
        onClose={onCancel}
        width={800}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            创建新版本
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={versions}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          scroll={{ y: 500 }}
        />
      </Drawer>

      {/* 创建新版本弹窗 */}
      <Modal
        title="创建新版本"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
          setNewVersion('');
        }}
        onOk={handleCreateVersion}
        confirmLoading={createLoading}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <label style={{ display: 'block', marginBottom: 8 }}>版本号：</label>
            <Input
              placeholder="例如: 1.1.0"
              value={newVersion}
              onChange={(e) => setNewVersion(e.target.value)}
            />
          </div>
        </Space>
      </Modal>

      {/* 版本对比弹窗 */}
      <Modal
        title="版本对比"
        open={compareModalVisible}
        onCancel={() => setCompareModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setCompareModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={600}
      >
        {compareData ? (
          <div>
            <p><strong>版本 1:</strong> {compareData.version1}</p>
            <p><strong>版本 2:</strong> {compareData.version2}</p>
            <p><strong>内容长度差异:</strong> {compareData.content_length_diff} 字符</p>
            <p><strong>内容是否相同:</strong> {compareData.same_content ? '是' : '否'}</p>
          </div>
        ) : (
          <Spin />
        )}
      </Modal>
    </>
  );
};

export default DocumentVersions;