import React, { useMemo, useState } from 'react'
import { Form, Modal, Select, Space, Typography, message } from 'antd'
import type { Version } from '../../types'

const { Text } = Typography

interface CloneMappingsModalProps {
  open: boolean
  versions: Version[]
  currentVersionId?: number
  loading?: boolean
  onClose: () => void
  onSubmit: (sourceVersionId: number, targetVersionId: number) => Promise<void>
}

const CloneMappingsModal: React.FC<CloneMappingsModalProps> = ({
  open,
  versions,
  currentVersionId,
  loading = false,
  onClose,
  onSubmit,
}) => {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  const sourceOptions = useMemo(
    () => versions.filter((item) => item.id !== currentVersionId),
    [currentVersionId, versions],
  )

  const currentVersion = useMemo(
    () => versions.find((item) => item.id === currentVersionId),
    [currentVersionId, versions],
  )

  const handleOk = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      await onSubmit(values.sourceVersionId, values.targetVersionId)
      form.resetFields()
      onClose()
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }
      message.error(error.message || '克隆映射失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="克隆映射"
      open={open}
      onCancel={onClose}
      onOk={() => void handleOk()}
      confirmLoading={loading || submitting}
      destroyOnClose
    >
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Text type="secondary">
          将其他版本中的字段映射复制到当前治理版本，适合跨版本复用已有治理结果。
        </Text>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ targetVersionId: currentVersionId }}
          preserve={false}
        >
          <Form.Item
            label="源版本"
            name="sourceVersionId"
            rules={[{ required: true, message: '请选择源版本' }]}
          >
            <Select
              options={sourceOptions.map((item) => ({
                value: item.id,
                label: `${item.version_number} (#${item.id})`,
              }))}
              placeholder="选择要复制映射的版本"
            />
          </Form.Item>
          <Form.Item
            label="目标版本"
            name="targetVersionId"
            rules={[{ required: true, message: '请选择目标版本' }]}
          >
            <Select
              options={versions.map((item) => ({
                value: item.id,
                label: `${item.version_number} (#${item.id})`,
              }))}
              placeholder="选择目标版本"
            />
          </Form.Item>
        </Form>
        {currentVersion ? <Text type="secondary">当前版本：{currentVersion.version_number} (#{currentVersion.id})</Text> : null}
      </Space>
    </Modal>
  )
}

export default CloneMappingsModal
