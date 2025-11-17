/**
 * Cortex API Client
 *
 * Axios-based API client for communicating with Monitor and Probe services
 */

import axios, { AxiosError } from 'axios';
import type { AxiosInstance } from 'axios';
import type {
  Agent,
  ClusterTopology,
  Alert,
  Decision,
  InspectionReport,
  HealthStatus,
  ProbeStatus,
  MonitorStatus,
  ApiResponse,
  PaginationParams,
  PaginatedResponse,
} from '../types';

// API Base URLs (can be configured via environment variables)
const MONITOR_API_URL = import.meta.env.VITE_MONITOR_API_URL || 'http://localhost:18000';
const PROBE_API_URL = import.meta.env.VITE_PROBE_API_URL || 'http://localhost:18001';

// Create Axios instances
const monitorClient: AxiosInstance = axios.create({
  baseURL: MONITOR_API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const probeClient: AxiosInstance = axios.create({
  baseURL: PROBE_API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
const errorInterceptor = (error: AxiosError) => {
  if (error.response) {
    // Server responded with error status
    console.error('API Error:', error.response.status, error.response.data);
  } else if (error.request) {
    // Request made but no response
    console.error('Network Error: No response from server');
  } else {
    console.error('Request Error:', error.message);
  }
  return Promise.reject(error);
};

monitorClient.interceptors.response.use(response => response, errorInterceptor);
probeClient.interceptors.response.use(response => response, errorInterceptor);

// ============================================================================
// Monitor API
// ============================================================================

export const monitorApi = {
  // Health Check
  async getHealth(): Promise<MonitorStatus> {
    const { data } = await monitorClient.get<MonitorStatus>('/health');
    return data;
  },

  // Cluster Management
  async getClusterTopology(): Promise<ApiResponse<ClusterTopology>> {
    const { data } = await monitorClient.get<ApiResponse<ClusterTopology>>('/api/v1/cluster/topology');
    return data;
  },

  async listAgents(params?: PaginationParams): Promise<ApiResponse<Agent[]>> {
    const { data } = await monitorClient.get<any>('/api/v1/agents', { params });
    // Backend returns { success, data: { agents, count }, message, timestamp }
    return {
      success: data.success,
      data: data.data?.agents || [],
      message: data.message,
    };
  },

  async getAgent(agentId: string): Promise<ApiResponse<Agent>> {
    const { data } = await monitorClient.get<ApiResponse<Agent>>(`/api/v1/agents/${agentId}`);
    return data;
  },

  async registerAgent(agent: Partial<Agent>): Promise<ApiResponse<Agent>> {
    const { data } = await monitorClient.post<ApiResponse<Agent>>('/api/v1/agents', agent);
    return data;
  },

  async updateAgentHeartbeat(agentId: string, healthStatus: string): Promise<ApiResponse> {
    const { data } = await monitorClient.post<ApiResponse>(
      `/api/v1/agents/${agentId}/heartbeat`,
      { health_status: healthStatus }
    );
    return data;
  },

  async deleteAgent(agentId: string): Promise<ApiResponse> {
    const { data} = await monitorClient.delete<ApiResponse>(`/api/v1/agents/${agentId}`);
    return data;
  },

  // Alerts
  async listAlerts(params?: PaginationParams & { agent_id?: string; level?: string; status?: string }): Promise<ApiResponse<Alert[]>> {
    const { data } = await monitorClient.get<any>('/api/v1/alerts', { params });
    // Backend returns { success, data: { alerts, count, limit, offset }, message, timestamp }
    return {
      success: data.success,
      data: data.data?.alerts || [],
      message: data.message,
    };
  },

  async getAlert(alertId: string): Promise<ApiResponse<Alert>> {
    const { data } = await monitorClient.get<ApiResponse<Alert>>(`/api/v1/alerts/${alertId}`);
    return data;
  },

  async createAlert(alert: Partial<Alert>): Promise<ApiResponse<Alert>> {
    const { data } = await monitorClient.post<ApiResponse<Alert>>('/api/v1/alerts', alert);
    return data;
  },

  async updateAlertStatus(alertId: string, status: string): Promise<ApiResponse> {
    const { data } = await monitorClient.patch<ApiResponse>(`/api/v1/alerts/${alertId}`, { status });
    return data;
  },

  // Decisions
  async listDecisions(params?: PaginationParams & { agent_id?: string; status?: string }): Promise<ApiResponse<Decision[]>> {
    const { data } = await monitorClient.get<any>('/api/v1/decisions', { params });
    // Backend returns { success, data: { decisions, count, limit, offset }, message, timestamp }
    return {
      success: data.success,
      data: data.data?.decisions || [],
      message: data.message,
    };
  },

  async createDecision(decision: Partial<Decision>): Promise<ApiResponse<Decision>> {
    const { data } = await monitorClient.post<ApiResponse<Decision>>('/api/v1/decisions', decision);
    return data;
  },

  // Reports
  // Note: Monitor does not provide report listing endpoint
  // Use probeApi.listReports() instead to get reports from Probe
  async createReport(report: any): Promise<ApiResponse> {
    const { data } = await monitorClient.post<ApiResponse>('/api/v1/reports', report);
    return data;
  },
};

// ============================================================================
// Probe API
// ============================================================================

export const probeApi = {
  // Health Check
  async getHealth(): Promise<HealthStatus> {
    const { data } = await probeClient.get<HealthStatus>('/health');
    return data;
  },

  // Status
  async getStatus(): Promise<ProbeStatus> {
    const { data } = await probeClient.get<ProbeStatus>('/status');
    return data;
  },

  // Schedule Management
  async getSchedule(): Promise<ApiResponse> {
    const { data } = await probeClient.get<ApiResponse>('/schedule');
    return data;
  },

  async pauseSchedule(): Promise<ApiResponse> {
    const { data } = await probeClient.post<ApiResponse>('/schedule/pause');
    return data;
  },

  async resumeSchedule(): Promise<ApiResponse> {
    const { data } = await probeClient.post<ApiResponse>('/schedule/resume');
    return data;
  },

  async triggerInspection(force: boolean = false): Promise<ApiResponse> {
    const { data } = await probeClient.post<ApiResponse>('/execute', { force });
    return data;
  },

  // Reports
  async listReports(limit: number = 20): Promise<ApiResponse<InspectionReport[]>> {
    const { data } = await probeClient.get<any>('/reports', { params: { limit } });
    // Backend returns { reports, total, timestamp }
    return {
      success: true,
      data: data.reports || [],
      message: `Retrieved ${data.total} reports`,
    };
  },

  async getReport(executionId: string): Promise<ApiResponse<InspectionReport>> {
    const { data } = await probeClient.get<any>(`/reports/${executionId}`);
    return {
      success: true,
      data: data,
      message: 'Report retrieved successfully',
    };
  },
};

// Export both clients for direct use if needed
export { monitorClient, probeClient };
