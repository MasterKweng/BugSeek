import React, { useState, useEffect, useCallback } from 'react';
import { Card, Table, Button, Space, Tag, message, Modal, Input, Select } from 'antd';
import { PlusOutlined, ReloadOutlined, DeleteOutlined, EyeOutlined, HistoryOutlined, FileTextOutlined } from '@ant-design/icons';
import ImportModal from './components/ImportModal';
import DocumentVersions from './components/DocumentVersions';
import * as documentService from './services/document';
import { useProjectStore } from '../../store/project';

const { Search } = Input;
const { Option } = Select;

const Documents: React.FC = () => {
  const { currentProject, currentVersion } = useProjectStore();
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [versionsModalVisible, setVersionsModalVisible] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<any>(null);

  // 搜索防抖 (P1-1)
  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchText(e.target.value);
  }, []);

  // 空值防御 (P1-2)
  const filteredDocuments = documents.filter((doc) => {
    const docName = doc?.name?.toLowerCase?.() || '';
    const docType = doc?.source_type || '';
    const matchSearch = !searchText || docName.includes(searchText.toLowerCase());
    const matchType = filterType === 'all' || docType === filterType;
    return matchSearch && matchType;
  });

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      // 不再传递 project_id 和 version_id，后端会自动从用户上下文获取
      const response = await documentService.getDocuments({ limit: 100 });
      setDocuments(response.documents || []);
    } catch (error) {
      message.error('获取文档列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleImport = async (data: any) => {
    setImportLoading(true);
    try {
      await documentService.importDocument(data);
      message.success('文档导入成功');
      setImportModalVisible(false);
      fetchDocuments();
    } catch (error: any) {
      message.error(error.response?.data?.message || '文档导入失败');
    } finally {
      setImportLoading(false);
    }
  };

  const handleDelete = (id: number, name: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除文档 "${name}" 吗？此操作不可恢复。`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await documentService.deleteDocument(id);
          message.success('删除成功');
          fetchDocuments();
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };

  const handleRefresh = () => {
    fetchDocuments();
    message.success('刷新成功');
  };

  const handleShowVersions = (document: any) => {
    setSelectedDocument(document);
    setVersionsModalVisible(true);
  };

  const handleParseDocument = async (document: any) => {
    try {
      await documentService.parseDocument(document.id);
      message.success('文档解析成功');
      fetchDocuments();
    } catch (error: any) {
      message.error(error.response?.data?.message || '文档解析失败');
    }
  };

  const columns = [
    {
      title: '文档名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: any) => (
        <Space>
          <span>{name || '未命名'}</span>
          {record?.source_url && (
            <Tag color="cyan">URL</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '来源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      render: (type: string) => {
        const colorMap: Record<string, string> = {
          swagger: 'blue',
          openapi: 'blue',
          yapi: 'green',
          postman: 'orange',
        };
        return <Tag color={colorMap[type] || 'default'}>{type || '未知'}</Tag>;
      },
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      render: (version: string) => <Tag>{version || '1.0.0'}</Tag>,
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
          <Button
            type="link"
            size="small"
            icon={<HistoryOutlined />}
            onClick={() => handleShowVersions(record)}
          >
            版本
          </Button>
          <Button
            type="link"
            size="small"
            icon={<FileTextOutlined />}
            onClick={() => handleParseDocument(record)}
          >
            解析
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              message.info('查看详情功能开发中');
            }}
          >
            查看
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record?.id, record?.name)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="文档管理"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setImportModalVisible(true)}>
              导入文档
            </Button>
          </Space>
        }
      >
        <Space style={{ marginBottom: 16 }} size="middle">
          <Search
            placeholder="搜索文档名称"
            allowClear
            style={{ width: 250 }}
            value={searchText}
            onChange={handleSearchChange}
          />
          <Select
            style={{ width: 150 }}
            value={filterType}
            onChange={setFilterType}
          >
            <Option value="all">全部类型</Option>
            <Option value="swagger">Swagger</Option>
            <Option value="openapi">OpenAPI</Option>
            <Option value="yapi">YApi</Option>
            <Option value="postman">Postman</Option>
          </Select>
        </Space>

        <Table
          columns={columns}
          dataSource={filteredDocuments}
          rowKey="id"
          loading={loading}
          scroll={{ y: 500 }}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
        />
      </Card>

      <ImportModal
        visible={importModalVisible}
        onCancel={() => setImportModalVisible(false)}
        onImport={handleImport}
        loading={importLoading}
      />

      <DocumentVersions
        visible={versionsModalVisible}
        documentId={selectedDocument?.id || 0}
        documentName={selectedDocument?.name || ''}
        onCancel={() => {
          setVersionsModalVisible(false);
          setSelectedDocument(null);
        }}
      />
    </div>
  );
};

export default Documents;