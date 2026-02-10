import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Table, 
  Button, 
  Space, 
  Tag, 
  Modal, 
  message, 
  Spin, 
  Tabs, 
  Descriptions,
  Badge,
  Checkbox
} from 'antd';
import { 
  PlusOutlined, 
  SearchOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined,
  PlayCircleOutlined,
  SyncOutlined
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useProjectStore } from '../store/project';
import * as fieldMappingService from '../services/fieldMapping';
import type { 
  FieldMappingSuggestion, 
  FieldMappingCandidate,
  FieldMappingBatchApplyItem 
} from '../services/fieldMapping';
import type { FieldMapping } from '../types';

const { TabPane } = Tabs;

const FieldMappingSuggestions: React.FC = () => {
  const navigate = useNavigate();
  const { currentProject, currentVersion } = useProjectStore();
  const [suggestions, setSuggestions] = useState<FieldMappingSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
  const [selectedCandidates, setSelectedCandidates] = useState<Record<number, FieldMappingCandidate | null>>({});
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedSuggestion, setSelectedSuggestion] = useState<FieldMappingSuggestion | null>(null);
  const [includePaths, setIncludePaths] = useState(true);
  const [includeQuery, setIncludeQuery] = useState(true);
  const [includeBody, setIncludeBody] = useState(true);
  
  // 高置信度阈值
  const HIGH_CONFIDENCE_THRESHOLD = 0.85;
  // 中等置信度阈值
  const MEDIUM_CONFIDENCE_THRESHOLD = 0.60;

  // 获取建议
  const fetchSuggestions = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    setLoading(true);
    try {
      const response = await fieldMappingService.suggestFieldMappings(
        { include_paths: includePaths, include_query: includeQuery, include_body: includeBody },
        { project_id: currentProject.id, version_id: currentVersion.id }
      );
      
      if (response.code === 0) {
        setSuggestions(response.data?.items || []);
        message.success(`生成了 ${response.data?.items?.length || 0} 个映射建议`);
      } else {
        message.error(response.message || '获取建议失败');
      }
    } catch (error: any) {
      console.error('获取建议失败:', error);
      message.error(error.message || '获取建议失败');
    } finally {
      setLoading(false);
    }
  };

  // 批量确认选中的映射
  const handleBatchConfirm = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    const selectedSuggestions = suggestions.filter(s => selectedRowKeys.includes(s.definition_id));
    
    if (selectedSuggestions.length === 0) {
      message.warning('请先选择要确认的映射');
      return;
    }

    // 准备批量应用的数据
    const batchItems: FieldMappingBatchApplyItem[] = [];
    
    selectedSuggestions.forEach(suggestion => {
      const selectedCandidate = selectedCandidates[suggestion.definition_id];
      if (selectedCandidate) {
        batchItems.push({
          definition_id: suggestion.definition_id,
          api_field_path: suggestion.api_field_path,
          db_table: selectedCandidate.db_table,
          db_column: selectedCandidate.db_column,
          relation_type: 'direct',
          source: 'ai'
        });
      }
    });

    if (batchItems.length === 0) {
      message.warning('请为选中的映射选择候选字段');
      return;
    }

    try {
      const response = await fieldMappingService.batchApplyFieldMappings(
        { items: batchItems, mode: 'confirm' },
        { project_id: currentProject.id, version_id: currentVersion.id }
      );

      if (response.code === 0) {
        message.success(`成功确认了 ${response.data?.processed_count} 个映射`);
        setConfirmModalVisible(false);
        setSelectedRowKeys([]);
        // 重新获取建议
        fetchSuggestions();
      } else {
        message.error(response.message || '批量确认失败');
      }
    } catch (error: any) {
      console.error('批量确认失败:', error);
      message.error(error.message || '批量确认失败');
    }
  };

  // 单个确认映射
  const handleConfirmSingle = async (suggestion: FieldMappingSuggestion, candidate: FieldMappingCandidate) => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    try {
      const response = await fieldMappingService.batchApplyFieldMappings(
        {
          items: [{
            definition_id: suggestion.definition_id,
            api_field_path: suggestion.api_field_path,
            db_table: candidate.db_table,
            db_column: candidate.db_column,
            relation_type: 'direct',
            source: 'ai'
          }],
          mode: 'confirm'
        },
        { project_id: currentProject.id, version_id: currentVersion.id }
      );

      if (response.code === 0) {
        message.success('映射确认成功');
        // 重新获取建议
        fetchSuggestions();
      } else {
        message.error(response.message || '确认失败');
      }
    } catch (error: any) {
      console.error('确认映射失败:', error);
      message.error(error.message || '确认失败');
    }
  };

  // 显示详情模态框
  const showDetailModal = (suggestion: FieldMappingSuggestion) => {
    setSelectedSuggestion(suggestion);
    setDetailModalVisible(true);
  };

  // 表格列定义
  const columns = [
    {
      title: 'API',
      dataIndex: 'definition_path',
      key: 'api',
      render: (text: string, record: FieldMappingSuggestion) => (
        <div>
          <Tag color={getMethodColor(record.definition_method)}>
            {record.definition_method}
          </Tag>
          <span>{record.definition_path}</span>
        </div>
      )
    },
    {
      title: 'API 字段路径',
      dataIndex: 'api_field_path',
      key: 'api_field_path'
    },
    {
      title: '推荐表/字段',
      key: 'recommended',
      render: (_: any, record: FieldMappingSuggestion) => {
        if (record.candidates && record.candidates.length > 0) {
          const topCandidate = record.candidates[0];
          return (
            <div>
              <div><strong>{topCandidate.db_table}</strong>.{topCandidate.db_column}</div>
              <div style={{ fontSize: '12px', color: '#999' }}>
                置信度: {(topCandidate.score * 100).toFixed(1)}%
              </div>
            </div>
          );
        }
        return <span style={{ color: '#ccc' }}>无推荐</span>;
      }
    },
    {
      title: '置信度',
      key: 'confidence',
      render: (_: any, record: FieldMappingSuggestion) => {
        if (record.candidates && record.candidates.length > 0) {
          const topCandidate = record.candidates[0];
          let color = 'default';
          if (topCandidate.score >= HIGH_CONFIDENCE_THRESHOLD) {
            color = 'success';
          } else if (topCandidate.score >= MEDIUM_CONFIDENCE_THRESHOLD) {
            color = 'warning';
          } else {
            color = 'error';
          }
          
          return <Tag color={color}>{(topCandidate.score * 100).toFixed(1)}%</Tag>;
        }
        return <span>-</span>;
      }
    },
    {
      title: '原因',
      key: 'reasons',
      render: (_: any, record: FieldMappingSuggestion) => {
        if (record.candidates && record.candidates.length > 0) {
          const topCandidate = record.candidates[0];
          return (
            <Space wrap>
              {topCandidate.reasons.map((reason, idx) => (
                <Tag key={idx} color="blue">{reason}</Tag>
              ))}
            </Space>
          );
        }
        return <span>-</span>;
      }
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: FieldMappingSuggestion) => (
        <Space size="middle">
          <Button 
            type="link" 
            size="small"
            onClick={() => showDetailModal(record)}
          >
            详情
          </Button>
          {record.candidates && record.candidates.length > 0 && (
            <Button 
              type="primary" 
              size="small"
              onClick={() => handleConfirmSingle(record, record.candidates[0])}
            >
              确认
            </Button>
          )}
        </Space>
      )
    }
  ];

  // 获取HTTP方法对应的颜色
  const getMethodColor = (method: string) => {
    const colorMap: Record<string, string> = {
      GET: 'blue',
      POST: 'green',
      PUT: 'orange',
      DELETE: 'red',
      PATCH: 'volcano'
    };
    return colorMap[method] || 'default';
  };

  // 初始化
  useEffect(() => {
    if (currentProject?.id && currentVersion?.id) {
      fetchSuggestions();
    }
  }, [currentProject?.id, currentVersion?.id]);

  // 选择行的配置
  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
    getCheckboxProps: (record: FieldMappingSuggestion) => ({
      disabled: !record.candidates || record.candidates.length === 0,
      name: record.api_field_path,
    }),
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title="字段映射建议"
        extra={
          <Space>
            <Button 
              icon={<SyncOutlined />} 
              onClick={fetchSuggestions}
              loading={loading}
            >
              重新生成建议
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => setConfirmModalVisible(true)}
              disabled={selectedRowKeys.length === 0}
            >
              批量确认 ({selectedRowKeys.length})
            </Button>
          </Space>
        }
      >
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Checkbox 
              checked={includePaths} 
              onChange={e => setIncludePaths(e.target.checked)}
            >
              包含路径参数
            </Checkbox>
            <Checkbox 
              checked={includeQuery} 
              onChange={e => setIncludeQuery(e.target.checked)}
            >
              包含查询参数
            </Checkbox>
            <Checkbox 
              checked={includeBody} 
              onChange={e => setIncludeBody(e.target.checked)}
            >
              包含请求体参数
            </Checkbox>
          </Space>
        </div>

        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={suggestions}
          rowKey="definition_id"
          loading={loading}
          pagination={{
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
        />
      </Card>

      {/* 批量确认模态框 */}
      <Modal
        title="批量确认映射"
        open={confirmModalVisible}
        onCancel={() => setConfirmModalVisible(false)}
        onOk={handleBatchConfirm}
        okText="确认应用"
        cancelText="取消"
      >
        <p>您选择了 {selectedRowKeys.length} 个映射建议，确认后将自动创建字段映射关系。</p>
        <p>高置信度（≥{HIGH_CONFIDENCE_THRESHOLD*100}%）的映射将被自动确认。</p>
      </Modal>

      {/* 详情模态框 */}
      <Modal
        title="映射详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={800}
      >
        {selectedSuggestion && (
          <div>
            <Descriptions title="API 信息" bordered column={2} size="small">
              <Descriptions.Item label="方法">
                <Tag color={getMethodColor(selectedSuggestion.definition_method)}>
                  {selectedSuggestion.definition_method}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="路径">{selectedSuggestion.definition_path}</Descriptions.Item>
              <Descriptions.Item label="字段路径">{selectedSuggestion.api_field_path}</Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 24 }}>
              <h3>候选映射列表</h3>
              {selectedSuggestion.candidates && selectedSuggestion.candidates.length > 0 ? (
                <div>
                  {selectedSuggestion.candidates.map((candidate, idx) => (
                    <Card 
                      key={idx} 
                      size="small" 
                      style={{ 
                        marginBottom: 12,
                        borderLeft: candidate.score >= HIGH_CONFIDENCE_THRESHOLD ? '4px solid #52c41a' : 
                                    candidate.score >= MEDIUM_CONFIDENCE_THRESHOLD ? '4px solid #faad14' : '4px solid #ff4d4f'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <strong>{candidate.db_table}.{candidate.db_column}</strong>
                          <div style={{ marginTop: 4 }}>
                            <Tag color={
                              candidate.score >= HIGH_CONFIDENCE_THRESHOLD ? 'success' : 
                              candidate.score >= MEDIUM_CONFIDENCE_THRESHOLD ? 'warning' : 'error'
                            }>
                              置信度: {(candidate.score * 100).toFixed(1)}%
                            </Tag>
                            <Space style={{ marginLeft: 8 }}>
                              {candidate.reasons.map((reason, i) => (
                                <Tag key={i} color="blue">{reason}</Tag>
                              ))}
                            </Space>
                          </div>
                        </div>
                        <Button 
                          type="primary"
                          size="small"
                          onClick={() => handleConfirmSingle(selectedSuggestion, candidate)}
                        >
                          确认此映射
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '24px', color: '#999' }}>
                  没有找到合适的候选映射
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default FieldMappingSuggestions;