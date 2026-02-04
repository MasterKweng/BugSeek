/**
 * 场景执行历史弹窗组件
 */
import React, { useEffect, useState } from 'react';
import {
  Modal,
  Table,
  Tag,
  Button,
  Space,
  Select,
  Pagination,
  message
} from 'antd';
import {
  ReloadOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { useScenarioStore } from '../../../store/scenario';
import ExecutionDetailModal from './ExecutionDetailModal';

const { Option } = Select;

interface ExecutionHistoryModalProps {
  visible: boolean;
  scenarioId: number | null;
  scenarioName: string;
  onClose: () => void;
}

interface ExecutionRecord {
  id: number;
  status: string;
  duration_ms: number;
  total_steps: number;
  passed_steps: number;
  failed_steps: number;
  environment_name: string;
  triggered_by: string;
  started_at: string;
  finished_at: string;
}

const ExecutionHistoryModal: React.FC<ExecutionHistoryModalProps> = ({
  visible,
  scenarioId,
  scenarioName,
  onClose
}) => {
  const {
    loadScenarioExecutions,
    loadScenarioExecutionDetail
  } = useScenarioStore();

  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedExecutionId, setSelectedExecutionId] = useState<number | null>(null);

  useEffect(() => {
    if (visible && scenarioId) {
      loadExecutions();
    }
  }, [visible, scenarioId, page, pageSize, statusFilter]);

  const loadExecutions = async () => {
    if (!scenarioId) return;

    setLoading(true);
    try {
      const data = await loadScenarioExecutions(scenarioId, page, pageSize, statusFilter);
      if (data) {
        setExecutions(data.executions || []);
        setTotal(data.total || 0);
      }
    } catch (error) {
      message.error('加载执行历史失败');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetail = async (executionId: number) => {
    if (!scenarioId) return;

    setLoading(true);
    try {
      const data = await loadScenarioExecutionDetail(scenarioId, executionId);
      if (data) {
        setSelectedExecutionId(executionId);
        setDetailVisible(true);
      }
    } catch (error) {
      message.error('加载执行详情失败');
    } finally {
      setLoading(false);
    }
  };

  const getStatusTag = (status: string) => {
    switch (status) {
      case 'success':
        return <Tag icon={<CheckCircleOutlined />} color="success">成功</Tag>;
      case 'failed':
        return <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>;
      case 'partial':
        return <Tag icon={<ClockCircleOutlined />} color="warning">部分成功</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  const columns = [
    {
      title: '执行时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString('zh-CN'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 100,
      render: (ms: number) => `${(ms / 1000).toFixed(2)}s`,
    },
    {
      title: '步骤',
      key: 'steps',
      width: 120,
      render: (_: any, record: ExecutionRecord) => (
        <span>
          {record.passed_steps}/{record.total_steps} 通过
          {record.failed_steps > 0 && (
            <Tag color="error" style={{ marginLeft: 4 }}>
              {record.failed_steps} 失败
            </Tag>
          )}
        </span>
      ),
    },
    {
      title: '环境',
      dataIndex: 'environment_name',
      key: 'environment_name',
      width: 120,
    },
    {
      title: '触发方式',
      dataIndex: 'triggered_by',
      key: 'triggered_by',
      width: 100,
      render: (type: string) => {
        const typeMap: Record<string, string> = {
          'manual': '手动',
          'jenkins': 'Jenkins',
          'schedule': '定时'
        };
        return typeMap[type] || type;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      fixed: 'right' as const,
      render: (_: any, record: ExecutionRecord) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => handleViewDetail(record.id)}
        >
          详情
        </Button>
      ),
    },
  ];

  return (
    <>
      <Modal
        title={`场景执行历史 - ${scenarioName}`}
        open={visible}
        onCancel={onClose}
        footer={null}
        width={1000}
      >
        <Space style={{ marginBottom: 16 }}>
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            placeholder="筛选状态"
            style={{ width: 120 }}
            allowClear
          >
            <Option value="success">成功</Option>
            <Option value="failed">失败</Option>
            <Option value="partial">部分成功</Option>
          </Select>
          <Button
            icon={<ReloadOutlined />}
            onClick={loadExecutions}
            loading={loading}
          >
            刷新
          </Button>
        </Space>

        <Table
          columns={columns}
          dataSource={executions}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 900 }}
        />

        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            onChange={(p, ps) => {
              setPage(p);
              setPageSize(ps);
            }}
            showSizeChanger
            showTotal={(total) => `共 ${total} 条`}
          />
        </div>
      </Modal>

      {/* 执行详情弹窗 */}
      <ExecutionDetailModal
        visible={detailVisible}
        scenarioId={scenarioId}
        executionId={selectedExecutionId}
        onClose={() => {
          setDetailVisible(false);
          setSelectedExecutionId(null);
        }}
      />
    </>
  );
};

export default ExecutionHistoryModal;