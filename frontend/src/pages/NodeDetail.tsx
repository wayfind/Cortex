/**
 * Node Detail Page
 *
 * Detailed view of a single node with metrics, alerts, and actions
 */

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Tag,
  Space,
  Typography,
  Button,
  Alert as AntAlert,
  Tabs,
} from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { monitorApi } from '../api/client';
import type { Agent, Alert } from '../types';

const { Title } = Typography;

const NodeDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      loadAgentData(id);
    }
  }, [id]);

  const loadAgentData = async (agentId: string) => {
    try {
      setLoading(true);
      setError(null);

      // Load agent details
      const agentResponse = await monitorApi.getAgent(agentId);
      if (agentResponse.success && agentResponse.data) {
        setAgent(agentResponse.data);
      }

      // Load alerts for this agent
      const alertsResponse = await monitorApi.listAlerts({ agent_id: agentId });
      if (alertsResponse.success && alertsResponse.data) {
        setAlerts(alertsResponse.data);
      }
    } catch (err) {
      console.error('Failed to load agent data:', err);
      setError('Failed to load agent data. Please ensure the Monitor service is running.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    return status === 'online' ? 'green' : status === 'offline' ? 'red' : 'orange';
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/nodes')}>
            Back to Nodes
          </Button>
          <Title level={2} style={{ margin: 0 }}>Node Details</Title>
        </Space>
      </div>

      {error && (
        <AntAlert
          message="Error"
          description={error}
          type="error"
          closable
          onClose={() => setError(null)}
        />
      )}

      {agent ? (
        <>
          <Card title="Basic Information" loading={loading}>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="ID">{agent.id}</Descriptions.Item>
              <Descriptions.Item label="Name">{agent.name}</Descriptions.Item>
              <Descriptions.Item label="Status">
                <Tag color={getStatusColor(agent.status)}>{agent.status.toUpperCase()}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Health Status">{agent.health_status}</Descriptions.Item>
              <Descriptions.Item label="Parent ID">
                {agent.parent_id || <Tag>Root Node</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="Upstream Monitor">
                {agent.upstream_monitor_url || 'None'}
              </Descriptions.Item>
              <Descriptions.Item label="Last Heartbeat">
                {agent.last_heartbeat ? new Date(agent.last_heartbeat).toLocaleString() : 'Never'}
              </Descriptions.Item>
              <Descriptions.Item label="Created At">
                {new Date(agent.created_at).toLocaleString()}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Tabs
            items={[
              {
                key: 'alerts',
                label: `Alerts (${alerts.length})`,
                children: (
                  <Card>
                    {alerts.length > 0 ? (
                      alerts.map(alert => (
                        <Card key={alert.id} type="inner" style={{ marginBottom: 16 }}>
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <div>
                              <Tag color={alert.level === 'L3' ? 'red' : 'orange'}>{alert.level}</Tag>
                              <Tag>{alert.status}</Tag>
                              <strong>{alert.title}</strong>
                            </div>
                            <p>{alert.description}</p>
                            <small>Created: {new Date(alert.created_at).toLocaleString()}</small>
                          </Space>
                        </Card>
                      ))
                    ) : (
                      <p>No alerts for this node</p>
                    )}
                  </Card>
                ),
              },
              {
                key: 'reports',
                label: 'Inspection Reports',
                children: <Card>Coming soon...</Card>,
              },
              {
                key: 'metrics',
                label: 'Metrics',
                children: <Card>Coming soon...</Card>,
              },
            ]}
          />
        </>
      ) : (
        <Card loading={loading}>
          <p>Loading agent data...</p>
        </Card>
      )}
    </Space>
  );
};

export default NodeDetail;
