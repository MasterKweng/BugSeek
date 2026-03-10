import React, { useState } from 'react';
import { Card, Input, Button, Steps, Alert, Spin, message } from 'antd';
import { SendOutlined, LoadingOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useProjectStore } from '../../store/project';
import api from '../../services/api';
import './IntentWorkbench.css';

const { TextArea } = Input;
const { Step } = Steps;

const IntentWorkbench: React.FC = () => {
  const navigate = useNavigate();
  const { currentProject, currentVersion } = useProjectStore();
  const [intent, setIntent] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [generatedScenario, setGeneratedScenario] = useState<any>(null);
  const [mappingSuggestions, setMappingSuggestions] = useState<any>(null);

  const handleGenerate = async () => {
    if (!currentProject?.id) {
      message.error('请先选择项目');
      return;
    }
    if (!currentVersion?.id) {
      message.error('请先选择版本');
      return;
    }
    if (!intent.trim()) {
      return;
    }

    setLoading(true);
    setCurrentStep(1);

    try {
      // BSK-SC-022: 调用意图工作台 API
      const response = await api.post('/intent-workbench/generate-scenario', {
        intent_text: intent,
        project_id: currentProject.id,
        version_id: currentVersion.id,
      });

      if (response.code === 0) {
        setCurrentStep(2);
        setGeneratedScenario(response.data.draft);
        
        // BSK-SC-025: 自动触发 JIT 字段映射
        await triggerJITMapping(response.data.draft);
      } else {
        message.error(response.message || '生成场景失败');
        setCurrentStep(0);
      }
    } catch (error: any) {
      console.error('生成场景失败:', error);
      message.error(error.message || '生成场景失败');
      setCurrentStep(0);
    } finally {
      setLoading(false);
    }
  };

  const triggerJITMapping = async (scenario: any) => {
    try {
      // 提取场景中的 definition_ids
      const definitionIds = scenario.nodes?.map((node: any) => node.ref_id).filter((id: any) => id) || [];
      
      if (definitionIds.length === 0) {
        message.warning('场景中没有接口定义，跳过字段映射');
        return;
      }

      // BSK-SC-025: 调用 JIT 字段映射 API
      const mappingResponse = await api.post('/field-mappings/suggest-task', {
        definition_ids: definitionIds,
        scenario_id: scenario.id,
        use_ai: true,
      });

      if (mappingResponse.code === 0) {
        setMappingSuggestions({
          task_id: mappingResponse.data.task_id,
          estimated_duration: mappingResponse.data.estimated_duration,
        });
        message.info(`已启动字段映射任务，预计耗时 ${mappingResponse.data.estimated_duration} 秒`);
      }
    } catch (error: any) {
      console.error('启动字段映射失败:', error);
      // 字段映射失败不影响场景保存
    }
  };

  const handleConfirm = async () => {
    if (!generatedScenario) {
      return;
    }

    try {
      // BSK-SC-022: 调用确认场景 API
      const response = await api.post('/intent-workbench/confirm-scenario', {
        draft: generatedScenario,
      });

      if (response.code === 0) {
        message.success('场景已保存');
        setCurrentStep(0);
        setIntent('');
        setGeneratedScenario(null);
        setMappingSuggestions(null);
        
        // 跳转到场景详情页
        navigate(`/scenario/${response.data.scenario_id}`);
      } else {
        message.error(response.message || '保存场景失败');
      }
    } catch (error: any) {
      console.error('保存场景失败:', error);
      message.error(error.message || '保存场景失败');
    }
  };

  const handleViewMapping = () => {
    if (mappingSuggestions?.task_id) {
      // 跳转到字段映射页面
      navigate(`/version-center/field-mapping?task_id=${mappingSuggestions.task_id}`);
    }
  };

  return (
    <div className="intent-workbench">
      <Card title="意图工作台" className="workbench-card">
        <Alert
          message="AI 驱动的场景生成"
          description="输入自然语言描述，系统将自动识别业务步骤、选择相关 API 并生成可执行场景"
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />

        <Steps current={currentStep} style={{ marginBottom: 32 }}>
          <Step title="输入意图" description="描述测试场景" />
          <Step title="AI 生成" description="智能编排 API" />
          <Step title="确认保存" description="预览并保存" />
        </Steps>

        {currentStep === 0 && (
          <div className="step-content">
            <TextArea
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder="例如：帮我生成一个电商购买链路，包含创建用户、登录、浏览商品、下单、支付，最后校验库存扣减"
              rows={6}
              maxLength={500}
              showCount
            />
            <div className="step-actions">
              <Button
                type="primary"
                icon={loading ? <LoadingOutlined /> : <SendOutlined />}
                onClick={handleGenerate}
                loading={loading}
                disabled={!intent.trim()}
                size="large"
              >
                生成场景
              </Button>
            </div>
          </div>
        )}

        {currentStep === 1 && (
          <div className="step-content">
            <Spin tip="AI 正在生成场景..." spinning={loading}>
              <div style={{ minHeight: 200 }}>
                <p>正在分析意图...</p>
                <p>正在检索相关 API...</p>
                <p>正在生成场景编排...</p>
              </div>
            </Spin>
          </div>
        )}

        {currentStep === 2 && generatedScenario && (
          <div className="step-content">
            <Card title="生成的场景" size="small" style={{ marginBottom: 16 }}>
              <h3>{generatedScenario.name}</h3>
              <p>{generatedScenario.description}</p>
              <h4>场景节点：</h4>
              <ul>
                {generatedScenario.nodes?.map((node: any, index: number) => (
                  <li key={index}>
                    {index + 1}. {node.node_name} ({node.node_type})
                    {node.depends_on && node.depends_on.length > 0 && (
                      <span style={{ marginLeft: 8, color: '#888' }}>
                        依赖: {node.depends_on.join(', ')}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </Card>

            {mappingSuggestions && (
              <Card title="字段映射" size="small" style={{ marginBottom: 16 }}>
                <p>已启动字段映射任务</p>
                <p>任务ID: {mappingSuggestions.task_id}</p>
                <p>预计耗时: {mappingSuggestions.estimated_duration} 秒</p>
                <Button type="link" onClick={handleViewMapping}>
                  查看映射建议
                </Button>
              </Card>
            )}

            <div className="step-actions">
              <Button onClick={() => setCurrentStep(0)}>
                重新生成
              </Button>
              <Button type="primary" icon={<CheckCircleOutlined />} onClick={handleConfirm}>
                确认保存
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default IntentWorkbench;