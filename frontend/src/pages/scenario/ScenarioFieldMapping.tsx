import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Space, Modal, message, Spin, Alert } from 'antd';
import { CheckOutlined, CloseOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../services/api';
import './ScenarioFieldMapping.css';

const ScenarioFieldMapping: React.FC = () => {
  const navigate = useNavigate();
  const { scenarioId } = useParams();
  const [scenario, setScenario] = useState<any>(null);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  useEffect(() => {
    loadScenario();
    loadSuggestions();
  }, [scenarioId]);

  const loadScenario = async () => {
    if (!scenarioId) return;
    
    try {
      const response = await api.get(`/scenarios/${scenarioId}`);
      if (response.code === 0) {
        setScenario(response.data);
      }
    } catch (error: any) {
      console.error('加载场景失败:', error);
    }
  };

  const loadSuggestions = async () => {
    setLoading(true);
    try {
      // BSK-SC-025: 从 URL 获取 task_id
      const urlParams = new URLSearchParams(window.location.search);
      const taskId = urlParams.get('task_id');
      
      if (!taskId) {
        message.warning('未找到映射任务ID');
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

  const handleConfirm = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请至少选择一个映射建议');
      return;
    }

    setConfirming(true);
    try {
      // BSK-SC-025: 批量确认映射建议
      const items = selectedRowKeys.map((key: any) => {
        const suggestion = suggestions.find((s: any) => s.id === key);
        return {
          suggestion_id: suggestion.id,
          definition_id: suggestion.definition_id,
          api_field_path: suggestion.api_field_path,
          db_table: suggestion.candidates[0]?.db_table,
          db_column: suggestion.candidates[0]?.db_column,
        };
      });

      const response = await api.post('/field-mappings/suggestions/accept', {
        items: items,
      });

      if (response.code === 0) {
        message.success(`成功确认 ${items.length} 个映射建议`);
        
        // BSK-SC-025: 回写场景节点映射
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

  const applyMappingToScenario = async (items: any[]) => {
    if (!scenario) return;

    try {
      // 将映射应用到场景节点的 input_mapping
      const updatedNodes = (scenario.nodes || []).map((node: any) => {
        const nodeMappings = items.filter((item: any) => item.definition_id === node.ref_id);
        
        if (nodeMappings.length > 0) {
          const inputMapping = { ...node.input_mapping } || {};
          
          nodeMappings.forEach((mapping: any) => {
            // 简单的逻辑：将数据库字段映射到接口字段
            const fieldPath = mapping.api_field_path.replace(/^body\./, '');
            inputMapping[fieldPath] = `{{${mapping.db_table}_${mapping.db_column}}}`;
          });
          
          return { ...node, input_mapping };
        }
        
        return node;
      });

      // 保存更新后的场景
      const response = await api.put(`/scenarios/${scenarioId}`, {
        name: scenario.name,
        description: scenario.description,
        nodes: updatedNodes,
      });

      if (response.code === 0) {
        message.success('映射已应用到场景节点');
        setScenario({ ...scenario, nodes: updatedNodes });
      }
    } catch (error: any) {
      console.error('应用映射到场景失败:', error);
      message.warning('映射已确认，但应用到场景失败，请手动配置');
    }
  };

  const columns = [
    {
      title: '接口字段',
      dataIndex: 'api_field_path',
      key: 'api_field_path',
      render: (text: string, record: any) => (
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
      render: (candidates: any[]) => (
        <div>
          {candidates?.slice(0, 3).map((c: any, i: number) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <Tag color="blue">{c.db_table}.{c.db_column}</Tag>
              <span style={{ marginLeft: 8, color: '#999' }}>
                置信度: {(c.score * 100).toFixed(1)}%
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
      render: (status: string) => (
        <Tag color={status === 'accepted' ? 'success' : 'default'}>
          {status === 'accepted' ? '已接受' : '待审核'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: any) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<CheckOutlined />}
            onClick={() => setSelectedRowKeys([...selectedRowKeys, record.id])}
          >
            选择
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<CloseOutlined />}
            onClick={() => setSelectedRowKeys(selectedRowKeys.filter(k => k !== record.id))}
          >
            取消
          </Button>
        </Space>
      ),
    },
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
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
          <Alert
            message={`场景: ${scenario.name}`}
            description={`包含 ${scenario.nodes?.length || 0} 个节点，${suggestions.length} 个字段映射建议`}
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Spin spinning={loading}>
          <Table
            rowSelection={rowSelection}
            columns={columns}
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