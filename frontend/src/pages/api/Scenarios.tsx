/**
 * 场景组装主页面 - 重构后
 * 使用拆分后的子组件，提高代码可维护性
 */
import React, { useState, useEffect } from 'react';
import { Card, Tabs, Modal, Form, Input, Steps, message, Alert } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useProjectStore } from '../../store/project';
import { useScenarioStore } from '../../store/scenario';
import Modules from './Modules';  // [SCENARIO-A-SOLUTION] 使用完整的 Modules 页面
import ScenarioListTab from './scenarios/ScenarioListTab';
import ModuleComposeTab from './scenarios/ModuleComposeTab';
import DependencyGraph from '../../components/DependencyGraph';
import api from '../../services/api';

const { TabPane } = Tabs;
const { Step } = Steps;
const { TextArea } = Input;

const Scenarios: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { currentProject } = useProjectStore();
  const {
    modules,
    dependencies,
    loadDependencies,
    setDependencyGraphVisible,
    dependencyGraphVisible
  } = useScenarioStore();

  const [activeTab, setActiveTab] = useState('modules');

  // 从 URL 参数读取 tab 并设置 activeTab
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && ['modules', 'scenarios', 'compose'].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  // 场景生成相关状态
  const [generateModalVisible, setGenerateModalVisible] = useState(false);
  const [analyzeModalVisible, setAnalyzeModalVisible] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState(0);
  const [analyzeResult, setAnalyzeResult] = useState<any>(null);
  const [graphModalVisible, setGraphModalVisible] = useState(false);
  const [graphData, setGraphData] = useState<any>(null);
  const [selectedChain, setSelectedChain] = useState<number[]>([]);
  const [scenarioName, setScenarioName] = useState('');
  const [pollIntervalId, setPollIntervalId] = useState<NodeJS.Timeout | null>(null);

  // 加载模块间依赖
  useEffect(() => {
    if (currentProject?.id) {
      loadDependencies();
    }
    
    // 清理定时器
    return () => {
      if (pollIntervalId) {
        clearInterval(pollIntervalId);
      }
    };
  }, [currentProject?.id, pollIntervalId]);

  // 分析依赖关系生成场景
  const handleAnalyzeDependencies = async () => {
    if (!currentProject) {
      message.warning('请先选择项目');
      return;
    }

    setAnalyzeModalVisible(true);
    setAnalyzeProgress(0);
    setAnalyzeResult(null);

    try {
      const response = await api.post('/api-integration/scenarios/analyze', {
        project_id: currentProject.id,
        version_id: currentProject.currentVersion?.id || null,
      });

      const taskId = response.data.task_id;
      message.info('依赖分析任务已创建，正在后台执行...');

      // 清理之前的定时器
      if (pollIntervalId) {
        clearInterval(pollIntervalId);
      }

      const newPollInterval = setInterval(async () => {
        try {
          // 验证 taskId 是否有效
          if (!taskId || typeof taskId !== 'number' || taskId <= 0) {
            clearInterval(newPollInterval);
            setPollIntervalId(null);
            message.error('任务ID无效');
            setAnalyzeModalVisible(false);
            return;
          }

          const progressResponse = await api.get(`/api-integration/scenarios/analyze/progress/${taskId}`);
          const progressData = progressResponse.data;
          setAnalyzeProgress(progressData.progress);

          if (progressData.status === 'completed') {
            clearInterval(newPollInterval);
            setPollIntervalId(null);
            setAnalyzeProgress(100);
            setAnalyzeResult(progressData.result);
            message.success('依赖分析完成');
          } else if (progressData.status === 'failed') {
            clearInterval(newPollInterval);
            setPollIntervalId(null);
            message.error(`依赖分析失败: ${progressData.error_message}`);
            setAnalyzeModalVisible(false);
          }
        } catch (error: any) {
          clearInterval(newPollInterval);
          setPollIntervalId(null);
          message.error(error.message || '查询任务进度失败');
          setAnalyzeModalVisible(false);
        }
      }, 1000);

      setPollIntervalId(newPollInterval);

    } catch (error: any) {
      message.error(error.message || '依赖分析失败');
      setAnalyzeModalVisible(false);
    }
  };

  // 生成场景
  const handleGenerateScenario = async () => {
    if (!currentProject) {
      message.warning('请先选择项目');
      return;
    }

    if (!scenarioName.trim()) {
      message.warning('请输入场景名称');
      return;
    }

    if (selectedChain.length < 2) {
      message.warning('请选择至少2个接口的业务链路');
      return;
    }

    try {
      await api.post('/api-integration/scenarios/generate', {
        project_id: currentProject.id,
        chain: selectedChain,
        name: scenarioName,
        description: '自动生成的业务链路测试场景',
      });

      message.success('场景生成成功');
      setGenerateModalVisible(false);
      setScenarioName('');
      setSelectedChain([]);
    } catch (error: any) {
      message.error(error.message || '场景生成失败');
    }
  };

  // 查看依赖图
  const handleViewGraph = async (scenarioId: number) => {
    try {
      const response = await api.get(`/api-integration/scenarios/${scenarioId}/graph`);
      setGraphData(response.data);
      setGraphModalVisible(true);
    } catch (error: any) {
      message.error(error.message || '获取依赖图失败');
    }
  };

  return (
    <div>
      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="模块分析" key="modules">
            {/* [SCENARIO-A-SOLUTION] 使用完整的 Modules 页面替代 ModuleAnalysisTab */}
            <Modules />
          </TabPane>

          <TabPane tab="场景列表" key="scenarios">
            <ScenarioListTab onAnalyzeDependencies={handleAnalyzeDependencies} />
          </TabPane>

          <TabPane tab="跨模块组合" key="compose">
            <ModuleComposeTab modules={modules} />
          </TabPane>
        </Tabs>
      </Card>

      {/* 依赖图弹窗 */}
      <Modal
        title="依赖关系图"
        open={graphModalVisible || dependencyGraphVisible}
        onCancel={() => {
          setGraphModalVisible(false);
          setDependencyGraphVisible(false);
        }}
        footer={null}
        width={1200}
      >
        <DependencyGraph dependencies={dependencies} />
      </Modal>

      {/* 依赖分析进度弹窗 */}
      <Modal
        title="依赖分析"
        open={analyzeModalVisible}
        onCancel={() => {
          setAnalyzeModalVisible(false);
          if (pollIntervalId) {
            clearInterval(pollIntervalId);
            setPollIntervalId(null);
          }
        }}
        footer={null}
        width={600}
      >
        <Steps current={analyzeProgress === 100 ? 2 : analyzeProgress > 0 ? 1 : 0}>
          <Step title="分析中" description="正在分析模块依赖关系" />
          <Step title="生成链路" description="识别业务链路" />
          <Step title="完成" description="分析完成" />
        </Steps>

        <div style={{ marginTop: 32, textAlign: 'center' }}>
          {analyzeProgress < 100 && (
            <div>
              <div style={{ fontSize: 16, marginBottom: 16 }}>
                分析进度: {analyzeProgress}%
              </div>
            </div>
          )}

          {analyzeResult && (
            <Alert
              message="分析完成"
              description={
                <div>
                  <p>共发现 {analyzeResult.chain_count || 0} 条业务链路</p>
                  <p>包含 {analyzeResult.endpoint_count || 0} 个接口</p>
                </div>
              }
              type="success"
              showIcon
            />
          )}
        </div>
      </Modal>

      {/* 生成场景弹窗 */}
      <Modal
        title="生成测试场景"
        open={generateModalVisible}
        onCancel={() => setGenerateModalVisible(false)}
        onOk={handleGenerateScenario}
        width={600}
      >
        <Form layout="vertical">
          <Form.Item label="场景名称" required>
            <Input
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              placeholder="请输入场景名称"
            />
          </Form.Item>
          <Form.Item label="场景描述">
            <TextArea rows={3} placeholder="请输入场景描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Scenarios;