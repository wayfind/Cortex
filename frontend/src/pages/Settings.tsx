/**
 * Settings Page
 *
 * Application settings and configuration
 */

import React from 'react';
import { Card, Space, Typography, Descriptions } from 'antd';

const { Title } = Typography;

const Settings: React.FC = () => {
  const monitorUrl = import.meta.env.VITE_MONITOR_API_URL || 'http://localhost:18000';
  const probeUrl = import.meta.env.VITE_PROBE_API_URL || 'http://localhost:18001';

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Title level={2}>Settings</Title>

      <Card title="API Configuration">
        <Descriptions bordered column={1}>
          <Descriptions.Item label="Monitor API URL">{monitorUrl}</Descriptions.Item>
          <Descriptions.Item label="Probe API URL">{probeUrl}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="Application Info">
        <Descriptions bordered column={1}>
          <Descriptions.Item label="Version">0.1.0 (Phase 3 - Web UI)</Descriptions.Item>
          <Descriptions.Item label="Build">Development</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="About">
        <p>
          <strong>Cortex Monitor Dashboard</strong>
        </p>
        <p>
          A decentralized, hierarchical monitoring and operations network.
          Each node is an independent agent that can dynamically form powerful,
          collectively intelligent operational clusters.
        </p>
      </Card>
    </Space>
  );
};

export default Settings;
