/**
 * 鉴权配置主页面
 * 符合前端代码规范
 */

import React, { useState, useEffect } from 'react';
import { Card, Tabs, Space, Tag } from 'antd';
import { FileTextOutlined, EnvironmentOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'react-router-dom';
import { getProjectAuthTemplate, getEnvironmentAuthConfig } from '../services/auth';
import { getProjectEnvironments } from '../services/environments';
import ProjectTemplateEditor from '../components/ProjectTemplateEditor';
import EnvironmentConfigEditor from '../components/EnvironmentConfigEditor';

/**
 * 鉴权配置主页面
 * 支持项目模板和环境差异化配置两种模式
 */
const AuthConfigView: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const [configMode, setConfigMode] = useState<'project' | 'environment'>('project');
  const [selectedEnvironment, setSelectedEnvironment] = useState<number | null>(null);

  const projectIdNum = projectId ? parseInt(projectId, 10) : 0;
  console.log('AuthConfig - projectId:', projectId, 'projectIdNum:', projectIdNum);

  // 获取环境列表
  const { data: envListData } = useQuery({
    queryKey: ['environments', projectIdNum],
    queryFn: () => getProjectEnvironments(projectIdNum, 1, 100),
    retry: false,
    enabled: !!projectIdNum
  });

  const envList = envListData?.items || [];
  console.log('AuthConfig - envList:', envList);

  // 获取项目模板
  const { data: projectTemplate } = useQuery({
    queryKey: ['authTemplate', projectIdNum],
    queryFn: () => getProjectAuthTemplate(projectIdNum),
    retry: false,
    enabled: !!projectIdNum
  });

  // 获取环境配置
  const { data: envAuthConfig } = useQuery({
    queryKey: ['authConfig', projectIdNum, selectedEnvironment],
    queryFn: () => getEnvironmentAuthConfig(projectIdNum, selectedEnvironment!),
    enabled: !!projectIdNum && !!selectedEnvironment,
    retry: false
  });
  
  // 从 URL 参数中读取环境 ID 并自动选中
  useEffect(() => {
    const envIdParam = searchParams.get('env');
    if (envIdParam) {
      const envId = parseInt(envIdParam, 10);
      if (!isNaN(envId)) {
        setSelectedEnvironment(envId);
        setConfigMode('environment');
      }
    }
  }, [searchParams]);

  // 监听 envList 变化
  useEffect(() => {
    console.log('AuthConfig - envList 更新:', envList);
  }, [envList]);
  
  /**
   * 切换配置模式
   */
  const handleModeChange = (key: string) => {
    setConfigMode(key as 'project' | 'environment');
    setSelectedEnvironment(null);
  };
  
  return (
    <div className="auth-config-container" style={{ padding: '24px' }}>
      <Card className="mode-switcher">
        <Tabs 
          activeKey={configMode}
          onChange={handleModeChange}
          items={[
            {
              key: 'project',
              label: (
                <Space>
                  <FileTextOutlined />
                  项目模板（所有环境共用）
                  {projectTemplate?.data && <Tag color="blue">已配置</Tag>}
                </Space>
              ),
              children: (
                <ProjectTemplateEditor
                  projectId={projectIdNum}
                  config={projectTemplate?.data ?? null}
                />
              )
            },
            {
              key: 'environment',
              label: (
                <Space>
                  <EnvironmentOutlined />
                  环境差异化配置
                </Space>
              ),
              children: (
                <EnvironmentConfigEditor
                  projectId={projectIdNum}
                  environments={envList || []}
                  selectedEnvironment={selectedEnvironment}
                  onSelectEnvironment={setSelectedEnvironment}
                  config={envAuthConfig?.data ?? null}
                  projectTemplate={projectTemplate?.data ?? null}
                />
              )
            }
          ]}
        />
      </Card>
    </div>
  );
};

export default AuthConfigView;
