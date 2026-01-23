import React, { useState } from 'react';
import { Modal, Form, Input, Select, Upload, Button, Radio, Checkbox, message, Space, Spin } from 'antd';
import { UploadOutlined, LinkOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useProjectStore } from '../../../store/project';

const { Option } = Select;
const { Dragger } = Upload;

interface ImportModalProps {
  visible: boolean;
  onCancel: () => void;
  onImport: (data: any) => Promise<void>;
  loading?: boolean;
}

const ImportModal: React.FC<ImportModalProps> = ({ visible, onCancel, onImport, loading }) => {
  const [form] = Form.useForm();
  const { currentProject, currentVersion } = useProjectStore();
  const [importType, setImportType] = useState<'file' | 'url'>('file');
  const [fileList, setFileList] = useState<any[]>([]);
  const [url, setUrl] = useState('');
  const [urlValid, setUrlValid] = useState<boolean | null>(null);

  const handleImportTypeChange = (e: any) => {
    setImportType(e.target.value);
    setFileList([]);
    setUrl('');
    setUrlValid(null);
  };

  const handleUploadChange = ({ fileList: newFileList }: any) => {
    setFileList(newFileList);
  };

  const beforeUpload = (file: any) => {
    const validTypes = ['application/json', 'application/x-yaml', 'text/yaml', 'text/plain'];
    const validExtensions = ['.json', '.yaml', '.yml'];
    const fileName = file?.name || '';
    const fileExtension = fileName.substring(fileName.lastIndexOf('.')).toLowerCase();

    if (!validExtensions.includes(fileExtension)) {
      message.error('仅支持 JSON、YAML 格式的文件');
      return Upload.LIST_IGNORE;
    }

    if (file?.size > 5 * 1024 * 1024) {
      message.error('文件大小不能超过 5MB');
      return Upload.LIST_IGNORE;
    }

    return false;
  };

  const handleTestUrl = async () => {
    if (!url) {
      message.warning('请输入 URL');
      return;
    }

    try {
      const urlObj = new URL(url);
      if (!urlObj.protocol.startsWith('http')) {
        message.error('URL 必须以 http:// 或 https:// 开头');
        setUrlValid(false);
        return;
      }

      message.loading({ content: '测试连接中...', key: 'testUrl' });

      // 模拟测试连接
      await new Promise(resolve => setTimeout(resolve, 1000));

      message.success({ content: '连接成功', key: 'testUrl' });
      setUrlValid(true);
    } catch (error) {
      message.error({ content: 'URL 格式错误', key: 'testUrl' });
      setUrlValid(false);
    }
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();

      if (!currentProject || !currentVersion) {
        message.error('请先选择项目和版本');
        return;
      }

      if (importType === 'file') {
        if (fileList.length === 0) {
          message.warning('请选择文件');
          return;
        }
        await onImport({
          ...values,
          importType,
          file: fileList[0].originFileObj,
          project_id: currentProject.id,
          version_id: currentVersion.id,
        });
      } else {
        if (!url) {
          message.warning('请输入 URL');
          return;
        }
        if (!urlValid) {
          message.warning('请先测试连接');
          return;
        }
        await onImport({
          ...values,
          importType,
          url,
          project_id: currentProject.id,
          version_id: currentVersion.id,
        });
      }

      // 重置表单
      form.resetFields();
      setFileList([]);
      setUrl('');
      setUrlValid(null);
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    setFileList([]);
    setUrl('');
    setUrlValid(null);
    onCancel();
  };

  return (
    <Modal
      title="导入文档"
      open={visible}
      onOk={handleOk}
      onCancel={handleCancel}
      confirmLoading={loading}
      width={600}
      destroyOnClose
    >
      <Spin spinning={loading}>
        <Form form={form} layout="vertical">
          <Form.Item label="导入方式">
            <Radio.Group value={importType} onChange={handleImportTypeChange}>
              <Radio value="file">上传文件</Radio>
              <Radio value="url">URL 导入</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            label="文档类型"
            name="sourceType"
            rules={[{ required: true, message: '请选择文档类型' }]}
            initialValue="swagger"
          >
            <Select placeholder="请选择文档类型">
              <Option value="swagger">Swagger/OpenAPI</Option>
              <Option value="yapi">YApi</Option>
              <Option value="postman">Postman Collection</Option>
            </Select>
          </Form.Item>

          {importType === 'file' ? (
            <Form.Item label="选择文件">
              <Dragger
                fileList={fileList}
                onChange={handleUploadChange}
                beforeUpload={beforeUpload}
                maxCount={1}
                accept=".json,.yaml,.yml"
              >
                <p className="ant-upload-drag-icon">
                  <UploadOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
                <p className="ant-upload-hint">支持 JSON、YAML 格式，最大 5MB</p>
              </Dragger>
            </Form.Item>
          ) : (
            <Form.Item label="文档 URL">
              <Space.Compact style={{ width: '100%' }}>
                <Input
                  placeholder="https://api.example.com/swagger.json"
                  value={url}
                  onChange={(e) => {
                    setUrl(e.target.value);
                    setUrlValid(null);
                  }}
                  prefix={<LinkOutlined />}
                />
                <Button
                  type="primary"
                  onClick={handleTestUrl}
                  disabled={!url}
                >
                  测试连接
                </Button>
              </Space.Compact>
              {urlValid === true && (
                <div style={{ color: '#52c41a', marginTop: 8 }}>
                  <CheckCircleOutlined /> 连接成功
                </div>
              )}
            </Form.Item>
          )}

          <Form.Item
            label="文档名称"
            name="name"
            rules={[{ required: true, message: '请输入文档名称' }]}
          >
            <Input placeholder="请输入文档名称" />
          </Form.Item>

          <Form.Item
            label="版本号"
            name="version"
            initialValue="1.0.0"
          >
            <Input placeholder="1.0.0" />
          </Form.Item>

          <Form.Item
            name="autoParse"
            valuePropName="checked"
            initialValue={true}
          >
            <Checkbox>导入后自动解析接口</Checkbox>
          </Form.Item>
        </Form>
      </Spin>
    </Modal>
  );
};

export default ImportModal;