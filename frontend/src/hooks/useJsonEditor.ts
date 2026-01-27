import { useState } from 'react';
import { message } from 'antd';

interface UseJsonEditorReturn {
  value: string;
  error: string;
  isValid: boolean;
  setValue: (value: string) => void;
  handleChange: (value: string) => void;
  format: () => void;
}

export const useJsonEditor = (initialValue: string = ''): UseJsonEditorReturn => {
  const [value, setValue] = useState<string>(initialValue);
  const [error, setError] = useState<string>('');
  const [isValid, setIsValid] = useState<boolean>(true);

  // 验证 JSON 格式
  const validate = (text: string): boolean => {
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
  };

  // 格式化 JSON
  const format = () => {
    if (!value.trim()) {
      message.warning('请输入 JSON 内容');
      return;
    }
    try {
      const parsed = JSON.parse(value);
      const formatted = JSON.stringify(parsed, null, 2);
      setValue(formatted);
      setError('');
      setIsValid(true);
      message.success('JSON 格式化成功');
    } catch (e: any) {
      message.error(`JSON 格式错误，无法美化: ${e.message}`);
    }
  };

  // 处理输入变化（自动校验）
  const handleChange = (newValue: string) => {
    setValue(newValue);
    validate(newValue);
  };

  return {
    value,
    error,
    isValid,
    setValue,
    handleChange,
    format
  };
};