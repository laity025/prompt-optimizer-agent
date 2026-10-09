// ==========================================================
// 状态徽标：任务状态 -> 皇家蓝体系彩色块（带状态点）
// ==========================================================
import { TASK_STATUS_LABEL, type TaskStatus } from '@/types'

const STATUS_CLASS: Record<TaskStatus, string> = {
  pending: 'pe-badge-pending',
  running: 'pe-badge-running',
  completed: 'pe-badge-done',
  stopped: 'pe-badge-stop',
  failed: 'pe-badge-error',
}

export default function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <span className={`pe-badge ${STATUS_CLASS[status]}`}>
      {status === 'running' ? <span className="pe-dot-pulse" /> : <span className="dot" />}
      {TASK_STATUS_LABEL[status] || status}
    </span>
  )
}
