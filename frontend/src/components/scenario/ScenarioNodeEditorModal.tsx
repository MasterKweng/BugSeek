import React from 'react'
import { Checkbox, Form, Input, InputNumber, Modal, Select, Space, Switch, Tooltip } from 'antd'
import type { FormInstance } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'

import type { ScenarioNode } from '../../types/scenario'

interface ApiDefinitionOption {
  id: number
  method: string
  path: string
  summary?: string
}

export interface NodeFormValues {
  node_key: string
  node_name?: string
  node_type: string
  ref_type?: string
  ref_id?: number
  step_order?: number
  depends_on?: string[]
  input_mapping?: string
  extract_rules?: string
  assertion_overrides?: string
  timeout_seconds?: number | null
  retry_count?: number
  continue_on_failure?: boolean
  is_enabled?: boolean
  extra_config?: string
}

interface ScenarioNodeEditorModalProps {
  open: boolean
  editingNode: ScenarioNode | null
  form: FormInstance<NodeFormValues>
  nodeType?: string
  nodes: ScenarioNode[]
  apiDefinitions: ApiDefinitionOption[]
  defaultExtra: string
  nodeTypes: string[]
  onOk: () => void
  onCancel: () => void
}

const { TextArea } = Input

const nodeTypeLabelMap: Record<string, string> = {
  api_call: 'API 调用',
  condition: '条件判断',
  wait: '等待/轮询',
  script: '脚本处理',
}

const refTypeLabelMap: Record<string, string> = {
  api_definition: '接口定义',
  api_case: '测试用例',
}

const withHint = (label: string, hint: string) => (
  <Space size={4}>
    <span>{label}</span>
    <Tooltip title={hint}>
      <QuestionCircleOutlined />
    </Tooltip>
  </Space>
)

const ScenarioNodeEditorModal: React.FC<ScenarioNodeEditorModalProps> = ({
  open,
  editingNode,
  form,
  nodeType,
  nodes,
  apiDefinitions,
  defaultExtra,
  nodeTypes,
  onOk,
  onCancel,
}) => (
  <Modal
    title={editingNode ? '编辑节点' : '添加节点'}
    open={open}
    onOk={onOk}
    onCancel={onCancel}
    width={760}
  >
    <Form
      form={form}
      layout="vertical"
      initialValues={{
        node_type: 'api_call',
        ref_type: 'api_definition',
        retry_count: 0,
        continue_on_failure: false,
        is_enabled: true,
      }}
    >
      <Space align="start" wrap style={{ display: 'flex' }}>
        <Form.Item name="node_key" label="节点标识" rules={[{ required: true, message: '请输入节点标识' }]}>
          <Input disabled={Boolean(editingNode)} style={{ width: 200 }} />
        </Form.Item>
        <Form.Item name="node_name" label="节点名称" rules={[{ required: true, message: '请输入节点名称' }]}>
          <Input style={{ width: 200 }} />
        </Form.Item>
        <Form.Item name="step_order" label="执行顺序">
          <InputNumber min={1} style={{ width: 120 }} />
        </Form.Item>
        <Form.Item name="is_enabled" label="启用" valuePropName="checked">
          <Checkbox />
        </Form.Item>
      </Space>

      <Space align="start" wrap style={{ display: 'flex' }}>
        <Form.Item name="node_type" label="节点类型" rules={[{ required: true, message: '请选择节点类型' }]}>
          <Select
            style={{ width: 160 }}
            options={nodeTypes.map((item) => ({ label: nodeTypeLabelMap[item] || item, value: item }))}
          />
        </Form.Item>
        {nodeType === 'api_call' ? (
          <>
            <Form.Item name="ref_type" label="引用类型" rules={[{ required: true, message: '请选择引用类型' }]}>
              <Select
                style={{ width: 180 }}
                options={[
                  { label: refTypeLabelMap.api_definition, value: 'api_definition' },
                  { label: refTypeLabelMap.api_case, value: 'api_case' },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="ref_id"
              label="接口定义 / 测试用例"
              rules={[{ required: true, message: '请选择接口定义或测试用例' }]}
            >
              <Select
                showSearch
                optionFilterProp="label"
                style={{ width: 320 }}
                options={apiDefinitions.map((item) => ({
                  label: `${item.method} ${item.path}${item.summary ? ` - ${item.summary}` : ''}`,
                  value: item.id,
                }))}
              />
            </Form.Item>
          </>
        ) : (
          <Form.Item
            name="extra_config"
            label={withHint('节点配置（JSON）', '条件、等待和脚本节点都通过这里填写专属配置。')}
          >
            <TextArea
              rows={4}
              style={{ width: 520 }}
              placeholder='例如：{"expression":{"==":[{"var":"vars.status"},"success"]}}'
            />
          </Form.Item>
        )}
      </Space>

      <Space align="start" wrap style={{ display: 'flex' }}>
        <Form.Item name="depends_on" label="依赖节点">
          <Select
            mode="multiple"
            allowClear
            style={{ width: 320 }}
            options={nodes
              .filter((item) => item.node_key !== editingNode?.node_key)
              .map((item) => ({
                label: `${item.node_name || item.node_key} (${item.node_key})`,
                value: item.node_key,
              }))}
          />
        </Form.Item>
        <Form.Item name="timeout_seconds" label="超时（秒）">
          <InputNumber min={1} style={{ width: 140 }} />
        </Form.Item>
        <Form.Item name="retry_count" label="重试次数">
          <InputNumber min={0} style={{ width: 140 }} />
        </Form.Item>
        <Form.Item name="continue_on_failure" label="失败后继续" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Space>

      <Form.Item
        name="input_mapping"
        label={withHint('输入映射（JSON）', '定义本节点如何从上下文或前序节点结果中组装输入。')}
      >
        <TextArea rows={4} />
      </Form.Item>
      <Form.Item
        name="extract_rules"
        label={withHint('提取规则（JSON）', '定义本节点如何从响应或输出中提取变量。')}
      >
        <TextArea rows={4} />
      </Form.Item>
      <Form.Item
        name="assertion_overrides"
        label={withHint('断言覆盖（JSON）', '覆盖默认断言规则，适合临时调整校验逻辑。')}
      >
        <TextArea rows={4} />
      </Form.Item>
      {nodeType === 'api_call' ? (
        <Form.Item name="extra_config" label={withHint('额外配置（JSON）', '用于接口节点的选例策略等高级配置。')}>
          <TextArea rows={4} placeholder={defaultExtra} />
        </Form.Item>
      ) : null}
    </Form>
  </Modal>
)

export default ScenarioNodeEditorModal
