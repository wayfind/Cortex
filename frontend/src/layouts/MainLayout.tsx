/**
 * Main Layout Component
 *
 * Provides the overall application structure with navigation and content area
 */

import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography } from 'antd';
import {
  DashboardOutlined,
  ClusterOutlined,
  BellOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';

const { Header, Content, Sider } = Layout;
const { Title } = Typography;

const MainLayout: React.FC = () => {
  const location = useLocation();

  const menuItems: MenuProps['items'] = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: <Link to="/">Dashboard</Link>,
    },
    {
      key: '/nodes',
      icon: <ClusterOutlined />,
      label: <Link to="/nodes">Nodes</Link>,
    },
    {
      key: '/alerts',
      icon: <BellOutlined />,
      label: <Link to="/alerts">Alerts</Link>,
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">Settings</Link>,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px' }}>
        <Title level={3} style={{ color: 'white', margin: 0 }}>
          Cortex Monitor
        </Title>
      </Header>

      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
          />
        </Sider>

        <Layout style={{ padding: '24px' }}>
          <Content
            style={{
              padding: 24,
              margin: 0,
              minHeight: 280,
              background: '#fff',
              borderRadius: '8px',
            }}
          >
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
