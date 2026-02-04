/**
 * 链路详情页面 - 独立页面方案（方案D）
 * 展示单个内部链路的完整信息，包括流程图和详细步骤
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Space,
  Tag,
  Descriptions,
  Timeline,
  message,
  Row,
  Col,
  Empty,
  Spin
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  DeleteOutlined,
  DownloadOutlined,
  ShareAltOutlined
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useProjectStore } from '../../store/project';
import { useScenarioStore } from '../../store/scenario';

const ChainDetail: React.FC = () => {
  const navigate = useNavigate();
  const { moduleId, chainId } = useParams<{ moduleId: string; chainId: string }>();
  const { currentProject } = useProjectStore();
  
  const {
    modules,
    internalChains,
    loadingInternalChains,
    viewModuleDetail,
  } = useScenarioStore();

  const [currentModule, setCurrentModule] = useState<any>(null);
  const [currentChain, setCurrentChain] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // 获取当前模块
  useEffect(() => {
    if (moduleId) {
      const module = modules.find(m => m.id === Number(moduleId));
      setCurrentModule(module);
      if (module) {
        viewModuleDetail(module);
      }
    }
  }, [moduleId, modules]);

  // 获取当前链路
  useEffect(() => {
    if (chainId && internalChains) {
      const chain = internalChains.find(c => c.chain_id === Number(chainId));
      setCurrentChain(chain || null);
      setLoading(false);
    }
  }, [chainId, internalChains]);

  // 返回链路列表
  const handleBack = () => {
    navigate(`/api/modules/${moduleId}?tab=internal-chains`);
  };

  // 获取 HTTP 方法颜色
  const getMethodColor = (method: string): string => {
    const colorMap: Record<string, string> = {
      GET: 'green',
      POST: 'blue',
      PUT: 'orange',
      DELETE: 'red',
      PATCH: 'purple',
    };
    return colorMap[method] || 'default';
  };

  // 渲染端点详情
  const renderEndpointDetail = (endpoint: any, index: number) => {
    if (!endpoint) return null;
    
    const isStart = index === 0;
    const isEnd = currentChain && index === currentChain.steps.length - 1;
    
    return (
      <div style={{ padding: '12px', background: isStart ? '#f0f9ff' : isEnd ? '#fef2f2' : '#fafafa', borderRadius: '4px' }}>
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Space>
            <Tag color={getMethodColor(endpoint.method)}>{endpoint.method}</Tag>
            <span style={{ fontSize: 12, color: '#999' }}>步骤 {index + 1}</span>
            <span style={{ fontSize: 12, color: '#999' }}>ID: {endpoint.id}</span>
          </Space>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{endpoint.path}</div>
          {endpoint.description && (
            <div style={{ fontSize: 12, color: '#666' }}>{endpoint.description}</div>
          )}
        </Space>
      </div>
    );
  };

  // 渲染流程图节点
  const renderFlowNode = (endpoint: any, index: number) => {
    if (!endpoint) return null;
    
    const isStart = index === 0;
    const isEnd = currentChain && index === currentChain.steps.length - 1;
    const borderColor = isStart ? '#52c41a' : isEnd ? '#ff4d4f' : '#1890ff';
    
    return (
      <div
        key={endpoint.id}
        style={{
          border: `2px solid ${borderColor}`,
          borderRadius: '8px',
          padding: '16px',
          background: '#fff',
          minWidth: '200px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          textAlign: 'center'
        }}
      >
        <Space direction="vertical" size={4}>
          <Tag color={getMethodColor(endpoint.method)}>{endpoint.method}</Tag>
          <div style={{ fontSize: 13, fontWeight: 500 }}>{endpoint.path}</div>
          <div style={{ fontSize: 11, color: '#999' }}>ID: {endpoint.id}</div>
        </Space>
      </div>
    );
  };

  // 编辑链路
  const handleEdit = () => {
    navigate(`/api/modules/${moduleId}/chains/${chainId}/edit`);
  };

  // 删除链路
  const handleDelete = () => {
    message.info('删除功能开发中...');
  };

  // 导出链路
  const handleExport = () => {
    message.info('导出功能开发中...');
  };

  // 分享链接
  const handleShare = () => {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
      message.success('链接已复制到剪贴板');
    }).catch(() => {
      message.error('复制失败');
    });
  };

  if (loading || loadingInternalChains) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (!currentModule) {
    return (
      <div style={{ padding: '24px' }}>
        <Empty description="模块不存在" />
      </div>
    );
  }

  if (!currentChain) {
    return (
      <div style={{ padding: '24px' }}>
        <Empty description="链路不存在" />
      </div>
    );
  }

  return (
    <div style={{ padding: '24px', height: 'calc(100vh - 112px)', overflow: 'auto' }}>
      {/* 返回按钮和标题 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={handleBack}
            >
              返回链路列表
            </Button>
            <h2 style={{ margin: 0 }}>{currentModule.name} - 链路详情</h2>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button icon={<EditOutlined />} onClick={handleEdit}>编辑</Button>
            <Button icon={<DeleteOutlined />} danger onClick={handleDelete}>删除</Button>
            <Button icon={<DownloadOutlined />} onClick={handleExport}>导出</Button>
            <Button icon={<ShareAltOutlined />} onClick={handleShare}>分享</Button>
          </Space>
        </Col>
      </Row>

      {/* 链路概览 */}
      <Card style={{ marginBottom: 24 }}>
        <Descriptions bordered column={3}>
          <Descriptions.Item label="链路ID">{currentChain.chain_id}</Descriptions.Item>
          <Descriptions.Item label="所属模块">{currentModule.name}</Descriptions.Item>
          <Descriptions.Item label="步骤数">{currentChain.step_count}</Descriptions.Item>
          <Descriptions.Item label="起点接口" span={2}>
            {currentChain.start_endpoint ? (
              <Space>
                <Tag color={getMethodColor(currentChain.start_endpoint.method)}>
                  {currentChain.start_endpoint.method}
                </Tag>
                <span>{currentChain.start_endpoint.path}</span>
                <span style={{ color: '#999' }}>(ID: {currentChain.start_endpoint.id})</span>
              </Space>
            ) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="终点接口">
            {currentChain.end_endpoint ? (
              <Space>
                <Tag color={getMethodColor(currentChain.end_endpoint.method)}>
                  {currentChain.end_endpoint.method}
                </Tag>
                <span>{currentChain.end_endpoint.path}</span>
                <span style={{ color: '#999' }}>(ID: {currentChain.end_endpoint.id})</span>
              </Space>
            ) : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 流程图可视化 */}
      <Card title="流程图可视化" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', flexWrap: 'wrap', padding: '24px' }}>
          {currentChain.steps.map((endpoint: any, index: number) => (
            <React.Fragment key={endpoint.id}>
              {renderFlowNode(endpoint, index)}
              {index < currentChain.steps.length - 1 && (
                <div style={{ 
                  width: '40px', 
                  height: '2px', 
                  background: '#d9d9d9',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <div style={{ 
                    width: '0', 
                    height: '0', 
                    borderTop: '5px solid transparent',
                    borderBottom: '5px solid transparent',
                    borderLeft: '8px solid #d9d9d9'
                  }} />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </Card>

      {/* 详细步骤列表 */}
      <Card title="详细步骤列表">
        <Timeline>
          {currentChain.steps.map((endpoint: any, index: number) => (
            <Timeline.Item
              key={endpoint.id}
              color={index === 0 ? 'green' : index === currentChain.steps.length - 1 ? 'red' : 'blue'}
            >
              {renderEndpointDetail(endpoint, index)}
            </Timeline.Item>
          ))}
        </Timeline>
      </Card>
    </div>
  );
};

export default ChainDetail;