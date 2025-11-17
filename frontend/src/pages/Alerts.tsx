/**
 * Alerts Page
 *
 * Central view for all alerts across the cluster with filtering and actions
 */

import React, { useEffect, useState } from 'react';
import { Table, Tag, Space, Typography, Card, Button, Alert as AntAlert, Select } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { monitorApi } from '../api/client';
import type { Alert } from '../types';

const { Title } = Typography;
const { Option } = Select;

const Alerts: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [levelFilter, setLevelFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  useEffect(() => {
    loadAlerts();
  }, [levelFilter, statusFilter]);

  const loadAlerts = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await monitorApi.listAlerts({
        level: levelFilter,
        status: statusFilter,
      });
      if (response.success && response.data) {
        setAlerts(response.data);
      }
    } catch (err) {
      console.error('Failed to load alerts:', err);
      setError('Failed to load alerts. Please ensure the Monitor service is running.');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
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
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
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
        const color =
          status === 'resolved' ? 'green' :
          status === 'in_progress' ? 'blue' :
          status === 'escalated' ? 'red' : 'orange';
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (time: string) => new Date(time).toLocaleString(),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2}>Alert Center</Title>
        <Button icon={<ReloadOutlined />} onClick={loadAlerts} loading={loading}>
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
        <Space style={{ marginBottom: 16 }}>
          <span>Filter by Level:</span>
          <Select
            style={{ width: 120 }}
            placeholder="All"
            allowClear
            onChange={setLevelFilter}
          >
            <Option value="L1">L1</Option>
            <Option value="L2">L2</Option>
            <Option value="L3">L3</Option>
          </Select>

          <span>Filter by Status:</span>
          <Select
            style={{ width: 150 }}
            placeholder="All"
            allowClear
            onChange={setStatusFilter}
          >
            <Option value="pending">Pending</Option>
            <Option value="in_progress">In Progress</Option>
            <Option value="resolved">Resolved</Option>
            <Option value="escalated">Escalated</Option>
          </Select>
        </Space>

        <Table
          dataSource={alerts}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </Space>
  );
};

export default Alerts;
