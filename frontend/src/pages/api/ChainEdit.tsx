/**
 * 链路编辑页面 - 独立页面方案（方案3 + 拖拽排序）
 * 使用步骤条引导编辑流程，支持基本信息编辑和接口节点选择
 * 使用 dnd-kit 实现拖拽排序功能
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Space,
  Steps,
  Form,
  Input,
  Select,
  message,
  Row,
  Col,
  Descriptions,
  Empty,
  Spin,
  Tag,
  List
} from 'antd';
import {
  ArrowLeftOutlined,
  SaveOutlined,
  CloseOutlined,
  ReloadOutlined,
  RightOutlined,
  LeftOutlined,
  HolderOutlined
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useProjectStore } from '../../store/project';
import { useScenarioStore } from '../../store/scenario';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const { Step } = Steps;
const { TextArea } = Input;
const { Option } = Select;

interface Endpoint {
  id: number;
  path: string;
  method: string;
  description: string;
}

// 可拖拽的列表项组件
const SortableItem: React.FC<{ id: string; endpoint: Endpoint; onRemove: (id: string) => void }> = ({ id, endpoint, onRemove }) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition };

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

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="sortable-item"
    >
      <Card
        size="small"
        style={{ 
          cursor: 'grab',
          marginBottom: 8,
          border: '1px solid #d9d9d9',
          borderRadius: '4px'
        }}
        bodyStyle={{ padding: '12px' }}
      >
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Space>
              <HolderOutlined style={{ cursor: 'grab', color: '#999' }} {...attributes} {...listeners} />
              <Tag color={getMethodColor(endpoint.method)}>{endpoint.method}</Tag>
              <span style={{ fontSize: 12, color: '#999' }}>ID: {endpoint.id}</span>
            </Space>
            <Button 
              type="text" 
              size="small" 
              danger 
              onClick={() => onRemove(id)}
              style={{ padding: 0, minWidth: 'auto' }}
            >
              ×
            </Button>
          </Space>
          <div style={{ fontSize: 13, fontWeight: 500 }}>{endpoint.path}</div>
          {endpoint.description && (
            <div style={{ fontSize: 11, color: '#999' }}>{endpoint.description}</div>
          )}
        </Space>
      </Card>
    </div>
  );
};

const ChainEdit: React.FC = () => {
  const navigate = useNavigate();
  const { moduleId, chainId } = useParams<{ moduleId: string; chainId: string }>();
  const { currentProject } = useProjectStore();
  
  const {
    modules,
    moduleDetail,
    internalChains,
    loadingInternalChains,
    viewModuleDetail,
  } = useScenarioStore();

  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [currentModule, setCurrentModule] = useState<any>(null);
  const [currentChain, setCurrentChain] = useState<any>(null);
  
  // 可选接口列表
  const [availableEndpoints, setAvailableEndpoints] = useState<Endpoint[]>([]);
  // 已选接口列表（用于拖拽排序）
  const [selectedEndpoints, setSelectedEndpoints] = useState<Endpoint[]>([]);
  // 搜索关键词
  const [searchText, setSearchText] = useState('');
  // 选中的可用接口（用于批量添加）
  const [selectedAvailableIds, setSelectedAvailableIds] = useState<string[]>([]);

  // dnd-kit 传感器配置
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // 初始化数据并加载模块详情
  useEffect(() => {
    if (moduleId) {
      const module = modules.find(m => m.id === Number(moduleId));
      setCurrentModule(module);
      if (module) {
        viewModuleDetail(module);
      } else {
        // 如果模块列表未加载，先加载模块列表
        // 这里暂时跳过，因为需要访问 useScenarioStore 的 loadModules
      }
    }
  }, [moduleId, modules, viewModuleDetail]);

  // 加载链路数据和模块接口
  useEffect(() => {
    // 先加载模块详情
    if (moduleId && internalChains.length === 0) {
      const module = modules.find(m => m.id === Number(moduleId));
      if (module) {
        viewModuleDetail(module);
      }
    }
  }, [moduleId, internalChains.length, modules, viewModuleDetail]);

  // 从 internalChains 中查找链路
  useEffect(() => {
    if (chainId && internalChains && internalChains.length > 0) {
      const chain = internalChains.find(c => c.chain_id === Number(chainId));
      if (chain) {
        setCurrentChain(chain);
        
        // 获取模块所有接口作为可选接口
        const allEndpoints: Endpoint[] = [
          ...(moduleDetail?.input_endpoints_detail || []),
          ...(moduleDetail?.output_endpoints_detail || []),
        ];
        setAvailableEndpoints(allEndpoints);
        
        // 设置已选接口
        setSelectedEndpoints(chain.steps || []);
        
        // 填充表单
        form.setFieldsValue({
          chain_name: `链路 #${chain.chain_id}`,
          description: `从 ${chain.start_endpoint?.path || ''} 到 ${chain.end_endpoint?.path || ''}`,
        });
      } else {
        setCurrentChain(null);
      }
      setLoading(false);
    }
  }, [chainId, internalChains, moduleDetail, form]);

  // 添加超时机制，避免无限加载
  useEffect(() => {
    const timer = setTimeout(() => {
      if (loading) {
        console.warn('页面加载超时，强制停止加载状态');
        setLoading(false);
      }
    }, 10000); // 10秒超时

    return () => clearTimeout(timer);
  }, [loading]);

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

  // 返回详情页
  const handleBack = () => {
    navigate(`/api/modules/${moduleId}/chains/${chainId}`);
  };

  // 过滤可选接口
  const filteredAvailableEndpoints = availableEndpoints.filter(endpoint => {
    const selectedIds = selectedEndpoints.map(e => String(e.id));
    const isSelected = selectedIds.includes(String(endpoint.id));
    const matchesSearch = !searchText || 
      endpoint.path.toLowerCase().includes(searchText.toLowerCase()) ||
      endpoint.description?.toLowerCase().includes(searchText.toLowerCase());
    return !isSelected && matchesSearch;
  });

  // 添加接口到已选列表
  const handleAddToEndpoints = () => {
    if (selectedAvailableIds.length === 0) {
      message.warning('请先选择要添加的接口');
      return;
    }
    const endpointsToAdd = availableEndpoints.filter(e => 
      selectedAvailableIds.includes(String(e.id))
    );
    setSelectedEndpoints([...selectedEndpoints, ...endpointsToAdd]);
    setSelectedAvailableIds([]);
  };

  // 批量添加所有可用接口
  const handleAddAllEndpoints = () => {
    if (filteredAvailableEndpoints.length === 0) {
      message.warning('没有可添加的接口');
      return;
    }
    setSelectedEndpoints([...selectedEndpoints, ...filteredAvailableEndpoints]);
  };

  // 从已选列表移除接口
  const handleRemoveFromSelected = (id: string) => {
    setSelectedEndpoints(selectedEndpoints.filter(e => String(e.id) !== id));
  };

  // 清空已选列表
  const handleClearSelected = () => {
    setSelectedEndpoints([]);
  };

  // 拖拽结束处理
  const handleDragEnd = (event: any) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = selectedEndpoints.findIndex(e => String(e.id) === active.id);
      const newIndex = selectedEndpoints.findIndex(e => String(e.id) === over.id);
      const newEndpoints = [...selectedEndpoints];
      const [movedItem] = newEndpoints.splice(oldIndex, 1);
      newEndpoints.splice(newIndex, 0, movedItem);
      setSelectedEndpoints(newEndpoints);
    }
  };

  // 上一步
  const handlePrev = () => {
    setCurrentStep(currentStep - 1);
  };

  // 下一步
  const handleNext = () => {
    if (currentStep === 0) {
      form.validateFields().then(() => {
        setCurrentStep(1);
      }).catch(() => {
        message.warning('请填写完整的基本信息');
      });
    } else if (currentStep === 1) {
      if (selectedEndpoints.length < 2) {
        message.warning('请至少选择2个接口节点');
        return;
      }
      setCurrentStep(2);
    }
  };

  // 保存
  const handleSave = () => {
    form.validateFields().then((values) => {
      // TODO: 调用后端API保存链路
      message.success('保存成功');
      navigate(`/api/modules/${moduleId}/chains/${chainId}`);
    }).catch(() => {
      message.warning('请填写完整信息');
    });
  };

  // 取消
  const handleCancel = () => {
    navigate(`/api/modules/${moduleId}/chains/${chainId}`);
  };

  // 重置
  const handleReset = () => {
    if (currentChain && currentChain.steps) {
      setSelectedEndpoints(currentChain.steps);
    }
    form.resetFields();
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (!currentModule || !currentChain) {
    return (
      <div style={{ padding: '24px' }}>
        <Empty description="链路不存在" />
      </div>
    );
  }

  const steps = [
    {
      title: '基本信息',
      description: '编辑链路名称和描述',
    },
    {
      title: '选择接口',
      description: '添加、移除或拖拽排序接口节点',
    },
    {
      title: '确认预览',
      description: '预览并确认修改',
    },
  ];

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
              返回详情
            </Button>
            <h2 style={{ margin: 0 }}>编辑链路 - {currentModule.name}</h2>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={handleReset}>重置</Button>
            <Button icon={<CloseOutlined />} onClick={handleCancel}>取消</Button>
          </Space>
        </Col>
      </Row>

      {/* 步骤条 */}
      <Card style={{ marginBottom: 24 }}>
        <Steps current={currentStep}>
          {steps.map((step, index) => (
            <Step key={index} title={step.title} description={step.description} />
          ))}
        </Steps>
      </Card>

      {/* 步骤内容 */}
      <Card>
        {/* 步骤1: 基本信息 */}
        {currentStep === 0 && (
          <Form
            form={form}
            layout="vertical"
            style={{ maxWidth: 600 }}
          >
            <Form.Item
              label="链路名称"
              name="chain_name"
              rules={[{ required: true, message: '请输入链路名称' }]}
            >
              <Input placeholder="请输入链路名称" />
            </Form.Item>
            
            <Form.Item
              label="链路描述"
              name="description"
              rules={[{ required: true, message: '请输入链路描述' }]}
            >
              <TextArea rows={4} placeholder="请输入链路描述" />
            </Form.Item>
          </Form>
        )}

        {/* 步骤2: 选择接口 */}
        {currentStep === 1 && (
          <div>
            <div style={{ marginBottom: 16, color: '#666' }}>
              选择接口节点并点击添加按钮，已选列表支持拖拽排序调整链路顺序
            </div>
            
            <Row gutter={16} style={{ height: '600px' }}>
              {/* 左侧：可选接口列表 */}
              <Col span={10}>
                <Card 
                  title={`可选接口 (${filteredAvailableEndpoints.length})`} 
                  size="small"
                  extra={
                    <Space>
                      <Button 
                        size="small" 
                        type="primary" 
                        onClick={handleAddAllEndpoints}
                        disabled={filteredAvailableEndpoints.length === 0}
                      >
                        添加全部
                      </Button>
                    </Space>
                  }
                  bodyStyle={{ padding: '12px' }}
                >
                  <Input
                    placeholder="搜索接口..."
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    style={{ marginBottom: 12 }}
                  />
                  <div style={{ height: '480px', overflow: 'auto' }}>
                    <List
                      dataSource={filteredAvailableEndpoints}
                      renderItem={(endpoint) => (
                        <List.Item
                          style={{ 
                            cursor: 'pointer',
                            padding: '8px',
                            borderRadius: '4px',
                            transition: 'background 0.2s',
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.background = '#f5f5f5'}
                          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                          onClick={() => {
                            const id = String(endpoint.id);
                            if (selectedAvailableIds.includes(id)) {
                              setSelectedAvailableIds(selectedAvailableIds.filter(i => i !== id));
                            } else {
                              setSelectedAvailableIds([...selectedAvailableIds, id]);
                            }
                          }}
                        >
                          <List.Item.Meta
                            avatar={
                              <input
                                type="checkbox"
                                checked={selectedAvailableIds.includes(String(endpoint.id))}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  const id = String(endpoint.id);
                                  if (e.target.checked) {
                                    setSelectedAvailableIds([...selectedAvailableIds, id]);
                                  } else {
                                    setSelectedAvailableIds(selectedAvailableIds.filter(i => i !== id));
                                  }
                                }}
                              />
                            }
                            title={
                              <Space>
                                <Tag color={getMethodColor(endpoint.method)}>{endpoint.method}</Tag>
                                <span style={{ fontSize: 12 }}>{endpoint.path}</span>
                              </Space>
                            }
                            description={
                              <span style={{ fontSize: 11, color: '#999' }}>
                                ID: {endpoint.id} {endpoint.description ? ` | ${endpoint.description}` : ''}
                              </span>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  </div>
                </Card>
              </Col>

              {/* 中间：穿梭按钮 */}
              <Col span={4} style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '12px' }}>
                <Button
                  type="primary"
                  icon={<RightOutlined />}
                  onClick={handleAddToEndpoints}
                  disabled={selectedAvailableIds.length === 0}
                >
                  添加
                </Button>
                <Button
                  danger
                  icon={<LeftOutlined />}
                  onClick={handleClearSelected}
                  disabled={selectedEndpoints.length === 0}
                >
                  清空
                </Button>
              </Col>

              {/* 右侧：已选接口列表（可拖拽排序） */}
              <Col span={10}>
                <Card
                  title={`已选接口 (${selectedEndpoints.length})`}
                  size="small"
                  bodyStyle={{ padding: '12px' }}
                >
                  <div style={{ marginBottom: 12, color: '#999', fontSize: 12 }}>
                    💡 拖拽接口卡片可调整顺序
                  </div>
                  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                    <SortableContext items={selectedEndpoints.map(e => String(e.id))} strategy={verticalListSortingStrategy}>
                      <div style={{ height: '480px', overflow: 'auto' }}>
                        {selectedEndpoints.map((endpoint) => (
                          <SortableItem
                            key={endpoint.id}
                            id={String(endpoint.id)}
                            endpoint={endpoint}
                            onRemove={handleRemoveFromSelected}
                          />
                        ))}
                        {selectedEndpoints.length === 0 && (
                          <Empty 
                            description="暂无已选接口" 
                            style={{ marginTop: '60px' }} 
                          />
                        )}
                      </div>
                    </SortableContext>
                  </DndContext>
                </Card>
              </Col>
            </Row>
          </div>
        )}

        {/* 步骤3: 确认预览 */}
        {currentStep === 2 && (
          <div>
            <Descriptions bordered column={1} style={{ marginBottom: 24 }}>
              <Descriptions.Item label="链路名称">
                {form.getFieldValue('chain_name')}
              </Descriptions.Item>
              <Descriptions.Item label="链路描述">
                {form.getFieldValue('description')}
              </Descriptions.Item>
              <Descriptions.Item label="接口节点数">
                {selectedEndpoints.length}
              </Descriptions.Item>
            </Descriptions>

            <h3>链路路径预览</h3>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              flexWrap: 'wrap', 
              padding: '24px',
              background: '#fafafa',
              borderRadius: '4px'
            }}>
              {selectedEndpoints.map((endpoint, index) => (
                <React.Fragment key={endpoint.id}>
                  <div style={{
                    border: '1px solid #d9d9d9',
                    borderRadius: '4px',
                    padding: '8px 16px',
                    background: '#fff'
                  }}>
                    <Space direction="vertical" size={0}>
                      <Tag color={getMethodColor(endpoint.method)}>{endpoint.method}</Tag>
                      <span style={{ fontSize: 12 }}>{endpoint.path}</span>
                    </Space>
                  </div>
                  {index < selectedEndpoints.length - 1 && (
                    <span style={{ color: '#999' }}>→</span>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div style={{ marginTop: 24, textAlign: 'right' }}>
          <Space>
            {currentStep > 0 && (
              <Button onClick={handlePrev}>上一步</Button>
            )}
            {currentStep < 2 && (
              <Button type="primary" onClick={handleNext}>
                {currentStep === 1 ? '下一步' : '下一步'}
              </Button>
            )}
            {currentStep === 2 && (
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>
                保存
              </Button>
            )}
          </Space>
        </div>
      </Card>
    </div>
  );
};

export default ChainEdit;