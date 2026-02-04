/**
 * 跨模块组合标签页组件
 */
import React, { useEffect, useState } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Modal,
  message,
  Form,
  Input,
  Descriptions,
  Steps,
  Tag,
  Empty,
  Select,
  Alert,
  Tooltip
} from 'antd';
import {
  PlusOutlined,
  EyeOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ArrowRightOutlined
} from '@ant-design/icons';
import { useScenarioStore } from '../../../store/scenario';
import type { ModuleChain, AnalysisStatus } from '../../../types/scenario';

const { TextArea } = Input;
const { Option } = Select;
const { Step } = Steps;

interface ModuleComposeTabProps {
  modules?: any[];
}

const ModuleComposeTab: React.FC<ModuleComposeTabProps> = ({ modules = [] }) => {
  const {
    moduleChains,
    loadingChains,
    loadModuleChains,
    createModuleChain,
    deleteModuleChain
  } = useScenarioStore();

  const [composeVisible, setComposeVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedChain, setSelectedChain] = useState<ModuleChain | null>(null);
  const [composing, setComposing] = useState(false);
  const [composeForm] = Form.useForm();

  useEffect(() => {
    loadModuleChains();
  }, []);

  const handleCompose = async () => {
    try {
      const values = await composeForm.validateFields();
      const { chain_name, description, module_chain } = values;

      setComposing(true);
      await createModuleChain({
        chain_name,
        description,
        module_chain
      });

      setComposeVisible(false);
      composeForm.resetFields();
    } catch (error: any) {
      if (error.errorFields) {
        message.error('请填写完整信息');
      }
    } finally {
      setComposing(false);
    }
  };

  const viewChainDetail = (chain: ModuleChain) => {
    setSelectedChain(chain);
    setDetailVisible(true);
  };

  const deleteChain = async (chainId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个模块链路吗？',
      onOk: async () => {
        try {
          await deleteModuleChain(chainId);
        } catch (error) {
          // Error already handled in store
        }
      },
    });
  };

  const chainColumns = [
    {
      title: '链路名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong>{text}</strong>
    },
    {
      title: '模块链路',
      dataIndex: 'group_names',
      key: 'group_names',
      render: (names: string[]) => (
        <Space>
          {names.map((name, index) => (
            <React.Fragment key={name}>
              <Tag color="blue">{name}</Tag>
              {index < names.length - 1 && <ArrowRightOutlined />}
            </React.Fragment>
          ))}
        </Space>
      )
    },
    {
      title: '接口数量',
      dataIndex: 'endpoint_count',
      key: 'endpoint_count',
      width: 100
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString('zh-CN')
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: ModuleChain) => (
        <Space size="small">
          <Button type="link" icon={<EyeOutlined />} onClick={() => viewChainDetail(record)}>
            详情
          </Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => deleteChain(record.id)}>
            删除
          </Button>
        </Space>
      )
    }
  ];

  return (
    <>
      <Card
        title="跨模块组合"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setComposeVisible(true)}
          >
            组合新场景
          </Button>
        }
      >
        <Table
          columns={chainColumns}
          dataSource={moduleChains}
          rowKey="id"
          loading={loadingChains}
          pagination={{ pageSize: 20 }}
        />
      </Card>

      {/* 组合场景弹窗 */}
      <Modal
        title="组合跨模块场景"
        open={composeVisible}
        onOk={handleCompose}
        onCancel={() => {
          setComposeVisible(false);
          composeForm.resetFields();
        }}
        confirmLoading={composing}
        width={800}
      >
        <Form
          form={composeForm}
          layout="vertical"
          initialValues={{
            module_chain: []
          }}
        >
          <Form.Item
            label="链路名称"
            name="chain_name"
            rules={[{ required: true, message: '请输入链路名称' }]}
          >
            <Input placeholder="例如：用户下单支付流程" />
          </Form.Item>

          <Form.Item
            label="描述"
            name="description"
          >
            <TextArea rows={3} placeholder="请输入场景描述" />
          </Form.Item>

          <Form.Item
            label="选择模块链路"
            name="module_chain"
            rules={[{ required: true, message: '请选择至少一个模块' }]}
          >
            <Select
              mode="multiple"
              placeholder="请选择模块（按执行顺序）"
              style={{ width: '100%' }}
            >
              {modules
                .filter((m: any) => m.analysis_status === 'completed')
                .map((module: any) => (
                  <Option key={module.id} value={module.id}>
                    {module.name}
                  </Option>
                ))}
            </Select>
          </Form.Item>

          {modules.filter((m: any) => m.analysis_status !== 'completed').length > 0 && (
            <Alert
              message="部分模块未完成分析"
              description="只有已完成分析的模块才能参与跨模块场景组合"
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}
        </Form>

        <Alert
          message="提示"
          description="模块的执行顺序将按照您选择的顺序进行，系统会自动识别模块间的数据传递关系"
          type="info"
          showIcon
        />
      </Modal>

      {/* 链路详情弹窗 */}
      <Modal
        title={`链路详情 - ${selectedChain?.name}`}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedChain && (
          <>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="链路名称">{selectedChain.name}</Descriptions.Item>
              <Descriptions.Item label="接口数量">{selectedChain.endpoint_count}</Descriptions.Item>
              <Descriptions.Item label="模块数量">{selectedChain.group_count}</Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(selectedChain.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label="描述" span={2}>
                {selectedChain.description || '无'}
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 24 }}>
              <h4>模块执行顺序</h4>
              <Steps
                direction="vertical"
                current={-1}
                items={selectedChain.group_names.map((name, index) => ({
                  title: name,
                  description: `步骤 ${index + 1}`,
                  icon: <CheckCircleOutlined />
                }))}
              />
            </div>
          </>
        )}
      </Modal>
    </>
  );
};

export default ModuleComposeTab;