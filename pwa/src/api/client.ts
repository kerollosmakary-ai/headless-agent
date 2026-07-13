const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000/api'
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://161.97.64.179:8080'

class ApiClient {
  private token: string | null = null

  setToken(token: string) { this.token = token }

  private headers() {
    return {
      'Content-Type': 'application/json',
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {})
    }
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...this.headers(), ...options.headers }
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: res.statusText }))
      throw new Error(err.message || `HTTP ${res.status}`)
    }
    return res.json()
  }

  // Tasks
  getTasks() { return this.request<Task[]>('/tasks') }
  getTask(id: string) { return this.request<Task>(`/tasks/${id}`) }
  createTask(task: Omit<Task, 'id' | 'createdAt' | 'logs' | 'status'>) {
    return this.request<Task>('/tasks', { method: 'POST', body: JSON.stringify(task) })
  }
  cancelTask(id: string) { return this.request<void>(`/tasks/${id}/cancel`, { method: 'POST' }) }
  retryTask(id: string) { return this.request<Task>(`/tasks/${id}/retry`, { method: 'POST' }) }

  // Approvals
  getApprovals() { return this.request<ApprovalRequest[]>('/approvals') }
  respondApproval(taskId: string, approved: boolean, token?: string) {
    return this.request<void>(`/approvals/${taskId}`, {
      method: 'POST',
      body: JSON.stringify({ approved, token })
    })
  }

  // Daemon
  getStatus() { return this.request<DaemonStatus>('/status') }
  getRunners() { return this.request<RunnerStatus[]>('/runners') }

  // WebSocket for live logs
  connectLogs(taskId: string, onMessage: (log: LogEntry) => void) {
    const ws = new WebSocket(`${WS_BASE}/tasks/${taskId}/logs?token=${this.token}`)
    ws.onmessage = (e) => onMessage(JSON.parse(e.data))
    return ws
  }

  // Server-Sent Events for status updates
  connectStatus(onMessage: (status: DaemonStatus) => void) {
    const es = new EventSource(`${API_BASE}/status/stream`, { headers: this.headers() })
    es.onmessage = (e) => onMessage(JSON.parse(e.data))
    return es
  }
}

export const api = new ApiClient()

// Re-export types for convenience
export type { Task, TaskStatus, LogEntry, DaemonStatus, ApprovalRequest, RunnerStatus } from '../types'
