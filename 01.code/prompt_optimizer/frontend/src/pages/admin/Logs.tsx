// ==========================================================
// 管理员 · 系统日志页：结果筛选 chips + 日志表格
// ==========================================================
import { useCallback, useEffect, useState } from 'react'
import { Table, Tag } from 'antd'
import { getLogs } from '@/api/admin'
import PageHeader from '@/components/PageHeader'
import { Panel } from '@/components/ui'
import type { AdminLogItem } from '@/types'
import { formatTime } from '@/utils'

const RESULT_OPTIONS = [
  { label: '全部', value: '' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

export default function AdminLogs() {
  const [items, setItems] = useState<AdminLogItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getLogs({ page, page_size: pageSize, result: result || undefined })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      /* 错误统一提示 */
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, result])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const columns = [
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: (v: string) => <span className="tnum">{formatTime(v)}</span> },
    { title: '用户', dataIndex: 'user_email', key: 'user_email', width: 180, render: (v: string | null) => v || '—' },
    { title: '操作', dataIndex: 'action', key: 'action' },
    {
      title: '结果',
      dataIndex: 'result',
      key: 'result',
      width: 100,
      render: (v: string) => (
        <Tag color={v === 'success' ? 'success' : 'error'}>{v === 'success' ? '成功' : '失败'}</Tag>
      ),
    },
    { title: '耗时(ms)', dataIndex: 'duration_ms', key: 'duration_ms', width: 110, render: (v: number | null) => (v == null ? '—' : <span className="tnum">{v}</span>) },
    { title: '错误信息', dataIndex: 'error_message', key: 'error_message', ellipsis: true, render: (v: string | null) => v || '—' },
  ]

  return (
    <div>
      <PageHeader title="系统日志" en="system logs" />
      <div className="pe-toolbar">
        <div className="pe-chips">
          {RESULT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`pe-chip ${result === opt.value ? 'is-active' : ''}`}
              onClick={() => {
                setResult(opt.value)
                setPage(1)
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <span className="pe-sub-italic">/audit trail</span>
      </div>
      <Panel tight>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
          }}
        />
      </Panel>
    </div>
  )
}
