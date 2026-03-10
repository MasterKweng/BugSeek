import React, { useState, useEffect } from 'react';
import { Card, Button, Space, Timeline, Tag, Progress, Alert, Spin } from 'antd';
import { ArrowLeftOutlined, RedoOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useProjectStore } from '../../store/project';
import api from '../../services/api';
import './ScenarioExecution.css';

const ScenarioExecution: React.FC = () => {
  const navigate = useNavigate();
  const { scenarioId, executionId } = useParams();
  const { selectedEnvironmentId } = useProjectStore();
  const [loading, setLoading] = useState(false);
  const [execution, setExecution] = useState<any>(null);
  const [scenario, setScenario] = useState<any>(null);

  useEffect(() => {
    loadExecution();
    loadScenario();
  }, [scenarioId, executionId]);

  const loadExecution = async () => {
    if (!scenarioId || !executionId) return;
    
    setLoading(true);
    try {
      const response = await api.get(`/scenarios/${scenarioId}/executions/${executionId}`);
      if (response.code === 0) {
        setExecution(response.data);
      }
    } catch (error: any) {
      console.error('加载执行详情失败:', error);
    } finally {
      setLoading(false);
    }
  };

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

  const handleRetry = async () => {
    if (!scenarioId || !selectedEnvironmentId) {
      alert('请先选择环境');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post(`/scenarios/${scenarioId}/execute`, {
        environment_id: selectedEnvironmentId,
      });

      if (response.code === 0) {
        alert('场景已重新执行');
        navigate(`/scenario/${scenarioId}/execution/${response.data.execution_id}`);
      }
    } catch (error: any) {
      console.error('重新执行失败:', error);
      alert('重新执行失败');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !execution) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  const successCount = execution?.results?.filter((r: any) => r.status === 'passed').length || 0;
  const failedCount = execution?.results?.filter((r: any) => r.status === 'failed').length || 0;
  const totalCount = execution?.results?.length || 0;
  const passRate = totalCount > 0 ? (successCount / totalCount) * 100 : 0;

  return (
    <div className="scenario-execution">
      <Space style={{ marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/scenario/${scenarioId}`)}>
          返回场景
        </Button>
        <Button icon={<RedoOutlined />} onClick={handleRetry} loading={loading}>
          重新执行
        </Button>
      </Space>

      <Card title="场景执行详情">
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <h3>执行概览</h3>
            <Space size="large" wrap>
              <span>场景: {scenario?.name}</span>
              <span>执行ID: {executionId}</span>
              <Tag color={execution?.status === 'completed' ? 'success' : 'processing'}>
                {execution?.status === 'completed' ? '已完成' : '执行中'}
              </Tag>
            </Space>
            <div style={{ marginTop: 16 }}>
              <Progress
                percent={Math.round(passRate)}
                status={failedCount > 0 ? 'exception' : 'success'}
                format={(percent) => `${successCount}/${totalCount} 通过`}
              />
            </div>
            {execution?.summary && (
              <div style={{ marginTop: 8 }}>
                <Space>
                  <span>总耗时: {execution.summary.duration_ms}ms</span>
                  <span>成功: {execution.summary.passed}</span>
                  <span>失败: {execution.summary.failed}</span>
                  <span>跳过: {execution.summary.skipped}</span>
                </Space>
              </div>
            )}
          </div>

          <div>
            <h3>执行时间线</h3>
            <Timeline
              items={execution?.results?.map((result: any, index: number) => {
                const node = scenario?.nodes?.find((n: any) => n.node_key === result.node_key);
                return {
                  color: result.status === 'passed' ? 'green' : 'red',
                  children: (
                    <div className="execution-item">
                      <div className="execution-item-header">
                        <Space>
                          <Tag color={result.status === 'passed' ? 'success' : 'error'}>
                            {result.status === 'passed' ? '成功' : '失败'}
                          </Tag>
                          <strong>{node?.node_name || result.node_key}</strong>
                          {node && (
                            <Tag>{node.node_type}</Tag>
                          )}
                        </Space>
                        <span>耗时: {result.response_time}ms</span>
                      </div>
                      <div className="execution-item-details">
                        {result.request_body && (
                          <div>
                            <strong>请求:</strong>
                            <pre>{JSON.stringify(result.request_body, null, 2)}</pre>
                          </div>
                        )}
                        {result.response_body && (
                          <div>
                            <strong>响应:</strong>
                            <pre>{JSON.stringify(result.response_body, null, 2)}</pre>
                          </div>
                        )}
                        {result.assertion_results && (
                          <div>
                            <strong>断言:</strong>
                            <pre>{JSON.stringify(result.assertion_results, null, 2)}</pre>
                          </div>
                        )}
                        {result.extracted_variables && Object.keys(result.extracted_variables).length > 0 && (
                          <div>
                            <strong>提取变量:</strong>
                            <pre>{JSON.stringify(result.extracted_variables, null, 2)}</pre>
                          </div>
                        )}
                        {result.error_message && (
                          <Alert
                            message="错误信息"
                            description={result.error_message}
                            type="error"
                            showIcon
                            style={{ marginTop: 8 }}
                          />
                        )}
                      </div>
                    </div>
                  ),
                };
              })}
            />
          </div>
        </Space>
      </Card>
    </div>
  );
};

export default ScenarioExecution;