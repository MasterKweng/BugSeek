import React, { useEffect, useState } from 'react';
import { Button, Card, message, Space, Spin, Table, Tag } from 'antd';
import { ArrowLeftOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';

import api from '../../services/api';
import './ScenarioFieldMapping.css';

interface MappingCandidate {
  db_table: string;
  db_column: string;
  score: number;
}

interface MappingSuggestion {
  id: number;
  definition_id: number;
  definition_method?: string;
  definition_path?: string;
  api_field_path: string;
  status?: string;
  candidates: MappingCandidate[];
}

interface ScenarioNode {
  ref_id: number;
  input_mapping?: Record<string, string>;
}

interface ScenarioDetail {
  name: string;
  description?: string;
  nodes?: ScenarioNode[];
}

interface AcceptedMapping {
  suggestion_id: number;
  definition_id: number;
  api_field_path: string;
  db_table?: string;
  db_column?: string;
}

const ScenarioFieldMapping: React.FC = () => {
  const navigate = useNavigate();
  const { scenarioId } = useParams();
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null);
  const [suggestions, setSuggestions] = useState<MappingSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  useEffect(() => {
    void loadScenario();
    void loadSuggestions();
  }, [scenarioId]);

  const loadScenario = async () => {
    if (!scenarioId) {
      return;
    }

    try {
      const response = await api.get(`/scenarios/${scenarioId}`);
      if (response.code === 0) {
        setScenario(response.data);
      }
    } catch (error) {
      console.error('加载场景失败:', error);
    }
  };

  const loadSuggestions = async () => {
    setLoading(true);
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const taskId = urlParams.get('task_id');
      if (!taskId) {
        message.warning('未找到映射任务 ID');
        return;
      }

      const response = await api.get(`/field-mappings/suggestions?task_id=${taskId}`);
      if (response.code === 0) {
        setSuggestions(response.data.items || []);
      }
    } catch (error: any) {
      console.error('加载映射建议失败:', error);
      message.error(error.message || '加载映射建议失败');
    } finally {
      setLoading(false);
    }
  };

  const applyMappingToScenario = async (items: AcceptedMapping[]) => {
    if (!scenario || !scenarioId) {
      return;
    }

    try {
      const updatedNodes = (scenario.nodes || []).map((node) => {
        const nodeMappings = items.filter((item) => item.definition_id === node.ref_id);
        if (nodeMappings.length === 0) {
          return node;
        }

        const inputMapping = { ...(node.input_mapping || {}) };
        nodeMappings.forEach((mapping) => {
          if (!mapping.db_table || !mapping.db_column) {
            return;
          }
          const fieldPath = mapping.api_field_path.replace(/^body\./, '');
          inputMapping[fieldPath] = `{{${mapping.db_table}_${mapping.db_column}}}`;
        });

        return { ...node, input_mapping: inputMapping };
      });

      const response = await api.put(`/scenarios/${scenarioId}`, {
        name: scenario.name,
        description: scenario.description,
        nodes: updatedNodes,
      });

      if (response.code === 0) {
        message.success('映射已应用到场景节点');
        setScenario({ ...scenario, nodes: updatedNodes });
      }
    } catch (error) {
      console.error('应用映射到场景失败:', error);
      message.warning('映射已确认，但应用到场景失败，请手动配置');
    }
  };

  const handleConfirm = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请至少选择一个映射建议');
      return;
    }

    setConfirming(true);
    try {
      const items: AcceptedMapping[] = selectedRowKeys
        .map((key) => suggestions.find((item) => item.id === key))
        .filter((item): item is MappingSuggestion => Boolean(item))
        .map((item) => ({
          suggestion_id: item.id,
          definition_id: item.definition_id,
          api_field_path: item.api_field_path,
          db_table: item.candidates[0]?.db_table,
          db_column: item.candidates[0]?.db_column,
        }));

      const response = await api.post('/field-mappings/suggestions/accept', { items });
      if (response.code === 0) {
        message.success(`成功确认 ${items.length} 个映射建议`);
        await applyMappingToScenario(items);
      } else {
        message.error(response.message || '确认映射失败');
      }
    } catch (error: any) {
      console.error('确认映射失败:', error);
      message.error(error.message || '确认映射失败');
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="scenario-field-mapping">
      <Card
        title="场景字段映射确认"
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/scenario/${scenarioId}`)}>
              返回场景
            </Button>
            <Button
              type="primary"
              onClick={handleConfirm}
              loading={confirming}
              disabled={selectedRowKeys.length === 0}
            >
              确认并应用 ({selectedRowKeys.length})
            </Button>
          </Space>
        }
      >
        {scenario && (
          <div className="workspace-inline-note">
            {`场景: ${scenario.name}，包含 ${scenario.nodes?.length || 0} 个节点和 ${suggestions.length} 个字段映射建议。`}
          </div>
        )}

        <Spin spinning={loading}>
          <Table<MappingSuggestion>
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys),
            }}
            columns={[
              {
                title: '接口字段',
                dataIndex: 'api_field_path',
                key: 'api_field_path',
                render: (text: string, record) => (
                  <div>
                    <div>{record.definition_method} {record.definition_path}</div>
                    <div style={{ color: '#666', fontSize: 12 }}>{text}</div>
                  </div>
                ),
              },
              {
                title: '推荐映射',
                dataIndex: 'candidates',
                key: 'candidates',
                render: (candidates: MappingCandidate[]) => (
                  <div>
                    {candidates?.slice(0, 3).map((candidate, index) => (
                      <div key={index} style={{ marginBottom: 4 }}>
                        <Tag color="blue">{candidate.db_table}.{candidate.db_column}</Tag>
                        <span style={{ marginLeft: 8, color: '#999' }}>
                          置信度: {(candidate.score * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                ),
              },
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                render: (status?: string) => (
                  <Tag color={status === 'accepted' ? 'success' : 'default'}>
                    {status === 'accepted' ? '已接受' : '待审核'}
                  </Tag>
                ),
              },
              {
                title: '操作',
                key: 'actions',
                render: (_, record) => {
                  const checked = selectedRowKeys.includes(record.id);
                  return (
                    <Space size="small">
                      <Button
                        type="link"
                        size="small"
                        icon={<CheckOutlined />}
                        onClick={() => setSelectedRowKeys(Array.from(new Set([...selectedRowKeys, record.id])))}
                      >
                        选择
                      </Button>
                      <Button
                        type="link"
                        size="small"
                        danger
                        icon={<CloseOutlined />}
                        onClick={() => setSelectedRowKeys(selectedRowKeys.filter((key) => key !== record.id))}
                        disabled={!checked}
                      >
                        取消
                      </Button>
                    </Space>
                  );
                },
              },
            ]}
            dataSource={suggestions}
            rowKey="id"
            pagination={{
              pageSize: 20,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条`,
            }}
          />
        </Spin>
      </Card>
    </div>
  );
};

export default ScenarioFieldMapping;

