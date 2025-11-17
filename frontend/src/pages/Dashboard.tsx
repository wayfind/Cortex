/**
 * Dashboard Page
 *
 * Main dashboard showing cluster status overview, metrics, and alerts
 */

import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Space, Typography, Alert as AntAlert, Badge } from 'antd';
import {
  ClusterOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  BellOutlined,
  WifiOutlined,
} from '@ant-design/icons';
import { monitorApi } from '../api/client';
import type { Agent, Alert, ClusterTopology } from '../types';
import { useWebSocket, type WebSocketEvent } from '../hooks/useWebSocket';

const { Title } = Typography;

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [topology, setTopology] = useState<ClusterTopology | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Load cluster topology
      const topologyResponse = await monitorApi.getClusterTopology();
      if (topologyResponse.success && topologyResponse.data) {
        // Calculate statistics from nodes array
        const nodes = topologyResponse.data.nodes || [];
        const total_count = nodes.length;
        const online_count = nodes.filter(n => n.status === 'online').length;
        const offline_count = nodes.filter(n => n.status === 'offline').length;
        const degraded_count = nodes.filter(n => n.health_status === 'degraded' || n.health_status === 'warning').length;

        // Add calculated fields to topology
        const enrichedTopology = {
          ...topologyResponse.data,
          total_count,
          online_count,
          offline_count,
          degraded_count,
        };

        setTopology(enrichedTopology);
      }

      // Load recent alerts
      const alertsResponse = await monitorApi.listAlerts({ page_size: 10 });
      if (alertsResponse.success && alertsResponse.data) {
        setRecentAlerts(alertsResponse.data);
      }
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      setError('Failed to connect to Monitor service. Please ensure the service is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle WebSocket events
  const handleWebSocketMessage = useCallback((event: WebSocketEvent) => {
    console.log('[Dashboard] WebSocket event:', event.type);

    switch (event.type) {
      case 'alert_triggered':
      case 'decision_made':
      case 'agent_status_changed':
        // Refresh dashboard data when important events occur
        loadDashboardData();
        break;
      case 'report_received':
        // Don't refresh for every report (too frequent)
        break;
    }
  }, [loadDashboardData]);

  // Connect to WebSocket
  const { isConnected } = useWebSocket({
    onMessage: handleWebSocketMessage,
    showNotifications: true,
  });

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);


  const alertColumns = [
    {
      title: 'Level',
      dataIndex: 'level',
      key: 'level',
      render: (level: string) => {
        const color = level === 'L3' ? 'red' : level === 'L2' ? 'orange' : 'blue';
        return <Tag color={color}>{level}</Tag>;
      },
    },
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      key: 'agent_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color = status === 'resolved' ? 'green' : status === 'pending' ? 'orange' : 'default';
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: 'Time',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString(),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>Cluster Dashboard</Title>
        <Badge
          status={isConnected ? 'success' : 'error'}
          text={isConnected ? 'Live' : 'Disconnected'}
        />
      </div>

      {error && (
        <AntAlert
          message="Connection Error"
          description={error}
          type="error"
          closable
          onClose={() => setError(null)}
        />
      )}

      {/* Status Cards */}
      <Row gutter={16}>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic
              title="Total Nodes"
              value={topology?.total_count || 0}
              prefix={<ClusterOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic
              title="Online"
              value={topology?.online_count || 0}
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic
              title="Offline"
              value={topology?.offline_count || 0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic
              title="Degraded"
              value={topology?.degraded_count || 0}
              valueStyle={{ color: '#faad14' }}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Recent Alerts */}
      <Card
        title={
          <Space>
            <BellOutlined />
            <span>Recent Alerts</span>
          </Space>
        }
        loading={loading}
      >
        <Table
          dataSource={recentAlerts}
          columns={alertColumns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* Cluster Topology Preview */}
      <Card title="Cluster Topology" loading={loading}>
        {topology && topology.nodes.length > 0 ? (
          <div>
            <p>Total nodes: {topology.total_count}</p>
            <p>Hierarchy levels: {Math.max(...topology.nodes.map(n => n.level)) + 1}</p>
            {/* TODO: Add visual topology graph */}
          </div>
        ) : (
          <p>No cluster topology data available</p>
        )}
      </Card>
    </Space>
  );
};

export default Dashboard;
