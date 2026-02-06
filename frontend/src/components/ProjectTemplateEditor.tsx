/**
 * 项目模板编辑器组件
 * 符合前端代码规范
 */

import React, { useEffect } from 'react';
import { Card, Empty, message } from 'antd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createProjectAuthTemplate, updateProjectAuthTemplate } from '../services/auth';
import AuthConfigForm from './AuthConfigForm';
import type { ProjectAuthTemplate, ProjectAuthTemplateCreate } from '../types/auth';

interface ProjectTemplateEditorProps {
  projectId: number;
  config: ProjectAuthTemplate | null;
}

/**
 * 项目模板编辑器
 * 用于创建和编辑项目级鉴权模板
 */
const ProjectTemplateEditor: React.FC<ProjectTemplateEditorProps> = ({ projectId, config }) => {
  const queryClient = useQueryClient();
  
  /**
   * 创建项目模板
   */
  const createMutation = useMutation({
    mutationFn: (data: ProjectAuthTemplateCreate) => createProjectAuthTemplate(projectId, data),
    onSuccess: () => {
      message.success('项目模板创建成功');
      queryClient.invalidateQueries({ queryKey: ['authTemplate', projectId] });
    },
    onError: (error: any) => {
      message.error(`创建失败: ${error.message || '未知错误'}`);
    }
  });
  
  /**
   * 更新项目模板
   */
  const updateMutation = useMutation({
    mutationFn: (data: ProjectAuthTemplateCreate) => updateProjectAuthTemplate(projectId, data),
    onSuccess: () => {
      message.success('项目模板更新成功');
      queryClient.invalidateQueries({ queryKey: ['authTemplate', projectId] });
    },
    onError: (error: any) => {
      message.error(`更新失败: ${error.message || '未知错误'}`);
    }
  });
  
  /**
   * 处理保存
   */
  const handleSave = (data: ProjectAuthTemplateCreate) => {
    if (config) {
      updateMutation.mutate(data);
    } else {
      createMutation.mutate(data);
    }
  };
  
  if (!config) {
    return (
      <Card>
        <Empty 
          description="暂无项目模板"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
        <div style={{ marginTop: 24 }}>
          <AuthConfigForm 
            mode="template"
            onSave={handleSave}
            loading={createMutation.isPending || updateMutation.isPending}
          />
        </div>
      </Card>
    );
  }
  
  return (
    <Card title="项目模板配置">
      <div style={{ marginBottom: 16 }}>
        <p style={{ color: '#666' }}>
          项目模板是所有环境的默认鉴权配置。可以为不同环境创建差异化的配置，覆盖项目模板的设置。
        </p>
      </div>
      <AuthConfigForm 
        mode="template"
        initialValues={config}
        onSave={handleSave}
        loading={createMutation.isPending || updateMutation.isPending}
      />
    </Card>
  );
};

export default ProjectTemplateEditor;