import React, { useState, useEffect } from 'react';
import { Layout, Menu, Button, Space, Dropdown, Avatar } from 'antd';
import {
  HomeOutlined,
  UserOutlined,
  FileTextOutlined,
  CodeOutlined,
  ApiOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  ProjectOutlined,
  BranchesOutlined,
  DownOutlined,
  CloudServerOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { useProjectStore } from '../store/project';
import ProjectSelector from './ProjectSelector';
import VersionSelector from './VersionSelector';

const { Header, Content } = Layout;

const MainLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuthStore();
  const { initializeFromStorage, fetchProjects, currentProject } = useProjectStore();

  useEffect(() => {
    // 初始化项目状态
    initializeFromStorage();
    fetchProjects();
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const menuItems = [
    {
      key: '/dashboard',
      icon: <HomeOutlined />,
      label: '仪表盘',
    },
    {
      key: 'projects',
      icon: <ProjectOutlined />,
      label: '项目管理',
      children: [
        {
          key: '/projects',
          label: '项目列表',
        },
        {
          key: 'versions',
          label: '版本管理',
        },
      ],
    },
    {
      key: 'api-hub',
      icon: <CloudServerOutlined />,
      label: 'API 资产库',
      children: [
        {
          key: '/api-hub/definitions',
          label: '接口定义',
        },
        {
          key: '/api-hub/cases',
          label: '测试用例',
        },
        {
          key: '/api-hub/sync',
          label: '文档同步',
        },
        {
          key: '/api-hub/snapshots',
          label: '版本快照',
        },
      ],
    },
    {
      key: 'api-integration',
      icon: <ApiOutlined />,
      label: '接口集成',
      children: [
        {
          key: '/api/documents',
          label: '文档管理',
        },
        {
          key: '/api/endpoints',
          label: '接口定义',
        },
        {
          key: '/api/scripts',
          label: '测试脚本',
        },
        {
          key: '/api/scenarios',
          label: '场景组装',
        },
        {
          key: '/api/mock',
          label: 'Mock 服务',
        },
        {
          key: '/api/suites',
          label: '测试套件',
        },
        {
          key: '/api/executions',
          label: '执行记录',
        },
        {
          key: '/api/reports',
          label: '测试报告',
        },
      ],
    },
    {
      key: 'ui-automation',
      icon: <RobotOutlined />,
      label: 'UI 自动化',
      children: [
        {
          key: '/ui-automation',
          label: 'UI 测试',
        },
      ],
    },
    {
      key: 'orchestrator',
      icon: <ThunderboltOutlined />,
      label: '流程编排',
      children: [
        {
          key: '/orchestrator',
          label: 'CI/CD 集成',
        },
      ],
    },
    {
      key: 'infra',
      icon: <DatabaseOutlined />,
      label: '基础设施',
      children: [
        {
          key: '/infra',
          label: '数据支撑',
        },
      ],
    },
    {
      key: 'todo',
      icon: <ExperimentOutlined />,
      label: '待实现',
      children: [
        {
          key: '/requirements',
          label: '需求洞察',
        },
        {
          key: '/code-quality',
          label: '代码质量',
        },
        {
          key: '/ui-automation',
          label: 'UI 自动化',
        },
      ],
    },
  ];

  const getSelectedKeys = () => {
    const path = location.pathname;
    if (path === '/') return ['/dashboard'];
    // 如果是版本管理页面，返回 versions 作为选中项
    if (path.startsWith('/projects/') && path.endsWith('/versions')) {
      return ['versions'];
    }
    return [path];
  };

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key === 'profile') {
      navigate('/profile');
    } else if (key === 'versions') {
      // 版本管理特殊处理
      if (currentProject) {
        navigate(`/projects/${currentProject.id}/versions`);
      } else {
        // 如果未选择项目，跳转到项目列表并提示用户
        navigate('/projects');
      }
    } else {
      navigate(key);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        background: '#fff',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        height: 64,
      }}>
        {/* Logo */}
        <div style={{
          marginRight: 40,
          fontSize: 20,
          fontWeight: 'bold',
          color: '#1890ff',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
        }} onClick={() => navigate('/')}>
          BugSeek
        </div>

        {/* 顶部导航菜单 */}
        <Menu
          theme="light"
          mode="horizontal"
          selectedKeys={getSelectedKeys()}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ flex: 1, lineHeight: '64px', border: 'none' }}
        />

        {/* 右侧工具栏 */}
        <Space size="middle" style={{ marginLeft: 24 }}>
          <ProjectSelector />
          <VersionSelector />
          <Dropdown
            menu={{
              items: [
                {
                  key: 'profile',
                  icon: <UserOutlined />,
                  label: '个人中心',
                  onClick: () => navigate('/profile'),
                },
                {
                  type: 'divider',
                },
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: handleLogout,
                },
              ],
            }}
            placement="bottomRight"
          >
            <Button type="text" icon={<Avatar icon={<UserOutlined />} />}>
              <DownOutlined />
            </Button>
          </Dropdown>
        </Space>
      </Header>
      <Content style={{ margin: '24px', overflow: 'auto' }}>
        <div style={{ padding: 24, minHeight: 'calc(100vh - 112px)', background: '#fff', borderRadius: 8 }}>
          <Outlet />
        </div>
      </Content>
    </Layout>
  );
};

export default MainLayout;