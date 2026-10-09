// ==========================================================
// 通用工具函数：状态颜色映射、类名拼接等
// ==========================================================
import type { TaskStatus } from '@/types'

// 任务状态徽标颜色映射（对齐 UIUX 设计文档 V2.0 皇家蓝）
// running 使用皇家蓝实心块，与品牌主色一致
export const STATUS_COLOR: Record<TaskStatus, string> = {
  pending: 'default',
  running: '#0E4AC3',
  completed: '#16A34A',
  stopped: '#D97706',
  failed: '#F03A3E',
}

// 简单的 classNames 合并工具
export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

// 下载 Blob 文件工具（用于报告导出）
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// 日期展示格式化，若为空返回占位
export function formatTime(time?: string | null) {
  if (!time) return '—'
  return time.replace('T', ' ').slice(0, 19)
}