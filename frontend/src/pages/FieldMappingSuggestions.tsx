import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  message,
  Spin,
  Descriptions,
  Badge,
  Checkbox,
  Drawer,
  Progress,
  Steps,
  Statistic,
  Row,
  Col,
  Switch,
  Form,
  Alert,
  List,
  Empty,
  Result,
  Divider,
  Slider,
  Select,
  Tabs,
  Popconfirm,
  Input
} from 'antd';
import { 
  CheckCircleOutlined, 
  PlayCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined
} from '@ant-design/icons';
import { useProjectStore } from '../store/project';
import * as fieldMappingService from '../services/fieldMapping';
import { getDbSchemas } from '../services/dbSchema';
import type { 
  FieldMappingSuggestion, 
  FieldMappingCandidate,
  FieldMappingBatchApplyItem,
  AsyncTask,
  AsyncTaskCreateRequest,
  PageState
} from '../services/fieldMapping';
import { FieldMappingStageProgress } from '../components/FieldMappingStageProgress';

const FieldMappingSuggestions: React.FC = () => {
  const { currentProject, currentVersion } = useProjectStore();
  
  // ==================== 页面状态管理（简化版 - 仅用于历史任务记录） ====================
  const [pageState, setPageState] = useState<PageState>('IDLE');
  const [taskId, setTaskId] = useState<number | null>(null);
  const [currentTask, setCurrentTask] = useState<AsyncTask | null>(null);
  
  // ==================== 原有状态 ====================
  const [suggestions, setSuggestions] = useState<FieldMappingSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [selectedCandidates] = useState<Record<number, FieldMappingCandidate | null>>({});
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedSuggestion, setSelectedSuggestion] = useState<FieldMappingSuggestion | null>(null);
  const [includePaths, setIncludePaths] = useState(true);
  const [includeQuery, setIncludeQuery] = useState(true);
  const [includeBody, setIncludeBody] = useState(true);
  
  // ==================== 新增：分页状态 ====================
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0
  });
  
  // ==================== 新增：Tab 切换状态 ====================
  const [activeTab, setActiveTab] = useState<'suggestions' | 'mappings'>('suggestions');
  
  // ==================== 新增：映射管理状态 ====================
  const [mappings, setMappings] = useState<fieldMappingService.FieldMappingWithDetails[]>([]);
  const [mappingsLoading, setMappingsLoading] = useState(false);
  const [mappingsPagination, setMappingsPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0
  });
  const [mappingFilter, setMappingFilter] = useState<'all' | 'proposed' | 'confirmed' | 'rejected'>('all');

  const filteredMappings = useMemo(() => {
    if (mappingFilter === 'all') {
      return mappings;
    }
    return mappings.filter(mapping => mapping.status === mappingFilter);
  }, [mappings, mappingFilter]);
  
  // ==================== 新增：映射管理函数 ====================
  const fetchMappings = useCallback(async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }
    
    setMappingsLoading(true);
    try {
      const response = await fieldMappingService.getFieldMappings({
        project_id: currentProject.id,
        version_id: currentVersion.id
      });
      
      if (response.code === 0 && response.data) {
        setMappings(response.data.items || []);
        setMappingsPagination({
          current: 1,
          pageSize: 20,
          total: response.data.total || 0
        });
      }
    } catch (error: any) {
      console.error('获取映射失败:', error);
      message.error(error.message || '获取映射失败');
    } finally {
      setMappingsLoading(false);
    }
  }, [currentProject?.id, currentVersion?.id]);
  
  const handleDeleteMapping = async (mappingId: number) => {
    try {
      const response = await fieldMappingService.deleteFieldMapping(mappingId, {
        project_id: currentProject.id,
        version_id: currentVersion.id
      });
      
      if (response.code === 0) {
        message.success('删除成功');
        fetchMappings();
      } else {
        message.error(response.message || '删除失败');
      }
    } catch (error: any) {
      console.error('删除映射失败:', error);
      message.error(error.message || '删除失败');
    }
  };
  
  const handleUpdateMappingStatus = async (mappingId: number, status: string) => {
    try {
      const response = await fieldMappingService.updateFieldMappingStatus(mappingId, status, {
        project_id: currentProject.id,
        version_id: currentVersion.id
      });
      
      if (response.code === 0) {
        message.success('状态更新成功');
        fetchMappings();
      } else {
        message.error(response.message || '状态更新失败');
      }
    } catch (error: any) {
      console.error('状态更新失败:', error);
      message.error(error.message || '状态更新失败');
    }
  };
  
  // ==================== 异步任务相关状态 ====================
  const [taskModalVisible, setTaskModalVisible] = useState(false);
  const [progressModalVisible, setProgressModalVisible] = useState(false);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  const [useAi] = useState(true);
  const [aiHighPriority] = useState(true);
  const [aiMediumPriority] = useState(true);
  const [aiLowPriority] = useState(false);
  
  // ==================== 轮询优化相关状态 ====================
  const [isPageVisible, setIsPageVisible] = useState(true);
  const [pollingStartTime, setPollingStartTime] = useState<number>(Date.now());
  const POLLING_TIMEOUT = 60 * 60 * 1000; // 1小时超时
  const pollingFailCount = React.useRef(0);
  
  // ==================== 历史记录相关状态 ====================
  const [historyDrawerVisible, setHistoryDrawerVisible] = useState(false);
  const [historyList, setHistoryList] = useState<fieldMappingService.AsyncTaskSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(20);
  const [expandedTaskId, setExpandedTaskId] = useState<number | null>(null);
  const [expandedTaskDetail, setExpandedTaskDetail] = useState<AsyncTask | null>(null);
  const [expandedTaskSuggestions, setExpandedTaskSuggestions] = useState<FieldMappingSuggestion[]>([]);
  
  // ==================== 数据结构状态 ====================
  const [schemaList, setSchemaList] = useState<any[]>([]);
  
  // ==================== 新增：算法配置状态 ====================
  const [useAiFallback, setUseAiFallback] = useState(true);  // 是否启用 AI 兜底
  const [aiConfidenceThreshold, setAiConfidenceThreshold] = useState(0.7);  // AI 触发阈值
  
  // ==================== 新增：筛选器状态 ====================
  const [typeFilter, setTypeFilter] = useState<'all' | 'manual' | 'auto'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'proposed' | 'confirmed' | 'rejected'>('all');
  
  // 新增：置信度筛选
  const [confidenceFilter, setConfidenceFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  
  // 新增：API方法筛选
  const [methodFilter, setMethodFilter] = useState<'all' | 'POST' | 'GET' | 'PUT' | 'DELETE' | 'PATCH'>('all');
  
  // 新增：字段类型筛选
  const [fieldTypeFilter, setFieldTypeFilter] = useState<'all' | 'path' | 'query' | 'body'>('all');
  
  // 新增：搜索关键词
  const [searchKeyword, setSearchKeyword] = useState('');
  
  // 高置信度阈值
  const HIGH_CONFIDENCE_THRESHOLD = 0.85;
  // 中等置信度阈值
  const MEDIUM_CONFIDENCE_THRESHOLD = 0.60;

  // 获取数据结构列表
  const fetchSchemas = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      setSchemaList([]);
      return;
    }
    try {
      const res = await getDbSchemas({
        project_id: currentProject.id,
        version_id: currentVersion.id
      });
      setSchemaList(res.data?.items || []);
    } catch (error: any) {
      console.error('获取数据结构失败:', error);
      setSchemaList([]);
    }
  };

  // 初始化时获取数据结构列表
  useEffect(() => {
    if (currentProject?.id && currentVersion?.id) {
      fetchSchemas();
    }
  }, [currentProject?.id, currentVersion?.id]);

  // 初始化时自动加载最近完成的任务建议
  useEffect(() => {
    if (currentProject?.id && currentVersion?.id && !taskId && pageState === 'IDLE') {
      fetchLatestCompletedTask();
    }
  }, [currentProject?.id, currentVersion?.id, taskId, pageState]);

  useEffect(() => {
    if (currentProject?.id && currentVersion?.id) {
      fetchMappings();
    }
  }, [currentProject?.id, currentVersion?.id, fetchMappings]);

  useEffect(() => {
    if (activeTab === 'mappings' && currentProject?.id && currentVersion?.id) {
      fetchMappings();
    }
  }, [activeTab, currentProject?.id, currentVersion?.id, fetchMappings]);

  // ==================== 页面可见性监听 ====================
  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsPageVisible(!document.hidden);
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // ==================== 智能轮询逻辑 ====================
  useEffect(() => {
    // 只有在 RUNNING 状态且有 taskId 时才轮询
    if (pageState !== 'RUNNING' || !taskId || !isPageVisible) {
      return;
    }

    // 检查轮询超时
    if (Date.now() - pollingStartTime > POLLING_TIMEOUT) {
      message.warning('轮询超时，请手动刷新页面');
      stopPolling();
      return;
    }

    // 根据页面可见性调整轮询频率
    const interval = isPageVisible ? 3000 : 30000;

    const poll = async () => {
      try {
        const response = await fieldMappingService.getAsyncTask(taskId);
        const task = response.data;

        // 空值防御
        if (!task) {
          console.error('获取任务失败：返回数据为空');
          return;
        }

        // 更新任务状态
        setCurrentTask(task);

        // 根据任务状态决定下一步
        if (task.status === 'completed') {
          setPageState('COMPLETED');
          loadTaskResults(taskId);
          stopPolling();
        } else if (task.status === 'failed') {
          setPageState('FAILED');
          stopPolling();
        } else if (task.status === 'cancelled') {
          setPageState('IDLE');
          stopPolling();
        }
        // running 状态继续轮询
      } catch (error: any) {
        console.error('轮询任务失败:', error);
        pollingFailCount.current += 1;
        
        // 连续失败3次后停止轮询
        if (pollingFailCount.current >= 3) {
          message.error('获取任务状态失败，请手动刷新');
          stopPolling();
        }
      }
    };

    const intervalId = setInterval(poll, interval);
    setPollingInterval(intervalId);

    return () => clearInterval(intervalId);
  }, [taskId, pageState, isPageVisible]);

  // ==================== 工具函数 ====================
  
  /**
   * 开始轮询
   */
  const startPolling = (newTaskId: number) => {
    setTaskId(newTaskId);
    setPageState('RUNNING');
    setPollingStartTime(Date.now());
    setProgressModalVisible(false); // 关闭旧的 Modal，使用页面态渲染
  };

  /**
   * 停止轮询
   */
  const stopPolling = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
  };

  /**
   * 刷新任务状态
   */
  const handleRefreshTask = async () => {
    if (!taskId) {
      return;
    }

    try {
      const response = await fieldMappingService.getAsyncTask(taskId);
      if (response.code === 0 && response.data) {
        setCurrentTask(response.data);
        message.success('状态已刷新');
      }
    } catch (error: any) {
      console.error('刷新任务失败:', error);
      message.error('刷新失败');
    }
  };

  /**
   * 关闭进度 Modal
   */
  const handleCloseProgressModal = () => {
    setProgressModalVisible(false);
  };

  /**
   * 加载任务详情
   */
  const loadTaskDetails = async (taskId: number) => {
    try {
      const response = await fieldMappingService.getAsyncTask(taskId);
      if (response.code === 0 && response.data) {
        setCurrentTask(response.data);
      }
    } catch (error: any) {
      console.error('加载任务详情失败:', error);
      // 超时错误不中断流程，等待轮询自动重试
      if (error.code === 'ECONNABORTED') {
        console.warn('加载任务详情超时，等待轮询重试');
      }
    }
  };

  // 获取最近完成的任务
  const fetchLatestCompletedTask = async () => {
    try {
      const response = await fieldMappingService.listAsyncTasks({
        task_type: 'field_mapping_suggest',
        status: 'completed',
        page: 1,
        page_size: 1
      });

      if (response.code === 0 && response.data?.items && response.data.items.length > 0) {
        const latestTask = response.data.items[0];
        setTaskId(latestTask.id);
        setCurrentTask(latestTask);
        setPageState('COMPLETED');
        loadTaskResults(latestTask.id);
      }
    } catch (error: any) {
      console.error('获取最近完成的任务失败:', error);
      // 不显示错误提示，因为没有最近的任务是正常情况
    }
  };

  // 加载任务结果（使用缓存优化 + 服务器分页）
    const loadTaskResults = async (taskId: number, page: number = 1, size: number = 20) => {
      try {
        const response = await fieldMappingService.getFieldMappingSuggestions(taskId, {
          page,
          page_size: size
        });
  
        if (response.code === 0 && response.data) {
          const items = response.data.items || [];
          setSuggestions(items);
          setPagination({
            current: page,
            pageSize: size,
            total: response.data.total || 0
          });
        }
      } catch (error: any) {
        console.error('加载任务结果失败:', error);
        message.error(error.message || '加载结果失败');
      }
    };  /**
   * 获取当前阶段索引
   */
  const getCurrentStageIndex = () => {
    if (!currentTask?.stages) return 0;
    
    for (let i = 0; i < currentTask.stages.length; i++) {
      if (currentTask.stages[i].status === 'running') {
        return i;
      }
    }
    
    // 如果没有正在运行的，检查是否有已完成的
    for (let i = currentTask.stages.length - 1; i >= 0; i--) {
      if (currentTask.stages[i].status === 'completed') {
        return i + 1;
      }
    }
    
    return 0;
  };

  /**
   * 获取步骤状态
   */
  const getStepStatus = (stageStatus: string) => {
    const statusMap: Record<string, 'wait' | 'process' | 'finish' | 'error'> = {
      'pending': 'wait',
      'running': 'process',
      'completed': 'finish',
      'failed': 'error'
    };
    return statusMap[stageStatus] || 'wait';
  };

  // ==================== 原有函数 ====================

  // 获取建议
  const fetchSuggestions = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    // 检查是否有数据结构
    if (schemaList.length === 0) {
      message.warning('当前版本尚未导入数据库结构，请先在"版本中心-数据结构"导入结构后再生成映射建议');
      return;
    }

    setLoading(true);
    try {
      const request: fieldMappingService.FieldMappingSuggestRequest = {
        include_paths: includePaths,
        include_query: includeQuery,
        include_body: includeBody,
        use_ai_fallback: useAiFallback,
        ai_confidence_threshold: aiConfidenceThreshold
      };
      
      const response = await fieldMappingService.suggestFieldMappings(
        request,
        { project_id: currentProject.id, version_id: currentVersion.id }
      );
      
      if (response.code === 0) {
        const items = response.data?.items || [];
        setSuggestions(items);
        message.success(`生成了 ${items.length} 个映射建议`);
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

  /**
   * 计算映射统计信息
   */
  const calculateStatistics = (suggestions: FieldMappingSuggestion[]): fieldMappingService.MappingStatistics => {
    let highConfidenceCount = 0;
    let mediumConfidenceCount = 0;
    let lowConfidenceCount = 0;
    let aiFallbackCount = 0;
    let autoConfirmedCount = 0;
    
    // 新增：状态统计
    let proposedCount = 0;
    let confirmedCount = 0;
    let rejectedCount = 0;
    
    suggestions.forEach(suggestion => {
      // 统计状态
      const status = suggestion.status || fieldMappingService.MappingStatus.PROPOSED;
      if (status === fieldMappingService.MappingStatus.PROPOSED) {
        proposedCount++;
      } else if (status === fieldMappingService.MappingStatus.CONFIRMED) {
        confirmedCount++;
      } else if (status === fieldMappingService.MappingStatus.REJECTED) {
        rejectedCount++;
      }
      
      suggestion.candidates.forEach(candidate => {
        // 检查是否 AI 选择
        if (candidate.ai_selected) {
          aiFallbackCount++;
        }
        
        // 统计置信度分布
        if (candidate.score >= 0.85) {
          highConfidenceCount++;
          autoConfirmedCount++;
        } else if (candidate.score >= 0.60) {
          mediumConfidenceCount++;
        } else {
          lowConfidenceCount++;
        }
      });
    });
    
    return {
      total_fields: suggestions.length,
      ai_fallback_count: aiFallbackCount,
      high_confidence_count: highConfidenceCount,
      medium_confidence_count: mediumConfidenceCount,
      low_confidence_count: lowConfidenceCount,
      auto_confirmed_count: autoConfirmedCount,
      // 新增：状态统计
      proposed_count: proposedCount,
      confirmed_count: confirmedCount,
      rejected_count: rejectedCount
    };
  };

  // 创建异步任务
  const handleCreateTask = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    // 检查是否有数据结构
    if (schemaList.length === 0) {
      message.warning('当前版本尚未导入数据库结构，请先在"版本中心-数据结构"导入结构后再生成映射建议');
      return;
    }

    const data: AsyncTaskCreateRequest = {
      include_paths: includePaths,
      include_query: includeQuery,
      include_body: includeBody,
      use_ai: useAi,
      ai_config: {
        high_priority_enabled: aiHighPriority,
        medium_priority_enabled: aiMediumPriority,
        low_priority_enabled: aiLowPriority
      }
    };

    setLoading(true);
    try {
      const response = await fieldMappingService.createFieldMappingSuggestTask(
        data,
        { project_id: currentProject.id, version_id: currentVersion.id }
      );

      if (response.code === 0 && response.data) {
        const newTaskId = response.data.task_id;
        message.success('任务已创建，请在执行记录中查看详情');
        setTaskModalVisible(false);
        
        // 打开执行记录抽屉
        await openHistoryDrawer();
        
        // 刷新历史记录以显示新任务
        await fetchHistoryList(1);
      } else {
        message.error(response.message || '创建任务失败');
      }
    } catch (error: any) {
      console.error('创建任务失败:', error);
      message.error(error.message || '创建任务失败');
    } finally {
      setLoading(false);
    }
  };

  // ==================== 历史记录相关函数 ====================
  
  /**
   * 打开历史记录抽屉
   */
  const openHistoryDrawer = async () => {
    if (!currentProject?.id) {
      message.warning('请先选择项目');
      return;
    }
    
    setHistoryDrawerVisible(true);
    await fetchHistoryList(1);
  };

  /**
   * 关闭历史记录抽屉
   */
  const closeHistoryDrawer = () => {
    setHistoryDrawerVisible(false);
  };

  /**
   * 获取历史记录列表（P2 优化：添加缓存）
   */
  const fetchHistoryList = async (page: number = 1) => {
    if (!currentProject?.id) {
      return;
    }

    setHistoryLoading(true);
    try {
      // 防御性编程：确保参数有效
      const validPage = Number.isInteger(page) && page > 0 ? page : 1;
      const validOffset = (validPage - 1) * historyPageSize;
      
      const response = await fieldMappingService.listAsyncTasks({
        task_type: 'field_mapping_suggest',
        project_id: currentProject.id,
        version_id: currentVersion?.id,
        limit: historyPageSize,
        offset: validOffset
      });

      if (response.code === 0 && response.data) {
        setHistoryList(response.data.items || []);
        setHistoryTotal(response.data.total || 0);
        setHistoryPage(validPage);
      } else {
        message.error(response.message || '获取历史记录失败');
      }
    } catch (error: any) {
      console.error('获取历史记录失败:', error);
      message.error(error.message || '获取历史记录失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  /**
   * 历史记录分页改变
   */
  const handleHistoryPageChange = (page: number, pageSize: number) => {
    setHistoryPageSize(pageSize);
    fetchHistoryList(page);
  };

  /**
   * 加载历史任务
   */
  const loadHistoryTask = async (taskId: number) => {
    // 如果当前有正在运行的任务，提示用户
    if (currentTask && currentTask.status === 'running') {
      Modal.confirm({
        title: '当前有任务正在进行',
        content: '切换历史记录将停止当前任务的监控，是否继续？',
        onOk: async () => {
          stopPolling();
          await switchToTask(taskId);
        }
      });
    } else {
      await switchToTask(taskId);
    }
  };

  /**
   * 切换到指定任务（P2 优化：使用缓存）
   */
  const switchToTask = async (taskId: number) => {
    try {
      // 使用带缓存的服务函数
      const task = await fieldMappingService.getAsyncTaskCached(taskId);

      if (!task) {
        message.error('任务不存在');
        return;
      }

      setTaskId(taskId);
      setCurrentTask(task);

      if (task.status === 'running') {
        setPageState('RUNNING');
        startPolling(taskId);
      } else if (task.status === 'completed') {
        setPageState('COMPLETED');
        loadTaskResults(taskId);
      } else if (task.status === 'failed') {
        setPageState('FAILED');
      } else if (task.status === 'cancelled') {
        setPageState('IDLE');
      } else {
        setPageState('IDLE');
      }

      closeHistoryDrawer();
    } catch (error: any) {
      console.error('加载任务失败:', error);
      message.error(error.message || '加载任务失败');
    }
  };

  /**
   * 展开/折叠历史任务详情
   */
  const toggleExpandTask = async (taskId: number) => {
    // 如果已展开，则折叠
    if (expandedTaskId === taskId) {
      setExpandedTaskId(null);
      setExpandedTaskDetail(null);
      setExpandedTaskSuggestions([]);
      return;
    }

    // 否则展开
    try {
      const response = await fieldMappingService.getAsyncTask(taskId);
      if (response.code === 0 && response.data) {
        setExpandedTaskDetail(response.data);
        setExpandedTaskId(taskId);

        // 如果任务已完成，加载建议结果
        if (response.data.status === 'completed') {
          const suggestions = await fieldMappingService.getFieldMappingSuggestionsCached(taskId);
          setExpandedTaskSuggestions(suggestions || []);
        }
      }
    } catch (error: any) {
      console.error('加载任务详情失败:', error);
      message.error(error.message || '加载任务详情失败');
    }
  };

  /**
   * 任务取消处理（增强版）
   */
  const handleCancelTask = async () => {
    if (!taskId) {
      return;
    }

    Modal.confirm({
      title: '确认取消任务',
      content: '取消后将无法恢复，是否继续？',
      onOk: async () => {
        try {
          const response = await fieldMappingService.cancelAsyncTask(taskId);
          if (response.code === 0) {
            message.success('任务已取消');
            stopPolling();
            setPageState('IDLE');
            setTaskId(null);
            setCurrentTask(null);
          } else {
            message.error(response.message || '取消任务失败');
          }
        } catch (error: any) {
          console.error('取消任务失败:', error);
          message.error(error.message || '取消任务失败');
        }
      }
    });
  };

  // 获取任务进度（保留旧函数用于兼容）
  const fetchTaskProgress = async (taskId: number) => {
    try {
      const response = await fieldMappingService.getAsyncTask(taskId);
      
      if (response.code === 0 && response.data) {
        setCurrentTask(response.data);
        
        // 如果任务完成或失败，停止轮询
        if (response.data.status === 'completed' || response.data.status === 'failed' || response.data.status === 'cancelled') {
          if (pollingInterval) {
            clearInterval(pollingInterval);
            setPollingInterval(null);
          }
          
          if (response.data.status === 'completed') {
            message.success('任务完成');
            // 加载结果
            loadTaskResults(taskId);
          } else if (response.data.status === 'failed') {
            message.error(`任务失败: ${response.data.error_message || '未知错误'}`);
          } else if (response.data.status === 'cancelled') {
            message.info('任务已取消');
          }
        }
      }
    } catch (error: any) {
      console.error('获取任务进度失败:', error);
    }
  };

  // 自动应用高置信度映射
  const handleAutoApplyHighConfidence = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    try {
      setLoading(true);
      const response = await fieldMappingService.autoApplyFieldMappings(
        {
          min_confidence: HIGH_CONFIDENCE_THRESHOLD
        },
        {
          project_id: currentProject.id,
          version_id: currentVersion.id
        }
      );
      message.success(`成功应用 ${response.data?.updated_count || 0} 个高置信度映射`);
      await fetchSuggestions(); // 刷新列表
    } catch (error: any) {
      message.error(error.message || '自动应用失败');
    } finally {
      setLoading(false);
    }
  };

  // 从其他版本集成
  const handleCloneFromVersion = () => {
    message.info('从其他版本集成功能待实现');
  };

  // 批量拒绝选中的映射
  const handleBatchReject = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }

    const selectedSuggestions = suggestions.filter(s => selectedRowKeys.includes(s.id!));
    
    if (selectedSuggestions.length === 0) {
      message.warning('请先选择要拒绝的映射');
      return;
    }

    try {
      setLoading(true);
      // 将选中的建议标记为已拒绝
      const updatedSuggestions = suggestions.map(s => {
        if (selectedRowKeys.includes(s.id!)) {
          return { ...s, status: fieldMappingService.MappingStatus.REJECTED };
        }
        return s;
      });
      setSuggestions(updatedSuggestions);
      setSelectedRowKeys([]);
      setRejectModalVisible(false);
      message.success(`已拒绝 ${selectedSuggestions.length} 个映射建议`);
    } catch (error: any) {
      message.error(error.message || '批量拒绝失败');
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

    const selectedSuggestions = suggestions.filter(s => selectedRowKeys.includes(s.id!));
    
    if (selectedSuggestions.length === 0) {
      message.warning('请先选择要确认的映射');
      return;
    }

    // 准备批量应用的数据
    const batchItems: FieldMappingBatchApplyItem[] = [];
    
    selectedSuggestions.forEach(suggestion => {
      const selectedCandidate = suggestion.candidates?.[0];
      if (selectedCandidate && typeof suggestion.id === 'number') {
        batchItems.push({
          suggestion_id: suggestion.id,
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

  // ==================== 页面可见性监听 ====================
  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsPageVisible(!document.hidden);
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // 表格列定义
  const columns = [
    {
      title: 'API',
      dataIndex: 'definition_path',
      key: 'api',
      render: (_text: string, record: FieldMappingSuggestion) => (
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
              <div style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
                置信度: {(topCandidate.score * 100).toFixed(1)}%
              </div>
              {/* 新增：AI 标识 */}
              {topCandidate.ai_selected && (
                <div style={{ marginTop: 4 }}>
                  <Tag color="purple" icon={<SyncOutlined />} style={{ fontSize: 11 }}>
                    AI 确认
                  </Tag>
                </div>
              )}
            </div>
          );
        }
        return <span style={{ color: '#ccc' }}>无推荐</span>;
      }
    },
    {
      title: '类型',
      key: 'type',
      width: 80,
      render: (_: any, record: FieldMappingSuggestion) => {
        const isAi = record.candidates?.[0]?.ai_selected;
        return isAi ? (
          <Tag color="green">自动 AI</Tag>
        ) : (
          <Tag color="purple">手动</Tag>
        );
      }
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_: any, record: FieldMappingSuggestion) => {
        const status = record.status || fieldMappingService.MappingStatus.PROPOSED;
        switch (status) {
          case fieldMappingService.MappingStatus.CONFIRMED:
            return <Tag color="success">已确认</Tag>;
          case fieldMappingService.MappingStatus.REJECTED:
            return <Tag color="error">已拒绝</Tag>;
          case fieldMappingService.MappingStatus.PROPOSED:
          default:
            return <Tag color="warning">待审核</Tag>;
        }
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
              {/* 新增：AI 选择原因 */}
              {topCandidate.ai_reason && (
                <Tag key="ai-reason" color="purple" icon={<SyncOutlined />}>
                  {topCandidate.ai_reason}
                </Tag>
              )}
            </Space>
          );
        }
        return <span>-</span>;
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: FieldMappingSuggestion) => (
        <Button 
          type="link" 
          size="small"
          onClick={() => showDetailModal(record)}
        >
          详情
        </Button>
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

  // ==================== 筛选逻辑（增强版） ====================
  const filteredSuggestions = suggestions.filter(s => {
    // 类型筛选
    const isAi = s.candidates?.[0]?.ai_selected || false;
    let typeMatch = true;
    if (typeFilter === 'manual') {
      typeMatch = !isAi;
    } else if (typeFilter === 'auto') {
      typeMatch = isAi;
    }

    // 状态筛选
    let statusMatch = true;
    if (statusFilter !== 'all') {
      statusMatch = s.status === statusFilter;
    }
    
    // 新增：置信度筛选
    let confidenceMatch = true;
    const score = s.candidates?.[0]?.score || 0;
    if (confidenceFilter === 'high' && score < 0.85) {
      confidenceMatch = false;
    } else if (confidenceFilter === 'medium' && (score < 0.6 || score >= 0.85)) {
      confidenceMatch = false;
    } else if (confidenceFilter === 'low' && score >= 0.6) {
      confidenceMatch = false;
    }
    
    // 新增：API筛选
    let methodMatch = true;
    if (methodFilter !== 'all' && s.definition_method !== methodFilter) {
      methodMatch = false;
    }
    
    // 新增：字段类型筛选
    let fieldTypeMatch = true;
    if (fieldTypeFilter !== 'all') {
      const prefix = s.api_field_path.split('.')[0];
      if (prefix !== fieldTypeFilter) {
        fieldTypeMatch = false;
      }
    }
    
    // 新增：搜索筛选
    let searchMatch = true;
    if (searchKeyword) {
      const keyword = searchKeyword.toLowerCase();
      const fieldName = s.api_field_path.split('.').pop()?.toLowerCase() || '';
      const tableName = s.candidates?.[0]?.db_table?.toLowerCase() || '';
      const columnName = s.candidates?.[0]?.db_column?.toLowerCase() || '';
      
      if (!fieldName.includes(keyword) && 
          !tableName.includes(keyword) && 
          !columnName.includes(keyword)) {
        searchMatch = false;
      }
    }

    return typeMatch && statusMatch && confidenceMatch && methodMatch && fieldTypeMatch && searchMatch;
  });

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
    // 确保使用id作为key
    columnWidth: '50px',
  };

  return (
    <div style={{ padding: 24 }}>
      {/* 标题行 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>字段映射管理</h2>
      </div>

      {/* Tabs 组件 */}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'suggestions' | 'mappings')}
        items={[
          {
            key: 'suggestions',
            label: '建议管理',
            children: (
              <>
{/* 标题行：参考数据结构页面样式 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>字段映射建议</h2>
        <Space>
          <Button 
            icon={<SyncOutlined />} 
            onClick={() => setTaskModalVisible(true)}
            loading={loading}
            type="primary"
          >
            生成映射建议
          </Button>
          <Button 
            icon={<ClockCircleOutlined />} 
            onClick={openHistoryDrawer}
          >
            执行记录
          </Button>
          <Button
            icon={<SyncOutlined />}
            onClick={handleCloneFromVersion}
          >
            从其他版本集成
          </Button>
          <Button
            icon={<PlayCircleOutlined />}
            onClick={() => setConfirmModalVisible(true)}
            disabled={selectedRowKeys.length === 0}
          >
            批量确认 ({selectedRowKeys.length})
          </Button>
          <Button
            icon={<CloseCircleOutlined />}
            onClick={() => setRejectModalVisible(true)}
            disabled={selectedRowKeys.length === 0}
          >
            批量拒绝 ({selectedRowKeys.length})
          </Button>
        </Space>
      </div>

      {/* ==================== 筛选器工具栏（增强版） ==================== */}
      {suggestions.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <Space wrap>
              <span style={{ color: 'var(--text-tertiary)' }}>🔍</span>
              
              {/* 搜索框 */}
              <Input.Search
                placeholder="搜索字段名/表名/列名"
                style={{ width: 200 }}
                value={searchKeyword}
                onChange={e => setSearchKeyword(e.target.value)}
                allowClear
              />
              
              {/* 类型筛选 */}
              <Select
                style={{ width: 120 }}
                value={typeFilter}
                onChange={setTypeFilter}
                options={[
                  { label: '全部类型', value: 'all' },
                  { label: '手动映射', value: 'manual' },
                  { label: '自动映射', value: 'auto' }
                ]}
              />
              
              {/* 状态筛选 */}
              <Select
                style={{ width: 120 }}
                value={statusFilter}
                onChange={setStatusFilter}
                options={[
                  { label: '全部状态', value: 'all' },
                  { label: '待审核', value: 'proposed' },
                  { label: '已确认', value: 'confirmed' },
                  { label: '已拒绝', value: 'rejected' }
                ]}
              />
              
              {/* 置信度筛选 */}
              <Select
                style={{ width: 140 }}
                value={confidenceFilter}
                onChange={setConfidenceFilter}
                options={[
                  { label: '全部置信度', value: 'all' },
                  { label: '高置信度（≥85%）', value: 'high' },
                  { label: '中等置信度（60%-85%）', value: 'medium' },
                  { label: '低置信度（<60%）', value: 'low' }
                ]}
              />
              
              {/* API筛选 */}
              <Select
                style={{ width: 120 }}
                value={methodFilter}
                onChange={setMethodFilter}
                options={[
                  { label: '全部API', value: 'all' },
                  { label: 'POST接口', value: 'POST' },
                  { label: 'GET接口', value: 'GET' },
                  { label: 'PUT接口', value: 'PUT' },
                  { label: 'DELETE接口', value: 'DELETE' },
                  { label: 'PATCH接口', value: 'PATCH' }
                ]}
              />
              
              {/* 字段类型筛选 */}
              <Select
                style={{ width: 120 }}
                value={fieldTypeFilter}
                onChange={setFieldTypeFilter}
                options={[
                  { label: '全部字段', value: 'all' },
                  { label: '路径参数', value: 'path' },
                  { label: '查询参数', value: 'query' },
                  { label: '请求体参数', value: 'body' }
                ]}
              />
              
              <Button 
                icon={<SyncOutlined />} 
                onClick={() => {
                  if (taskId) {
                    loadTaskResults(taskId, pagination.current, pagination.pageSize);
                  } else {
                    message.info('没有正在进行的任务，请先生成映射建议');
                  }
                }}
                size="small"
              >
                刷新
              </Button>
            </Space>
          </div>
        )}

        {/* ==================== 字段选择复选框 ==================== */}
        
        {/* 字段选择复选框 */}
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

        {/* ==================== 建议列表表格（简化版 - 移除pageState判断） ==================== */}
        {suggestions.length === 0 && !loading ? (
          <Empty
            description="暂无映射建议"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" onClick={() => setTaskModalVisible(true)}>
              生成映射建议
            </Button>
          </Empty>
        ) : (
          <Table
            rowSelection={rowSelection}
            columns={columns}
            dataSource={filteredSuggestions}
            rowKey="id"
            loading={loading}
            pagination={{
              current: pagination.current,
              pageSize: pagination.pageSize,
              total: filteredSuggestions.length,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 条`,
              onChange: (page, pageSize) => {
                // 重置筛选器状态，避免分页切换时出现重复数据
                setTypeFilter('all');
                setStatusFilter('all');
                setConfidenceFilter('all');
                setMethodFilter('all');
                setFieldTypeFilter('all');
                setPagination({ ...pagination, current: page, pageSize: size });
              },
              onShowSizeChange: (current, size) => {
                // 重置筛选器状态，避免分页切换时出现重复数据
                setTypeFilter('all');
                setStatusFilter('all');
                setConfidenceFilter('all');
                setMethodFilter('all');
                setFieldTypeFilter('all');
                setPagination({ ...pagination, current: 1, pageSize: size });
              }
            }}
          />
        )}

        {/* ==================== 以下内容已简化 - 移除任务进度相关渲染 ==================== */}
        {/* RUNNING 态：显示进度面板 - 已移除 */}
        {/* COMPLETED 态：显示任务摘要和结果表格 - 已移除 */}
        {/* FAILED 态：显示错误信息 - 已移除 */}
        {/* 兼容：如果 pageState 为空但 suggestions 有数据，显示表格 - 已简化到上方 */}
        
        {/* ==================== 简化完成 ==================== */}

      {/* 任务创建模态框 */}
      <Modal
        title="生成字段映射建议"
        open={taskModalVisible}
        onCancel={() => setTaskModalVisible(false)}
        onOk={handleCreateTask}
        okText="开始生成"
        cancelText="取消"
        confirmLoading={loading}
        width={600}
      >
        <Form layout="vertical">
          <Form.Item label="包含参数类型">
            <Space direction="vertical">
              <Checkbox checked={includePaths} onChange={e => setIncludePaths(e.target.checked)}>
                路径参数
              </Checkbox>
              <Checkbox checked={includeQuery} onChange={e => setIncludeQuery(e.target.checked)}>
                查询参数
              </Checkbox>
              <Checkbox checked={includeBody} onChange={e => setIncludeBody(e.target.checked)}>
                请求体参数
              </Checkbox>
            </Space>
          </Form.Item>

          {/* ==================== 新增：算法配置 ==================== */}
          <Divider>算法配置</Divider>

          <Form.Item label="AI 兜底">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Switch 
                checked={useAiFallback} 
                onChange={setUseAiFallback}
                checkedChildren="启用"
                unCheckedChildren="禁用"
              />
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                对低置信度字段使用 AI 辅助决策
              </div>
            </Space>
          </Form.Item>

          <Form.Item label={`AI 触发阈值: ${aiConfidenceThreshold}`}>
            <Slider
              min={0.5}
              max={0.9}
              step={0.05}
              value={aiConfidenceThreshold}
              onChange={setAiConfidenceThreshold}
              marks={{
                0.5: '0.5',
                0.7: '0.7',
                0.9: '0.9'
              }}
              disabled={!useAiFallback}
            />
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4 }}>
              置信度低于此值时触发 AI（推荐 0.7）
            </div>
          </Form.Item>

          <Alert
            message="算法说明"
            description={
              <div>
                <div>• 重心算法：通过分析字段上下文确定主表，提高跨表同名词映射准确性</div>
                <div>• AI 兜底：对低置信度字段（{aiConfidenceThreshold}）使用 AI 辅助决策</div>
                <div>• 推荐配置：启用重心算法 + AI 兜底 + 阈值 0.7</div>
              </div>
            }
            type="info"
            showIcon
          />
        </Form>
      </Modal>

      {/* 进度对话框 */}
      <Modal
        title="映射建议生成进度"
        open={progressModalVisible}
        onCancel={handleCloseProgressModal}
        footer={null}
        width={720}
      >
        {currentTask && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* 总体进度 */}
            <div>
              <div style={{ marginBottom: 8 }}>
                <strong>总体进度</strong>
                <span style={{ marginLeft: 16, color: 'var(--text-tertiary)' }}>
                  {currentTask.progress}%
                </span>
              </div>
              <Progress 
                percent={currentTask.progress} 
                status={currentTask.status === 'failed' ? 'exception' : currentTask.status === 'completed' ? 'success' : 'active'}
              />
              {currentTask.progress_message && (
                <div style={{ marginTop: 8, color: 'var(--text-tertiary)' }}>{currentTask.progress_message}</div>
              )}
            </div>

            {/* 阶段进度 */}
            <div>
              <strong style={{ marginBottom: 12, display: 'block' }}>处理阶段</strong>
              <FieldMappingStageProgress
                taskId={currentTask.id}
                progress={currentTask as any}
                onRetry={async () => {
                  // 重试后重新轮询任务进度
                  await fetchTaskProgress(currentTask.id);
                }}
                onResume={async () => {
                  // 继续执行后重新轮询任务进度
                  await fetchTaskProgress(currentTask.id);
                }}
                onReset={async () => {
                  // 重置后清空当前任务状态
                  setCurrentTask(null);
                }}
              />
            </div>

            {/* 筛选统计 */}
            {currentTask.status === 'running' && currentTask.statistics && (
              <div>
                <strong style={{ marginBottom: 8, display: 'block' }}>筛选统计</strong>
                <List
                  size="small"
                  dataSource={[
                    { label: '自动确认', count: currentTask.statistics.auto_confirmed || 0, color: 'green' },
                    { label: '高优先级AI', count: currentTask.statistics.ai_high || 0, color: 'red' },
                    { label: '中优先级AI', count: currentTask.statistics.ai_medium || 0, color: 'orange' },
                    { label: '低优先级AI', count: currentTask.statistics.ai_low || 0, color: 'blue' }
                  ]}
                  renderItem={item => (
                    <List.Item>
                      <Tag color={item.color}>{item.label}</Tag>
                      <span>{item.count}个字段</span>
                    </List.Item>
                  )}
                />
              </div>
            )}

            {/* 操作按钮 */}
            {currentTask.status === 'completed' && (
              <Space>
                <Button type="primary" onClick={() => {
                  handleCloseProgressModal();
                }}>
                  查看结果
                </Button>
              </Space>
            )}

            {currentTask.status === 'running' && (
              <Button danger onClick={handleCancelTask}>
                取消任务
              </Button>
            )}

            {currentTask.status === 'failed' && (
              <Alert
                message="处理失败"
                description={currentTask.error_message}
                type="error"
                showIcon
              />
            )}
          </Space>
        )}
      </Modal>

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

      {/* 批量拒绝模态框 */}
      <Modal
        title="批量拒绝映射"
        open={rejectModalVisible}
        onCancel={() => setRejectModalVisible(false)}
        onOk={handleBatchReject}
        okText="确认拒绝"
        cancelText="取消"
      >
        <p>您选择了 {selectedRowKeys.length} 个映射建议，确认后将标记为已拒绝状态。</p>
        <p style={{ color: '#ff4d4f' }}>已拒绝的映射将不会被应用到数据库。</p>
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
                <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-tertiary)' }}>
                  没有找到合适的候选映射
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* ==================== 历史记录抽屉 ==================== */}
      <Drawer
        title="执行记录"
        placement="right"
        width={600}
        open={historyDrawerVisible}
        onClose={closeHistoryDrawer}
        styles={{
          body: { paddingBottom: 80 }
        }}
        extra={
          <Button onClick={() => fetchHistoryList()} icon={<SyncOutlined />}>
            刷新
          </Button>
        }
      >
        <Spin spinning={historyLoading}>
          <List
            dataSource={historyList}
            pagination={{
              current: historyPage,
              pageSize: historyPageSize,
              total: historyTotal,
              onChange: handleHistoryPageChange,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 条`,
              // P2 优化：虚拟滚动配置
              position: 'bottom',
              simple: false
            }}
            renderItem={(item) => (
              <div key={item.id}>
                <List.Item
                  actions={[
                    <Button 
                      type="link" 
                      size="small"
                      onClick={() => toggleExpandTask(item.id)}
                    >
                      {expandedTaskId === item.id ? '收起' : '查看'}
                    </Button>
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      <Badge 
                        status={
                          item.status === 'completed' ? 'success' : 
                          item.status === 'failed' ? 'error' : 
                          item.status === 'running' ? 'processing' : 'default'
                        }
                        text={item.id.toString()}
                      />
                    }
                    title={`任务 #${item.id}`}
                    description={
                      <div>
                        <div style={{ marginBottom: 4 }}>
                          <Tag color={
                            item.status === 'completed' ? 'green' : 
                            item.status === 'failed' ? 'red' : 
                            item.status === 'running' ? 'blue' : 'default'
                          }>
                            {item.status === 'completed' ? '已完成' : 
                             item.status === 'failed' ? '失败' : 
                             item.status === 'running' ? '进行中' : 
                             item.status === 'cancelled' ? '已取消' : '等待中'}
                          </Tag>
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                          创建时间: {new Date(item.created_at).toLocaleString('zh-CN')}
                        </div>
                        {item.finished_at && (
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                            完成时间: {new Date(item.finished_at).toLocaleString('zh-CN')}
                          </div>
                        )}
                        {item.duration && (
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                            耗时: {Math.floor(item.duration / 60)} 分 {item.duration % 60} 秒
                          </div>
                        )}
                        {item.result_count !== null && (
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                            生成建议: {item.result_count} 个
                          </div>
                        )}
                        {item.statistics && (
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                            自动确认: {item.statistics.auto_confirmed || 0}，AI增强: {item.statistics.ai_enhanced || 0}
                          </div>
                        )}
                        {item.error_message && (
                          <div style={{ fontSize: 12, color: '#ff4d4f' }}>
                            错误: {item.error_message}
                          </div>
                        )}
                      </div>
                    }
                  />
                </List.Item>

                {/* 展开的任务详情 */}
                {expandedTaskId === item.id && expandedTaskDetail && (
                  <div style={{
                    padding: '16px 16px 16px 48px',
                    backgroundColor: 'var(--bg-tertiary)',
                    borderTop: '1px solid var(--border-color)'
                  }}>
                    {/* 任务状态 */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 8 }}>
                        <strong>任务状态：</strong>
                        <Tag color={
                          expandedTaskDetail.status === 'completed' ? 'green' : 
                          expandedTaskDetail.status === 'failed' ? 'red' : 
                          expandedTaskDetail.status === 'running' ? 'blue' : 'default'
                        }>
                          {expandedTaskDetail.status === 'completed' ? '已完成' : 
                           expandedTaskDetail.status === 'failed' ? '失败' : 
                           expandedTaskDetail.status === 'running' ? '进行中' : 
                           expandedTaskDetail.status === 'cancelled' ? '已取消' : '等待中'}
                        </Tag>
                      </div>
                      
                      {/* 进度条 */}
                      {expandedTaskDetail.progress !== undefined && (
                        <div style={{ marginBottom: 12 }}>
                          <Progress 
                            percent={expandedTaskDetail.progress} 
                            status={expandedTaskDetail.status === 'failed' ? 'exception' : 
                                    expandedTaskDetail.status === 'completed' ? 'success' : 'active'}
                          />
                        </div>
                      )}

                      {/* 错误信息 */}
                      {expandedTaskDetail.error_message && (
                        <Alert
                          message="执行失败"
                          description={expandedTaskDetail.error_message}
                          type="error"
                          showIcon
                          style={{ marginBottom: 12 }}
                        />
                      )}
                    </div>

                    {/* 阶段进度 */}
                    {expandedTaskDetail.stages && expandedTaskDetail.stages.length > 0 && (
                      <div style={{ marginBottom: 16 }}>
                        <strong style={{ marginBottom: 8, display: 'block' }}>处理阶段</strong>
                        <Steps 
                          current={expandedTaskDetail.stages.findIndex(s => s.status === 'running') >= 0 
                            ? expandedTaskDetail.stages.findIndex(s => s.status === 'running')
                            : expandedTaskDetail.stages.filter(s => s.status === 'completed').length}
                          direction="vertical"
                          size="small"
                          items={expandedTaskDetail.stages.map((stage) => ({
                            title: stage.name,
                            status: stage.status === 'completed' ? 'finish' : 
                                    stage.status === 'running' ? 'process' : 
                                    stage.status === 'failed' ? 'error' : 'wait',
                            description: (
                              <div>
                                {stage.description && <div style={{ marginBottom: 4 }}>{stage.description}</div>}
                                <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                                  进度: {stage.progress}%
                                </div>
                              </div>
                            )
                          }))}
                        />
                      </div>
                    )}

                    {/* 映射建议列表 */}
                    {expandedTaskDetail.status === 'completed' && expandedTaskSuggestions.length > 0 && (
                      <div>
                        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong>映射建议列表</strong>
                          <Tag color="blue">{expandedTaskSuggestions.length} 条</Tag>
                        </div>
                        <Table
                          size="small"
                          columns={[
                            {
                              title: 'API',
                              dataIndex: 'definition_path',
                              key: 'api',
                              render: (_text: string, record: FieldMappingSuggestion) => (
                                <div>
                                  <Tag color={getMethodColor(record.definition_method)} style={{ fontSize: 11 }}>
                                    {record.definition_method}
                                  </Tag>
                                  <span style={{ fontSize: 12 }}>{record.definition_path}</span>
                                </div>
                              )
                            },
                            {
                              title: '字段路径',
                              dataIndex: 'api_field_path',
                              key: 'api_field_path',
                              render: (text: string) => <span style={{ fontSize: 12 }}>{text}</span>
                            },
                            {
                              title: '推荐',
                              key: 'recommended',
                              render: (_: any, record: FieldMappingSuggestion) => {
                                if (record.candidates && record.candidates.length > 0) {
                                  const topCandidate = record.candidates[0];
                                  return (
                                    <div style={{ fontSize: 12 }}>
                                      <strong>{topCandidate.db_table}</strong>.{topCandidate.db_column}
                                      <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                                        置信度: {(topCandidate.score * 100).toFixed(1)}%
                                      </div>
                                    </div>
                                  );
                                }
                                return <span style={{ fontSize: 12, color: '#ccc' }}>无推荐</span>;
                              }
                            },
                            {
                              title: '状态',
                              key: 'status',
                              width: 70,
                              render: (_: any, record: FieldMappingSuggestion) => {
                                const status = record.status || fieldMappingService.MappingStatus.PROPOSED;
                                const statusMap = {
                                  [fieldMappingService.MappingStatus.CONFIRMED]: { text: '已确认', color: 'success' },
                                  [fieldMappingService.MappingStatus.REJECTED]: { text: '已拒绝', color: 'error' },
                                  [fieldMappingService.MappingStatus.PROPOSED]: { text: '待审核', color: 'warning' }
                                };
                                const statusInfo = statusMap[status] || statusMap[fieldMappingService.MappingStatus.PROPOSED];
                                return <Tag color={statusInfo.color} style={{ fontSize: 11 }}>{statusInfo.text}</Tag>;
                              }
                            }
                          ]}
                          dataSource={expandedTaskSuggestions}
                          rowKey="id"
                          pagination={{
                            pageSize: 5,
                            size: 'small',
                            showTotal: (total) => `共 ${total} 条`
                          }}
                          scroll={{ y: 300 }}
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          />
        </Spin>
      </Drawer>
              </>
            )
          },
          {
            key: 'mappings',
            label: '映射管理',
            children: (
              <div>
                {/* 工具栏 */}
                <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    <Select
                      value={mappingFilter}
                      onChange={(value: any) => setMappingFilter(value)}
                      style={{ width: 120 }}
                      size="small"
                    >
                      <Select.Option value="all">全部状态</Select.Option>
                      <Select.Option value="confirmed">已确认</Select.Option>
                      <Select.Option value="rejected">已拒绝</Select.Option>
                      <Select.Option value="proposed">待审核</Select.Option>
                    </Select>
                    <Button 
                      icon={<SyncOutlined />} 
                      onClick={fetchMappings}
                      size="small"
                    >
                      刷新
                    </Button>
                  </Space>
                  <Space>
                    <Tag color="blue">
                      {filteredMappings.length} 条映射
                      {mappingFilter !== 'all' && `（共 ${mappings.length} 条）`}
                    </Tag>
                  </Space>
                </div>

                {/* 映射列表表格 */}
                <Table
                  dataSource={filteredMappings}
                  rowKey="id"
                  loading={mappingsLoading}
                  pagination={{
                    current: mappingsPagination.current,
                    pageSize: mappingsPagination.pageSize,
                    total: filteredMappings.length,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page, pageSize) => {
                      setMappingsPagination({
                        ...mappingsPagination,
                        current: page,
                        pageSize: pageSize || 20
                      });
                    },
                    onShowSizeChange: (current, size) => {
                      setMappingsPagination({
                        current: 1,
                        pageSize: size,
                        total: mappingsPagination.total
                      });
                    }
                  }}
                  columns={[
                    {
                      title: 'API',
                      key: 'api',
                      render: (_: any, record: fieldMappingService.FieldMappingWithDetails) => (
                        <div>
                          <Tag color={getMethodColor(record.definition_method)}>
                            {record.definition_method}
                          </Tag>
                          <span>{record.definition_path}</span>
                        </div>
                      )
                    },
                    {
                      title: 'API 字段',
                      dataIndex: 'api_field_path',
                      key: 'api_field_path'
                    },
                    {
                      title: '映射表/字段',
                      key: 'mapping',
                      render: (_: any, record: fieldMappingService.FieldMappingWithDetails) => (
                        <div>
                          <strong>{record.db_table}</strong>.{record.db_column}
                        </div>
                      )
                    },
                    {
                      title: '置信度',
                      dataIndex: 'confidence',
                      key: 'confidence',
                      width: 100,
                      render: (score: number) => {
                        if (!score) return <span>-</span>;
                        const percentage = (score * 100).toFixed(1);
                        let color = 'default';
                        if (score >= 0.85) color = 'success';
                        else if (score >= 0.7) color = 'processing';
                        else if (score >= 0.5) color = 'warning';
                        else color = 'error';
                        return (
                          <Progress 
                            percent={parseFloat(percentage)} 
                            size="small" 
                            strokeColor={color}
                            format={() => `${percentage}%`}
                          />
                        );
                      }
                    },
                    {
                      title: '来源',
                      dataIndex: 'source',
                      key: 'source',
                      width: 100,
                      render: (source: string) => {
                        if (source === 'ai') {
                          return <Tag color="green">自动 AI</Tag>;
                        }
                        return <Tag color="blue">手动</Tag>;
                      }
                    },
                    {
                      title: '操作',
                      key: 'action',
                      width: 120,
                      render: (_: any, record: fieldMappingService.FieldMappingWithDetails) => (
                        <Space size="small">
                          <Popconfirm
                            title="确认删除？"
                            onConfirm={() => handleDeleteMapping(record.id)}
                            okText="确定"
                            cancelText="取消"
                          >
                            <Button 
                              type="link" 
                              size="small" 
                              danger
                            >
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      )
                    }
                  ]}
                />
              </div>
            )
          }
        ]}
      />
    </div>
  );
};

export default FieldMappingSuggestions;
