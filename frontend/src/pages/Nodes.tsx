/**
 * Nodes Page
 *
 * List of all nodes in the cluster with status and actions
 */

import React, { useEffect, useState } from 'react';
import { Table, Tag, Space, Typography, Card, Button, Alert as AntAlert } from 'antd';
import { Link } from 'react-router-dom';
import { ReloadOutlined } from '@ant-design/icons';
import { monitorApi } from '../api/client';
import type { Agent } from '../types';

const { Title } = Typography;

const Nodes: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await monitorApi.listAgents();
      if (response.success && response.data) {
        setAgents(response.data);
      }
    } catch (err) {
      console.error('Failed to load agents:', err);
      setError('Failed to load agents. Please ensure the Monitor service is running.');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string) => <Link to={`/nodes/${id}`}>{id}</Link>,
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color = status === 'online' ? 'green' : status === 'offline' ? 'red' : 'orange';
        return <Tag color={color}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: 'Parent ID',
      dataIndex: 'parent_id',
      key: 'parent_id',
      render: (parentId: string | null) => parentId || <Tag>Root</Tag>,
    },
    {
      title: 'Last Heartbeat',
      dataIndex: 'last_heartbeat',
      key: 'last_heartbeat',
      render: (time: string) => time ? new Date(time).toLocaleString() : 'Never',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Agent) => (
        <Space size="middle">
          <Link to={`/nodes/${record.id}`}>View Details</Link>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2}>Cluster Nodes</Title>
        <Button icon={<ReloadOutlined />} onClick={loadAgents} loading={loading}>
          Refresh
        </Button>
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

      <Card>
        <Table
          dataSource={agents}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </Space>
  );
};

export default Nodes;
