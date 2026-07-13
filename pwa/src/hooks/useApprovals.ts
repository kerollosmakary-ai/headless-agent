import { useCallback } from 'react'
import { useAppStore, ApprovalRequest } from '../store/useAppStore'

export function useApprovals() {
  const { approvals, addApproval, updateApproval } = useAppStore()

  const requestApproval = useCallback(async (approval: Omit<ApprovalRequest, 'id' | 'status' | 'requestedAt'>) => {
    const newApproval: ApprovalRequest = {
      ...approval,
      id: crypto.randomUUID(),
      status: 'pending',
      requestedAt: new Date().toISOString()
    }
    addApproval(newApproval)

    try {
      await fetch('/api/approvals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${useAppStore.getState().token}` },
        body: JSON.stringify(newApproval)
      })
    } catch (e) {
      updateApproval(newApproval.id, { status: 'rejected' })
    }

    return newApproval
  }, [addApproval, updateApproval])

  const decideApproval = useCallback(
    (id: string, decision: 'approved' | 'rejected') => {
      updateApproval(id, { status: decision, decidedAt: new Date().toISOString(), decidedBy: 'user' })
      fetch(`/api/approvals/${id}/${decision}`, { method: 'POST' })
    },
    [updateApproval]
  )

  const pendingApprovals = approvals.filter((a) => a.status === 'pending')

  return { approvals, pendingApprovals, requestApproval, decideApproval }
}
