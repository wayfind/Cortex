/**
 * Cortex Web Dashboard - Main App Component
 *
 * Sets up routing and application structure
 */

import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';

// Layout
import MainLayout from './layouts/MainLayout';

// Pages
import Dashboard from './pages/Dashboard';
import Nodes from './pages/Nodes';
import NodeDetail from './pages/NodeDetail';
import Alerts from './pages/Alerts';
import Settings from './pages/Settings';

// Ant Design theme configuration
const theme = {
  token: {
    colorPrimary: '#1890ff',
    borderRadius: 6,
  },
};

function App() {
  return (
    <ConfigProvider theme={theme}>
      <Router>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="nodes" element={<Nodes />} />
            <Route path="nodes/:id" element={<NodeDetail />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
