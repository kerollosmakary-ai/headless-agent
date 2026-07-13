export type TaskStatus = 'pending' | 'queued' | 'running' | 'awaiting_approval' | 'completed' | 'failed'

export interface Task {
  id: string
  type: 'code' | 'browser' | 'shell' | 'composite'
  name: string
  description?: string
  payload: CodePayload | BrowserPayload | ShellPayload | CompositePayload
  priority: 'low' | 'normal' | 'high' | 'critical'
  status: TaskStatus
  approvalRequired: boolean
  approvalToken?: string
  createdAt: string
  startedAt?: string
  completedAt?: string
  result?: TaskResult
  error?: string
  logs: LogEntry[]
  metadata: Record<string, any>
}

export interface CodePayload {
  language: 'javascript' | 'typescript' | 'python' | 'go' | 'rust' | 'shell'
  code: string
  dependencies?: string[]
  timeoutMs?: number
  memoryLimitMb?: number
  env?: Record<string, string>
}

export interface BrowserPayload {
  url: string
  script: string
  viewport?: { width: number; height: number }
  userAgent?: string
  waitFor?: string
  screenshot?: boolean
}

export interface ShellPayload {
  command: string
  args?: string[]
  cwd?: string
  env?: Record<string, string>
  timeoutMs?: number
}

export interface CompositePayload {
  steps: Array<{
    type: 'code' | 'browser' | 'shell'
    payload: CodePayload | BrowserPayload | ShellPayload
    condition?: string
  }>
}

export interface TaskResult {
  output?: string
  stdout?: string
  stderr?: string
  exitCode?: number
  screenshots?: string[]
  artifacts?: Record<string, string>
  durationMs: number
}

export interface LogEntry {
  timestamp: string
  level: 'debug' | 'info' | 'warn' | 'error'
  message: string
  source?: string
  metadata?: Record<string, any>
}

export interface ApprovalRequest {
  taskId: string
  type: 'captcha' | 'human_review' | '2fa' | 'policy_check'
  challenge: string
  context: Record<string, any>
  expiresAt: string
  callbackUrl: string
}

export interface DaemonStatus {
  version: string
  uptime: number
  queue: {
    pending: number
    running: number
    completed: number
    failed: number
  }
  runners: RunnerStatus[]
  resources: {
    cpu: { used: number; total: number }
    memory: { used: number; total: number }
    disk: { used: number; total: number }
  }
}

export interface RunnerStatus {
  id: string
  type: 'node' | 'python' | 'browser' | 'shell' | 'go' | 'rust'
  status: 'idle' | 'busy' | 'offline'
  currentTaskId?: string
  capabilities: string[]
}

export interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  action?: { label: string; onClick: () => void }
  timestamp: string
  read: boolean
}
