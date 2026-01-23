import React, { useState, useEffect } from 'react';
import { Layout, Menu, Button, Space } from 'antd';
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
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { useProjectStore } from '../store/project';
import ProjectSelector from './ProjectSelector';
import VersionSelector from './VersionSelector';

const { Header, Sider, Content } = Layout;

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
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
      key: 'requirements',
      icon: <FileTextOutlined />,
      label: '需求洞察',
      children: [
        {
          key: '/requirements',
          label: '需求审查',
        },
      ],
    },
    {
      key: 'code-quality',
      icon: <CodeOutlined />,
      label: '代码质量',
      children: [
        {
          key: '/code-quality',
          label: '代码审查',
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
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人中心',
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

  const getOpenKeys = () => {
    const path = location.pathname;
    if (path.startsWith('/api')) return ['api-integration'];
    if (path.startsWith('/requirements')) return ['requirements'];
    if (path.startsWith('/code-quality')) return ['code-quality'];
    if (path.startsWith('/ui-automation')) return ['ui-automation'];
    if (path.startsWith('/orchestrator')) return ['orchestrator'];
    if (path.startsWith('/infra')) return ['infra'];
    if (path.startsWith('/projects')) return ['projects'];
    return [];
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: collapsed ? 16 : 20,
          fontWeight: 'bold',
          background: '#001529',
        }}>
          {collapsed ? 'BS' : 'BugSeek'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={getSelectedKeys()}
          defaultOpenKeys={getOpenKeys()}
          items={menuItems}
          onClick={({ key }) => {
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
          }}
        />
      </Sider>
      <Layout>
        <Header style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}>
          <Space size="large">
            <ProjectSelector />
            <VersionSelector />
          </Space>
          <Button
            type="text"
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            退出登录
          </Button>
        </Header>
        <Content style={{ margin: '24px 16px 0', overflow: 'auto' }}>
          <div style={{ padding: 24, minHeight: 360, background: '#fff' }}>
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;