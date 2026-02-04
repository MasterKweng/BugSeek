/**
 * 场景执行详情弹窗组件
 */
import React, { useEffect, useState } from 'react';
import {
  Modal,
  Steps,
  Tag,
  Descriptions,
  Collapse,
  Alert,
  Space,
  Empty
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  MinusCircleOutlined
} from '@ant-design/icons';
import { useScenarioStore } from '../../../store/scenario';

const { Panel } = Collapse;

interface ExecutionDetailModalProps {
  visible: boolean;
  scenarioId: number | null;
  executionId: number | null;
  onClose: () => void;
}

interface ExecutionDetail {
  id: number;
  scenario_id: number;
  scenario_name: string;
  status: string;
  duration_ms: number;
  total_steps: number;
  passed_steps: number;
  failed_steps: number;
  environment_name: string;
  triggered_by: string;
  started_at: string;
  finished_at: string;
  steps: StepResult[];
}

interface StepResult {
  step: number;
  endpoint_id: number;
  endpoint_name: string;
  status: string;
  duration_ms: number;
  response_code: number | null;
  assertions: any;
  variables_used: Record<string, string>;
  extracted_variables: Record<string, string>;
}

const ExecutionDetailModal: React.FC<ExecutionDetailModalProps> = ({
  visible,
  scenarioId,
  executionId,
  onClose
}) => {
  const { loadScenarioExecutionDetail } = useScenarioStore();
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible && scenarioId && executionId) {
      loadDetail();
    }
  }, [visible, scenarioId, executionId]);

  const loadDetail = async () => {
    if (!scenarioId || !executionId) return;

    setLoading(true);
    try {
      const data = await loadScenarioExecutionDetail(scenarioId, executionId);
      if (data) {
        setDetail(data);
      }
    } catch (error) {
      console.error('加载执行详情失败', error);
    } finally {
      setLoading(false);
    }
  };

  const getStepStatus = (status: string) => {
    switch (status) {
      case 'success':
        return 'finish';
      case 'failed':
        return 'error';
      case 'running':
        return 'process';
      default:
        return 'wait';
    }
  };

  const getStepIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'running':
        return <ClockCircleOutlined style={{ color: '#1890ff' }} />;
      default:
        return <MinusCircleOutlined style={{ color: '#d9d9d9' }} />;
    }
  };

  const getAssertionSummary = (assertions: any) => {
    if (!assertions) return null;

    const results = assertions.results || [];
    const passed = results.filter((r: any) => r.passed).length;
    const failed = results.filter((r: any) => !r.passed).length;

    return (
      <Space size={4}>
        <span>断言: {passed}/{results.length}</span>
        {failed > 0 && <Tag color="error">{failed} 失败</Tag>}
      </Space>
    );
  };

  const renderStepDetail = (step: StepResult) => {
    const assertions = step.assertions?.results || [];

    return (
      <div>
        <Descriptions size="small" bordered column={2}>
          <Descriptions.Item label="接口">{step.endpoint_name}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={step.status === 'success' ? 'success' : 'error'}>
              {step.status === 'success' ? '成功' : '失败'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="耗时">{step.duration_ms}ms</Descriptions.Item>
          <Descriptions.Item label="响应码">
            {step.response_code || '-'}
          </Descriptions.Item>
        </Descriptions>

        {Object.keys(step.variables_used).length > 0 && (
          <div style={{ marginTop: 12 }}>
            <strong>使用的变量：</strong>
            <div style={{ marginTop: 4, padding: '8px', background: '#f5f5f5', borderRadius: 4 }}>
              {Object.entries(step.variables_used).map(([key, value]) => (
                <Tag key={key} style={{ margin: 2 }}>
                  {key}: {value}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {Object.keys(step.extracted_variables).length > 0 && (
          <div style={{ marginTop: 12 }}>
            <strong>提取的变量：</strong>
            <div style={{ marginTop: 4, padding: '8px', background: '#f5f5f5', borderRadius: 4 }}>
              {Object.entries(step.extracted_variables).map(([key, value]) => (
                <Tag key={key} color="green" style={{ margin: 2 }}>
                  {key}: {JSON.stringify(value)}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {assertions.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <strong>断言结果：</strong>
            <Collapse ghost style={{ marginTop: 4 }}>
              {assertions.map((assertion: any, index: number) => (
                <Panel
                  header={
                    <Space>
                      {assertion.passed ? (
                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      ) : (
                        <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                      )}
                      <span>{assertion.type}</span>
                    </Space>
                  }
                  key={index}
                >
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="类型">
                      {assertion.type}
                    </Descriptions.Item>
                    <Descriptions.Item label="期望值">
                      {JSON.stringify(assertion.expected)}
                    </Descriptions.Item>
                    <Descriptions.Item label="实际值">
                      {JSON.stringify(assertion.actual)}
                    </Descriptions.Item>
                  </Descriptions>
                </Panel>
              ))}
            </Collapse>
          </div>
        )}
      </div>
    );
  };

  return (
    <Modal
      title={`执行详情 #${executionId}`}
      open={visible}
      onCancel={onClose}
      footer={null}
      width={900}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>
      ) : !detail ? (
        <Empty description="暂无数据" />
      ) : (
        <>
          {/* 执行概览 */}
          <Alert
            message={
              detail.status === 'success' ? '执行成功' : '执行失败'
            }
            description={
              <div>
                <p>总步骤: {detail.total_steps}</p>
                <p>成功: {detail.passed_steps}</p>
                <p>失败: {detail.failed_steps}</p>
                <p>耗时: {(detail.duration_ms / 1000).toFixed(2)}s</p>
              </div>
            }
            type={detail.status === 'success' ? 'success' : 'error'}
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="场景名称">
              {detail.scenario_name}
            </Descriptions.Item>
            <Descriptions.Item label="执行状态">
              {getStepIcon(detail.status)}
              <span style={{ marginLeft: 8 }}>
                {detail.status === 'success' ? '成功' : '失败'}
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="执行环境">
              {detail.environment_name}
            </Descriptions.Item>
            <Descriptions.Item label="触发方式">
              {detail.triggered_by === 'manual' ? '手动' : detail.triggered_by}
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">
              {new Date(detail.started_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            <Descriptions.Item label="结束时间">
              {new Date(detail.finished_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
          </Descriptions>

          {/* 步骤执行详情 */}
          <div style={{ marginTop: 24 }}>
            <h4>步骤执行详情</h4>
            <Collapse
              activeKey={detail.steps.map(s => s.step.toString())}
              items={detail.steps.map(step => ({
                key: step.step.toString(),
                label: (
                  <Space>
                    {getStepIcon(step.status)}
                    <span>Step {step.step}: {step.endpoint_name}</span>
                    <Tag color={step.status === 'success' ? 'success' : 'error'}>
                      {step.duration_ms}ms
                    </Tag>
                    {getAssertionSummary(step.assertions)}
                  </Space>
                ),
                children: renderStepDetail(step)
              }))}
            />
          </div>
        </>
      )}
    </Modal>
  );
};

export default ExecutionDetailModal;