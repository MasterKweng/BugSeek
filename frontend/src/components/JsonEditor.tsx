import React, { useState, useCallback } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { json } from '@codemirror/lang-json';
import { oneDark } from '@codemirror/theme-one-dark';
import { Alert, Button, Space, message } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, BgColorsOutlined } from '@ant-design/icons';

interface JsonEditorProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  height?: string;
  readOnly?: boolean;
  label?: string;
  showFormatButton?: boolean;
  showValidateStatus?: boolean;
}

const JsonEditor: React.FC<JsonEditorProps> = ({
  value = '',
  onChange,
  placeholder,
  height = '300px',
  readOnly = false,
  label,
  showFormatButton = true,
  showValidateStatus = true
}) => {
  const [error, setError] = useState<string>('');
  const [isValid, setIsValid] = useState<boolean>(true);

  // 验证 JSON 格式
  const validateJson = useCallback((text: string): boolean => {
    if (!text.trim()) {
      setError('');
      setIsValid(true);
      return true;
    }
    try {
      JSON.parse(text);
      setError('');
      setIsValid(true);
      return true;
    } catch (e: any) {
      setError(`JSON 格式错误: ${e.message}`);
      setIsValid(false);
      return false;
    }
  }, []);

  // 美化 JSON
  const formatJson = useCallback(() => {
    if (!value.trim()) {
      message.warning('没有内容需要格式化');
      return;
    }
    try {
      const parsed = JSON.parse(value);
      const formatted = JSON.stringify(parsed, null, 2);
      onChange?.(formatted);
      validateJson(formatted);
      message.success('JSON 格式化成功');
    } catch (e: any) {
      message.error(`JSON 格式错误，无法美化: ${e.message}`);
    }
  }, [value, onChange, validateJson]);

  // 压缩 JSON
  const minifyJson = useCallback(() => {
    if (!value.trim()) {
      message.warning('没有内容需要压缩');
      return;
    }
    try {
      const parsed = JSON.parse(value);
      const minified = JSON.stringify(parsed);
      onChange?.(minified);
      validateJson(minified);
      message.success('JSON 压缩成功');
    } catch (e: any) {
      message.error(`JSON 格式错误，无法压缩: ${e.message}`);
    }
  }, [value, onChange, validateJson]);

  const handleChange = useCallback((newValue: string) => {
    onChange?.(newValue);
    validateJson(newValue);
  }, [onChange, validateJson]);

  return (
    <div>
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        {label && (
          <span style={{ fontWeight: 500, fontSize: 14 }}>{label}</span>
        )}
        
        {showValidateStatus && (
          <span style={{ fontSize: 12, color: isValid ? '#52c41a' : '#ff4d4f', display: 'flex', alignItems: 'center', gap: 4 }}>
            {isValid ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            {isValid ? 'JSON 格式正确' : 'JSON 格式错误'}
          </span>
        )}
      </div>

      {/* 编辑器 */}
      <div style={{ border: error ? '2px solid #ff4d4f' : '1px solid #d9d9d9', borderRadius: 6, overflow: 'hidden' }}>
        <CodeMirror
          value={value}
          height={height}
          theme={oneDark}
          extensions={[json()]}
          onChange={handleChange}
          readOnly={readOnly}
          placeholder={placeholder}
          style={{
            fontSize: 13,
            fontFamily: 'Fira Code, Consolas, Monaco, monospace'
          }}
        />
      </div>

      {/* 错误提示 */}
      {error && (
        <Alert
          message={error}
          type="error"
          showIcon
          style={{ marginTop: 8 }}
        />
      )}

      {/* 操作按钮 */}
      {showFormatButton && !readOnly && (
        <Space style={{ marginTop: 8 }}>
          <Button
            size="small"
            icon={<BgColorsOutlined />}
            onClick={formatJson}
          >
            美化
          </Button>
          <Button
            size="small"
            onClick={minifyJson}
          >
            压缩
          </Button>
        </Space>
      )}
    </div>
  );
};

export default JsonEditor;