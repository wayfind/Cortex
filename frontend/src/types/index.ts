/**
 * Cortex Web Dashboard - Type Definitions
 */

// Agent/Node Types
export interface Agent {
  id: string;
  name: string;
  parent_id: string | null;
  upstream_monitor_url: string | null;
  status: 'online' | 'offline' | 'degraded';
  last_heartbeat: string;
  health_status: string;
  created_at: string;
  updated_at: string;
}

// Cluster Topology Types
export interface ClusterNode extends Agent {
  level: number;  // L0, L1, L2, etc.
  children?: ClusterNode[];
}

export interface ClusterTopology {
  nodes: ClusterNode[];
  total_count: number;
  online_count: number;
  offline_count: number;
  degraded_count: number;
}

// Alert Types
export type AlertLevel = 'L1' | 'L2' | 'L3';
export type AlertStatus = 'pending' | 'in_progress' | 'resolved' | 'escalated';

export interface Alert {
  id: string;
  agent_id: string;
  agent_name?: string;
  level: AlertLevel;
  status: AlertStatus;
  title: string;
  description: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
}

// Decision Types
export interface Decision {
  id: string;
  agent_id: string;
  alert_id: string;
  decision_type: 'approve' | 'reject' | 'escalate';
  reason: string;
  created_at: string;
}

// Inspection Report Types
export interface InspectionReport {
  id: string;
  agent_id: string;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  findings: string;
  actions_taken?: string;
}

// Health Check Types
export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  details?: Record<string, any>;
}

// Probe Status Types
export interface ProbeStatus {
  agent_id: string;
  status: string;
  scheduler_running: boolean;
  next_run: string | null;
  last_run: string | null;
  workspace: string;
}

// Monitor Status Types
export interface MonitorStatus {
  status: string;
  timestamp: string;
  database_url: string;
  cluster_mode: boolean;
}

// API Response Types
export interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
}

// Pagination Types
export interface PaginationParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  order?: 'asc' | 'desc';
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
