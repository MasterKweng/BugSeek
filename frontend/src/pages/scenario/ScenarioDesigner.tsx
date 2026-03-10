import React, { useState, useEffect } from 'react';
import { Card, Button, Space, Modal, Form, Input, Select, Tag, message } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ArrowRightOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useProjectStore } from '../../store/project';
import api from '../../services/api';
import './ScenarioDesigner.css';

const { Option } = Select;

const ScenarioDesigner: React.FC = () => {
  const navigate = useNavigate();
  const { scenarioId } = useParams();
  const { currentProject, currentVersion } = useProjectStore();
  const [form] = Form.useForm();
  
  const [scenario, setScenario] = useState<any>(null);
  const [nodes, setNodes] = useState<any[]>([]);
  const [apiDefinitions, setApiDefinitions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [nodeModalVisible, setNodeModalVisible] = useState(false);
  const [editingNode, setEditingNode] = useState<any>(null);

  useEffect(() => {
    loadScenario();
    loadApiDefinitions();
  }, [scenarioId]);

  const loadScenario = async () => {
    if (!scenarioId) return;
    
    setLoading(true);
    try {
      const response = await api.get(`/scenarios/${scenarioId}`);
      if (response.code === 0) {
        setScenario(response.data);
        setNodes(response.data.nodes || []);
        form.setFieldsValue({
          name: response.data.name,
          description: response.data.description,
        });
      }
    } catch (error: any) {
      message.error(error.message || '加载场景失败');
    } finally {
      setLoading(false);
    }
  };

  const loadApiDefinitions = async () => {
    if (!currentProject?.id) return;
    
    try {
      const response = await api.get(`/api-definitions?project_id=${currentProject.id}`);
      if (response.code === 0) {
        setApiDefinitions(response.data.items || []);
      }
    } catch (error: any) {
      console.error('加载接口定义失败:', error);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      
      const response = await api.put(`/scenarios/${scenarioId}`, {
        name: values.name,
        description: values.description,
        nodes: nodes,
      });

      if (response.code === 0) {
        message.success('场景保存成功');
        setScenario({ ...scenario, ...values });
      } else {
        message.error(response.message || '保存场景失败');
      }
    } catch (error: any) {
      message.error(error.message || '保存场景失败');
    }
  };

  const handleAddNode = () => {
    setEditingNode(null);
    setNodeModalVisible(true);
  };

  const handleEditNode = (node: any) => {
    setEditingNode(node);
    setNodeModalVisible(true);
  };

  const handleDeleteNode = (nodeKey: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除节点 "${nodeKey}" 吗？`,
      onOk: () => {
        setNodes(nodes.filter(n => n.node_key !== nodeKey));
        message.success('节点已删除');
      },
    });
  };

  const handleNodeModalOk = async () => {
    try {
      const values = await form.validateFields();
      
      if (editingNode) {
        // 更新现有节点
        setNodes(nodes.map(n => 
          n.node_key === editingNode.node_key 
            ? { ...n, ...values }
            : n
        ));
        message.success('节点已更新');
      } else {
        // 添加新节点
        const newNode = {
          node_key: values.node_key,
          node_name: values.node_name,
          node_type: 'api_call',
          ref_type: 'api_definition',
          ref_id: values.ref_id,
          step_order: nodes.length,
          depends_on: values.depends_on || [],
          input_mapping: {},
          extract_rules: {},
          assertion_overrides: {},
          is_enabled: true,
        };
        setNodes([...nodes, newNode]);
        message.success('节点已添加');
      }
      
      setNodeModalVisible(false);
    } catch (error: any) {
      message.error(error.message || '操作失败');
    }
  };

  const handleNodeModalCancel = () => {
    setNodeModalVisible(false);
    form.resetFields();
  };

  return (
    <div className="scenario-designer">
      <Card
        title="场景编排"
        extra={
          <Space>
            <Button onClick={() => navigate(`/scenario/${scenarioId}`)}>
              返回
            </Button>
            <Button type="primary" onClick={handleSave} loading={loading}>
              保存场景
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="场景名称"
            rules={[{ required: true, message: '请输入场景名称' }]}
          >
            <Input placeholder="请输入场景名称" />
          </Form.Item>
          <Form.Item
            name="description"
            label="场景描述"
          >
            <Input.TextArea placeholder="请输入场景描述" rows={3} />
          </Form.Item>
        </Form>

        <div className="nodes-section">
          <div className="nodes-header">
            <h3>场景节点</h3>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleAddNode}>
              添加节点
            </Button>
          </div>

          <div className="nodes-list">
            {nodes.map((node, index) => (
              <Card key={node.node_key} size="small" className="node-card">
                <div className="node-header">
                  <Space>
                    <Tag color="blue">{index + 1}</Tag>
                    <strong>{node.node_name}</strong>
                    <Tag>{node.node_key}</Tag>
                  </Space>
                  <Space>
                    <Button 
                      type="link" 
                      size="small" 
                      icon={<EditOutlined />}
                      onClick={() => handleEditNode(node)}
                    >
                      编辑
                    </Button>
                    <Button 
                      type="link" 
                      size="small" 
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleDeleteNode(node.node_key)}
                    >
                      删除
                    </Button>
                  </Space>
                </div>
                <div className="node-details">
                  <div>类型: {node.node_type}</div>
                  <div>引用: {apiDefinitions.find(d => d.id === node.ref_id)?.path || '未知'}</div>
                  {node.depends_on && node.depends_on.length > 0 && (
                    <div>依赖: {node.depends_on.join(', ')}</div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>

        <Modal
          title={editingNode ? '编辑节点' : '添加节点'}
          open={nodeModalVisible}
          onOk={handleNodeModalOk}
          onCancel={handleNodeModalCancel}
          width={600}
        >
          <Form form={form} layout="vertical">
            <Form.Item
              name="node_key"
              label="节点标识"
              rules={[{ required: true, message: '请输入节点标识' }]}
              initialValue={editingNode?.node_key}
            >
              <Input placeholder="例如: create_user" disabled={!!editingNode} />
            </Form.Item>
            <Form.Item
              name="node_name"
              label="节点名称"
              rules={[{ required: true, message: '请输入节点名称' }]}
              initialValue={editingNode?.node_name}
            >
              <Input placeholder="例如: 创建用户" />
            </Form.Item>
            <Form.Item
              name="ref_id"
              label="选择接口"
              rules={[{ required: true, message: '请选择接口' }]}
              initialValue={editingNode?.ref_id}
            >
              <Select placeholder="请选择接口">
                {apiDefinitions.map(def => (
                  <Option key={def.id} value={def.id}>
                    {def.method} {def.path} - {def.summary}
                  </Option>
                ))}
              </Select>
            </Form.Item>
            <Form.Item
              name="depends_on"
              label="依赖节点"
              initialValue={editingNode?.depends_on || []}
            >
              <Select mode="tags" placeholder="选择依赖的节点">
                {nodes.filter(n => n.node_key !== editingNode?.node_key).map(node => (
                  <Option key={node.node_key} value={node.node_key}>
                    {node.node_name}
                  </Option>
                ))}
              </Select>
            </Form.Item>
          </Form>
        </Modal>
      </Card>
    </div>
  );
};

export default ScenarioDesigner;