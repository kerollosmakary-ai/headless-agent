import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useAppStore } from './store/useAppStore'
import { api } from './api/client'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { TaskQueue } from './pages/TaskQueue'
import { TaskDetail } from './pages/TaskDetail'
import { Approvals } from './pages/Approvals'
import { Settings } from './pages/Settings'
import { NewTask } from './pages/NewTask'
import { ConnectionProvider } from './components/ConnectionProvider'
import { Toaster } from './components/Toaster'

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/queue" element={<TaskQueue />} />
      <Route path="/tasks/new" element={<NewTask />} />
      <Route path="/tasks/:id" element={<TaskDetail />} />
      <Route path="/approvals" element={<Approvals />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export function App() {
  const { setConnectionStatus, addNotification, daemonStatus, setDaemonStatus } = useAppStore()

  useEffect(() => {
    let mounted = true
    const checkConnection = async () => {
      try {
        const status = await api.getStatus()
        if (mounted) {
          setDaemonStatus(status)
          setConnectionStatus('connected')
        }
      } catch {
        if (mounted) setConnectionStatus('disconnected')
      }
    }
    checkConnection()
    const interval = setInterval(checkConnection, 30000)
    return () => { mounted = false; clearInterval(interval) }
  }, [setConnectionStatus, setDaemonStatus])

  return (
    <ConnectionProvider>
      <Layout>
        <AppRoutes />
        <Toaster />
      </Layout>
    </ConnectionProvider>
  )
}
