import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Task {
  id: string
  name: string
  type: 'code' | 'shell' | 'http' | 'browser'
  payload: any
  status: 'pending' | 'running' | 'completed' | 'failed' | 'awaiting_approval'
  approvalId?: string
  result?: any
  error?: string
  createdAt: string
  startedAt?: string
  completedAt?: string
  logs: LogEntry[]
}

export interface LogEntry {
  id: string
  taskId: string
  level: 'info' | 'warn' | 'error' | 'debug'
  message: string
  timestamp: string
  meta?: any
}

export interface ApprovalRequest {
  id: string
  taskId: string
  type: 'dangerous_command' | 'network_access' | 'file_write' | 'secret_access' | 'custom'
  title: string
  description: string
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  payload: any
  status: 'pending' | 'approved' | 'rejected'
  requestedAt: string
  decidedAt?: string
  decidedBy?: string
}

export interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  timestamp: string
  read: boolean
  actionUrl?: string
}

interface AppState {
  // Auth
  token: string | null
  setToken: (token: string) => void
  logout: () => void

  // Tasks
  tasks: Task[]
  addTask: (task: Task) => void
  updateTask: (id: string, updates: Partial<Task>) => void
  removeTask: (id: string) => void

  // Approvals
  approvals: ApprovalRequest[]
  addApproval: (approval: ApprovalRequest) => void
  updateApproval: (id: string, updates: Partial<ApprovalRequest>) => void

  // Notifications
  notifications: Notification[]
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void
  dismissNotification: (id: string) => void
  markAllRead: () => void

  // Connection
  connectionStatus: 'connected' | 'connecting' | 'disconnected'
  setConnectionStatus: (status: AppState['connectionStatus']) => void

  // UI
  sidebarOpen: boolean
  toggleSidebar: () => void
  activeView: 'dashboard' | 'tasks' | 'approvals' | 'logs' | 'settings'
  setActiveView: (view: AppState['activeView']) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      token: null,
      setToken: (token) => set({ token }),
      logout: () => set({ token: null, tasks: [], approvals: [], notifications: [] }),

      tasks: [],
      addTask: (task) => set({ tasks: [task, ...get().tasks] }),
      updateTask: (id, updates) =>
        set({ tasks: get().tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)) }),
      removeTask: (id) => set({ tasks: get().tasks.filter((t) => t.id !== id) }),

      approvals: [],
      addApproval: (approval) => set({ approvals: [approval, ...get().approvals] }),
      updateApproval: (id, updates) =>
        set({ approvals: get().approvals.map((a) => (a.id === id ? { ...a, ...updates } : a)) }),

      notifications: [],
      addNotification: (n) =>
        set({
          notifications: [
            { ...n, id: crypto.randomUUID(), timestamp: new Date().toISOString(), read: false },
            ...get().notifications
          ].slice(0, 100)
        }),
      dismissNotification: (id) =>
        set({ notifications: get().notifications.filter((n) => n.id !== id) }),
      markAllRead: () =>
        set({ notifications: get().notifications.map((n) => ({ ...n, read: true })) }),

      connectionStatus: 'disconnected',
      setConnectionStatus: (status) => set({ connectionStatus: status }),

      sidebarOpen: true,
      toggleSidebar: () => set({ sidebarOpen: !get().sidebarOpen }),
      activeView: 'dashboard',
      setActiveView: (view) => set({ activeView: view })
    }),
    { name: 'agent-store', partialize: (s) => ({ token: s.token, activeView: s.activeView }) }
  )
)
