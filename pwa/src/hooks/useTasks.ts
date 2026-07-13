import { useCallback } from 'react'
import { useAppStore, Task } from '../store/useAppStore'

export function useTasks() {
  const { tasks, addTask, updateTask, removeTask } = useAppStore()

  const submitTask = useCallback(async (task: Omit<Task, 'id' | 'createdAt' | 'logs' | 'status'>) => {
    const newTask: Task = {
      ...task,
      id: crypto.randomUUID(),
      status: 'pending',
      createdAt: new Date().toISOString(),
      logs: []
    }
    addTask(newTask)

    try {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${useAppStore.getState().token}` },
        body: JSON.stringify(newTask)
      })
      const saved = await res.json()
      updateTask(newTask.id, { id: saved.id })
    } catch (e) {
      updateTask(newTask.id, { status: 'failed', error: 'Failed to submit' })
    }

    return newTask
  }, [addTask, updateTask])

  const cancelTask = useCallback((id: string) => {
    updateTask(id, { status: 'failed', error: 'Cancelled by user' })
    fetch(`/api/tasks/${id}/cancel`, { method: 'POST' })
  }, [updateTask])

  const retryTask = useCallback((task: Task) => {
    const newTask: Task = { ...task, id: crypto.randomUUID(), status: 'pending', createdAt: new Date().toISOString(), logs: [] }
    addTask(newTask)
    submitTask(newTask)
  }, [addTask])

  return { tasks, submitTask, cancelTask, retryTask, updateTask, removeTask }
}

export function useTask(id: string) {
  const { tasks, updateTask } = useAppStore()
  return tasks.find((t) => t.id === id)
}
