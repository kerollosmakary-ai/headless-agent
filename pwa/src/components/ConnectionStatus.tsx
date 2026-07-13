import { useAppStore } from '../store/useAppStore'

export function ConnectionStatus() {
  const { connectionStatus } = useAppStore()

  const config = {
    connected: { color: 'text-emerald-400', label: 'Connected', dot: 'bg-emerald-400' },
    connecting: { color: 'text-amber-400', label: 'Connecting...', dot: 'bg-amber-400 animate-pulse' },
    disconnected: { color: 'text-red-400', label: 'Disconnected', dot: 'bg-red-400' }
  }[connectionStatus]

  return (
    <div className="flex items-center gap-2 text-xs font-medium" role="status" aria-live="polite">
      <span className={`w-2 h-2 rounded-full ${config.dot}`} />
      <span className={config.color}>{config.label}</span>
    </div>
  )
}

cat > /root/headless-agent/pwa/src/components/NotificationBell.tsx << 'EOF'
import { useState } from 'react'
import { useAppStore } from '../store/useAppStore'

export function NotificationBell() {
  const { notifications, dismissNotification } = useAppStore()
  const [open, setOpen] = useState(false)
  const unread = notifications.filter((n) => !n.read).length

  return (
    <div className="relative">
      <button
        className="relative p-2 rounded-lg hover:bg-slate-800 transition-colors"
        onClick={() => setOpen(!open)}
        aria-label={`Notifications${unread > 0 ? `, ${unread} unread` : ''}`}
        aria-expanded={open}
      >
        <Bell className="w-5 h-5 text-slate-400" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-slate-900 border border-slate-800 rounded-lg shadow-xl overflow-hidden z-50">
          <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <h3 className="font-semibold">Notifications</h3>
            {notifications.some((n) => !n.read) && (
              <button
                className="text-xs text-sky-400 hover:underline"
                onClick={() => notifications.filter((n) => !n.read).forEach((n) => dismissNotification(n.id))}
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-slate-500 text-sm">No notifications</div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => dismissNotification(n.id)}
                  className={`w-full px-4 py-3 text-left hover:bg-slate-800/50 transition-colors ${
                    !n.read ? 'bg-sky-500/5' : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`w-2 h-2 mt-2 rounded-full shrink-0 ${n.type === 'error' ? 'bg-red-500' : n.type === 'warning' ? 'bg-amber-500' : n.type === 'success' ? 'bg-emerald-500' : 'bg-sky-500'}`} />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">{n.title}</p>
                      {n.message && <p className="text-xs text-slate-400 truncate">{n.message}</p>}
                      <p className="text-xs text-slate-500 mt-1">{new Date(n.timestamp).toLocaleTimeString()}</p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Bell({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )
}

cat > /root/headless-agent/pwa/src/components/ConnectionProvider.tsx << 'EOF'
import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { EventSourcePolyfill } from 'event-source-polyfill'

interface ConnectionContextType {
  daemonStatus: DaemonStatus | null
  setDaemonStatus: (status: DaemonStatus) => void
}

const ConnectionContext = createContext<ConnectionContextType | null>(null)

export function ConnectionProvider({ children }: { children: ReactNode }) {
  const [daemonStatus, setDaemonStatus] = useState<DaemonStatus | null>(null)

  useEffect(() => {
    const es = new EventSourcePolyfill('/api/status/stream', {
      headers: { Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}` }
    })
    es.onmessage = (e) => setDaemonStatus(JSON.parse(e.data))
    es.onerror = () => es.close()
    return () => es.close()
  }, [])

  return (
    <ConnectionContext.Provider value={{ daemonStatus, setDaemonStatus }}>
      {children}
    </ConnectionContext.Provider>
  )
}

export function useConnection() {
  const ctx = useContext(ConnectionContext)
  if (!ctx) throw new Error('useConnection must be used within ConnectionProvider')
  return ctx
}

interface DaemonStatus {
  version: string
  uptime: number
  queue: { pending: number; running: number; completed: number; failed: number }
  runners: Array<{ id: string; type: string; status: string }>
}

cat > /root/headless-agent/pwa/src/components/Toaster.tsx << 'EOF'
import { useAppStore } from '../store/useAppStore'
import { X } from './icons'

export function Toaster() {
  const { notifications, dismissNotification } = useAppStore()
  const toasts = notifications.slice(0, 5)

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none" aria-live="polite">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={() => dismissNotification(toast.id)} />
      ))}
    </div>
  )
}

function Toast({ toast, onDismiss }: { toast: any; onDismiss: () => void }) {
  const colors = {
    success: 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300',
    error: 'bg-red-500/20 border-red-500/30 text-red-300',
    warning: 'bg-amber-500/20 border-amber-500/30 text-amber-300',
    info: 'bg-sky-500/20 border-sky-500/30 text-sky-300'
  }

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg min-w-[300px] max-w-md animate-slide-in ${colors[toast.type]}`}
      role="alert"
    >
      <div className="flex-1 min-w-0">
        <p className="font-medium">{toast.title}</p>
        {toast.message && <p className="text-sm opacity-80 mt-0.5">{toast.message}</p>}
      </div>
      <button onClick={onDismiss} className="p-1 opacity-50 hover:opacity-100 text-current">
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
