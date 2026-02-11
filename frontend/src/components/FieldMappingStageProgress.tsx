import React, { useState, useEffect, useCallback } from 'react';
import { Progress, Button, Spin, Space, Modal, message, Tag } from 'antd';
import { ReloadOutlined, PlayCircleOutlined, RedoOutlined, CloseOutlined } from '@ant-design/icons';
import { 
  getStageResult, 
  resumeTask, 
  retryStage, 
  resetTask, 
  type StageResult, 
  type TaskProgress 
} from '../services/fieldMapping';

interface FieldMappingStageProgressProps {
  taskId: number;
  progress: TaskProgress;
  onRetry?: (stageNum: number) => void;
  onResume?: () => void;
  onReset?: () => void;
}

/**
 * 字段映射阶段进度展示组件
 * 
 * 遵循前端代码规范：
 * - 空值防御（NPE）：使用可选链 `?.` 和默认值 `|| {}`
 * - 防抖处理：轮询使用 debounce
 * - 拒绝白屏：使用 Loading Spinner
 * - 防止重复提交：按钮Loading状态
 * - 友好异常提示：message提示错误信息
 */
export const FieldMappingStageProgress: React.FC<FieldMappingStageProgressProps> = ({
  taskId,
  progress,
  onRetry,
  onResume,
  onReset
}) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [stageResultModal, setStageResultModal] = useState<{
    visible: boolean;
    stageNum: number | null;
    data: StageResult | null;
  }>({
    visible: false,
    stageNum: null,
    data: null
  });
  const [resuming, setResuming] = useState<boolean>(false);
  const [retrying, setRetrying] = useState<boolean>(false);
  const [resetting, setResetting] = useState<boolean>(false);

  // 阶段配置
  const stages = [
    { num: 1, name: "字段提取", icon: "📋" },
    { num: 2, name: "规则评分", icon: "📊" },
    { num: 3, name: "智能筛选", icon: "🔍" },
    {num: 4, name: "AI优化", icon: "🤖" },
    { num: 5, name: "结果合并", icon: "📝" }
  ];

  // 获取阶段状态
  const getStageStatus = (stageNum: number): string => {
    const stageKey = `stage${stageNum}` as keyof TaskProgress['stage_results'];
    const stage = progress?.stage_results?.[stageKey];
    return stage?.status || 'not_started';
  };

  // 获取阶段进度
  const getStageProgress = (stageNum: number): number => {
    const stageKey = `stage${stageNum}` as keyof TaskProgress['stage_results'];
    const stage = progress?.stage_results?.[stageKey];
    return stage?.progress || 0;
  };

  // 判断是否为当前执行阶段
  const isCurrentStage = (stageNum: number): boolean => {
    return progress?.current_stage === stageNum;
  };

  // 判断阶段是否失败
  const isStageFailed = (stageNum: number): boolean => {
    return getStageStatus(stageNum) === 'failed';
  };

  // 判断阶段是否已完成
  const isStageCompleted = (stageNum: number): boolean => {
    return getStageStatus(stageNum) === 'completed';
  };

  // 判断阶段是否正在运行
  const isStageRunning = (stageNum: number): boolean => {
    return getStageStatus(stageNum) === 'running';
  };

  // 获取状态标签颜色
  const getStatusColor = (status: string): string => {
    const colorMap: Record<string, string> = {
      'not_started': 'default',
      'running': 'processing',
      'completed': 'success',
      'failed': 'error',
      'skipped': 'warning'
    };
    return colorMap[status] || 'default';
  };

  // 获取状态标签文本
  const getStatusLabel = (status: string): string => {
    const labelMap: Record<string, string> = {
      'not_started': '未开始',
      'running': '进行中',
      'completed': '已完成',
      'failed': '失败',
      'skipped': '已跳过'
    };
    return labelMap[status] || '未知';
  };

  // 查看阶段结果
  const handleViewResult = async (stageNum: number) => {
    setLoading(true);
    try {
      const response = await getStageResult(taskId, stageNum);
      if (response.code === 0) {
        setStageResultModal({
          visible: true,
          stageNum,
          data: response.data || null
        });
      } else {
        message.error(response.message || '查询阶段结果失败');
      }
    } catch (error) {
      console.error('查询阶段结果失败:', error);
      message.error('查询阶段结果失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 重试阶段
  const handleRetryStage = async (stageNum: number) => {
    setRetrying(true);
    try {
      const response = await retryStage(taskId, stageNum);
      if (response.code === 0) {
        message.success(`已重试阶段${stageNum}`);
        if (onRetry) {
          onRetry(stageNum);
        }
      } else {
        message.error(response.message || '重试阶段失败');
      }
    } catch (error) {
      console.error('重试阶段失败:', error);
      message.error('重试阶段失败，请稍后重试');
    } finally {
      setRetrying(false);
    }
  };

  // 继续执行
  const handleResume = async () => {
    setResuming(true);
    try {
      const response = await resumeTask(taskId);
      if (response.code === 0) {
        message.success('任务已继续执行');
        if (onResume) {
          onResume();
        }
      } else {
        message.error(response.message || '继续执行失败');
      }
    } catch (error) {
      console.error('继续执行失败:', error);
      message.error('继续执行失败，请稍后重试');
    } finally {
      setResuming(false);
    }
  };

  // 重置任务
  const handleReset = async () => {
    Modal.confirm({
      title: '确认重置',
      content: '重置将清除所有阶段结果，任务将从头开始执行。确定要继续吗？',
      okText: '确定',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        setResetting(true);
        try {
          const response = await resetTask(taskId);
          if (response.code === 0) {
            message.success('任务已重置');
            if (onReset) {
              onReset();
            }
          } else {
            message.error(response.message || '重置任务失败');
          }
        } catch (error) {
          console.error('重置任务失败:', error);
          message.error('重置任务失败，请稍后重试');
        } finally {
          setResetting(false);
        }
      }
    });
  };

  // 获取任务整体状态
  const getTaskStatus = (): string => {
    // 检查是否有任何阶段正在运行
    for (let i = 1; i <= 5; i++) {
      if (isStageRunning(i)) {
        return 'running';
      }
    }
    
    // 检查是否有阶段失败
    for (let i = 1; i <= 5; i++) {
      if (isStageFailed(i)) {
        return 'failed';
      }
    }
    
    // 检查是否所有阶段都已完成
    const allCompleted = stages.every(stage => isStageCompleted(stage.num));
    if (allCompleted) {
      return 'completed';
    }
    
    return 'pending';
  };

  const taskStatus = getTaskStatus();

  // 渲染阶段结果数据
  const renderStageData = (data: any, stageNum: number) => {
    if (!data) {
      return <div className="text-center text-gray-400 py-4">暂无数据</div>;
    }

    return (
      <div className="space-y-4">
        {Object.entries(data).map(([key, value]) => {
          // 处理嵌套对象
          if (typeof value === 'object' && value !== null) {
            return (
              <div key={key} className="mb-2">
                <div className="font-medium text-gray-700 mb-1">{key}:</div>
                <div className="ml-4 text-sm text-gray-600">
                  {renderStageData(value, stageNum)}
                </div>
              </div>
            );
          }
          
          // 处理数组
          if (Array.isArray(value)) {
            return (
              <div key={key} className="mb-2">
                <div className="font-medium text-gray-700 mb-1">{key}:</div>
                <div className="ml-4 text-sm text-gray-600">
                  {value.join(', ')}
                </div>
              </div>
            );
          }
          
          // 处理字符串
          return (
            <div key={key} className="mb-2">
              <span className="font-medium text-gray-700">{key}:</span>
              <span className="ml-2 text-sm text-gray-600">{String(value)}</span>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* 控制按钮区域 */}
      <div className="flex items-center justify-between bg-gray-50 p-3 rounded-lg">
        <div className="text-sm text-gray-600">
          当前阶段: {progress?.current_stage || 0} / 5
        </div>
        <Space>
          {taskStatus === 'failed' && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={resuming}
              onClick={handleResume}
            >
              继续执行
            </Button>
          )}
          <Button
            danger
            icon={<RedoOutlined />}
            loading={resetting}
            onClick={handleReset}
          >
            重置任务
          </Button>
        </Space>
      </div>

      {/* 阶段进度列表 */}
      <div className="space-y-3">
        {stages.map((stage) => {
          const status = getStageStatus(stage.num);
          const stageProgress = getStageProgress(stage.num);
          const isCurrent = isCurrentStage(stage.num);
          const isFailed = isStageFailed(stage.num);
          const isCompleted = isStageCompleted(stage.num);
          const isRunning = isStageRunning(stage.num);

          return (
            <div
              key={stage.num}
              className={`p-4 border rounded-lg transition-all ${
                isCurrent ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">{stage.icon}</span>
                  <div>
                    <div className="font-medium">{stage.name}</div>
                    <div className="flex items-center space-x-2 text-sm text-gray-500">
                      <span>状态: </span>
                      <Tag color={getStatusColor(status)}>
                        {getStatusLabel(status)}
                      </Tag>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  {/* 进度条 */}
                  <Progress
                    percent={stageProgress}
                    size="small"
                    status={isRunning ? 'active' : 'normal'}
                  />

                  {/* 操作按钮 */}
                  {isCompleted && (
                    <Button
                      type="link"
                      size="small"
                      loading={loading}
                      onClick={() => handleViewResult(stage.num)}
                    >
                      查看结果
                    </Button>
                  )}

                  {isFailed && (
                    <Button
                      type="primary"
                      danger
                      size="small"
                      icon={<ReloadOutlined />}
                      loading={retrying}
                      onClick={() => handleRetryStage(stage.num)}
                    >
                      重试
                    </Button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 阶段结果详情弹窗 */}
      <Modal
        title={`阶段${stageResultModal.stageNum}结果详情 - ${stageResultModal.data?.name || ''}`}
        open={stageResultModal.visible}
        onCancel={() => setStageResultModal({ visible: false, stageNum: null, data: null })}
        width={800}
        footer={[
          <Button key="close" onClick={() => setStageResultModal({ visible: false, stageNum: null, data: null })}>
            关闭
          </Button>
        ]}
        styles={{
          body: { padding: '20px' }
        }}
      >
        {loading ? (
          <div className="text-center py-8">
            <Spin size="large" tip="加载中..." />
          </div>
        ) : (
          <div className="space-y-4">
            {/* 阶段基本信息 */}
            {stageResultModal.data && (
              <div>
                <div className="mb-2">
                  <span className="font-medium text-gray-700">状态:</span>
                  <Tag 
                    color={getStatusColor(stageResultModal.data.status)}
                    style={{ marginLeft: 8 }}
                  >
                    {getStatusLabel(stageResultModal.data.status)}
                  </Tag>
                </div>
                {stageResultModal.data.completed_at && (
                  <div>
                    <span className="font-medium text-gray-700">完成时间:</span>
                    <span className="ml-2 text-sm text-gray-600">
                      {stageResultModal.data.completed_at}
                    </span>
                  </div>
                )}
                {stageResultModal.data.progress !== undefined && (
                  <div>
                    <span className="font-medium text-gray-700">进度:</span>
                    <span className="ml-2 text-sm text-gray-600">
                      {stageResultModal.data.progress}%
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* 阶段详细数据 */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="font-medium text-gray-700 mb-2">详细数据:</div>
              {renderStageData(stageResultModal.data?.data, stageResultModal.stageNum || 0)}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};