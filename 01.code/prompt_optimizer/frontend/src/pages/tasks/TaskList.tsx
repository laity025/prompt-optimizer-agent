// ==========================================================
// 任务列表页：状态 chips + 圆形搜索 + 任务卡片栅格 + 分页
// ==========================================================
import { useCallback, useEffect, useState } from 'react'
import { Pagination, Spin, App } from 'antd'
import { PlusOutlined, SearchOutlined, DeleteOutlined, AppstoreOutlined, ReloadOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { listTasks, deleteTask } from '@/api/task'
import StatusBadge from '@/components/StatusBadge'
import PageHeader from '@/components/PageHeader'
import { EmptyArt } from '@/components/ui'
import { type TaskListItem, type TaskStatus, type TaskType } from '@/types'
import { formatTime } from '@/utils'

// 状态筛选 chips
const STATUS_OPTIONS: { label: string; value: '' | TaskStatus }[] = [
  { label: '全部', value: '' },
  { label: '待运行', value: 'pending' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已停止', value: 'stopped' },
  { label: '失败', value: 'failed' },
]

// 任务类型英文副题
const TYPE_EN: Record<TaskType, string> = {
  text_gen: '/text generation',
  summary: '/summarization',
  extraction: '/extraction',
  code: '/code generation',
  custom: '/custom task',
}

export default function TaskList() {
  const navigate = useNavigate()
  const app = App.useApp()
  const [items, setItems] = useState<TaskListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(9)
  const [status, setStatus] = useState<'' | TaskStatus>('')
  const [keyword, setKeyword] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listTasks({ page, page_size: pageSize, status: status || undefined, keyword: keyword || undefined })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      /* 错误已统一提示 */
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, status, keyword])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 删除任务（运行中由后端约束禁止）
  const handleDelete = (e: React.MouseEvent, id: number, name: string) => {
    e.stopPropagation()
    app.modal.confirm({
      title: '删除任务',
      content: `确定删除任务「${name}」吗？将级联删除其全部用例与迭代数据。`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        await deleteTask(id)
        app.message.success('已删除')
        fetchData()
      },
    })
  }

  return (
    <div>
      <PageHeader
        title="任务列表"
        en="tasks"
        extra={
          <button className="pe-btn pe-btn-blue" onClick={() => navigate('/tasks/new')}>
            <PlusOutlined />
            新建任务
          </button>
        }
      />

      {/* 筛选 + 搜索 */}
      <div className="pe-toolbar">
        <div className="pe-chips">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`pe-chip ${status === opt.value ? 'is-active' : ''}`}
              onClick={() => {
                setStatus(opt.value)
                setPage(1)
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="pe-search">
          <SearchOutlined />
          <input
            placeholder="按任务名搜索，回车确认"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                setPage(1)
                fetchData()
              }
            }}
          />
        </div>
      </div>

      <Spin spinning={loading}>
        {items.length === 0 && !loading ? (
          <div className="pe-card" style={{ padding: '8px 0 28px' }}>
            <EmptyArt text={keyword || status ? '没有符合筛选条件的任务' : '还没有任务，从创建第一个优化任务开始'} />
            <div style={{ textAlign: 'center' }}>
              <button className="pe-btn pe-btn-blue pe-btn-sm" onClick={() => navigate('/tasks/new')}>
                <PlusOutlined />
                新建任务
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="pe-grid">
              {items.map((task, idx) => (
                <div
                  key={task.id}
                  className="pe-card pe-card-hover pe-task-card"
                  onClick={() => navigate(`/tasks/${task.id}`)}
                >
                  <span className="pe-corner-orb" />
                  <button
                    type="button"
                    className="pe-card-del"
                    title="删除任务"
                    onClick={(e) => handleDelete(e, task.id, task.name)}
                  >
                    <DeleteOutlined />
                  </button>

                  <div className="pe-card-top">
                    <span className="pe-dotnum">{String((page - 1) * pageSize + idx + 1).padStart(2, '0')}</span>
                    <span className="pe-task-score tnum">
                      {task.best_score == null ? '—' : task.best_score.toFixed(1)}
                      {task.best_score != null && <small>分</small>}
                    </span>
                  </div>

                  <div className="pe-task-name">{task.name}</div>
                  <div className="pe-task-type">
                    <span className="pe-sub-italic">{TYPE_EN[task.task_type as TaskType] || `/${task.task_type}`}</span>
                    <StatusBadge status={task.status} />
                  </div>

                  <hr className="hairline" />
                  <div className="pe-task-meta">
                    <span>
                      <AppstoreOutlined />
                      {task.case_count} 用例
                    </span>
                    <span>
                      <ReloadOutlined />
                      第 {task.current_round} 轮
                    </span>
                    <span>
                      <ClockCircleOutlined />
                      {formatTime(task.created_at).slice(0, 16)}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 22 }}>
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                showSizeChanger
                pageSizeOptions={[9, 12, 24]}
                showTotal={(t) => `共 ${t} 个任务`}
                onChange={(p, ps) => {
                  setPage(p)
                  setPageSize(ps)
                }}
              />
            </div>
          </>
        )}
      </Spin>
    </div>
  )
}
