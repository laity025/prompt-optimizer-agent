// ==========================================================
// 任务详情页容器：加载任务、运行期间轮询进度、组织块状子页签
// ==========================================================
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { App, Spin } from 'antd'
import { ArrowLeftOutlined, CaretRightOutlined, StopOutlined, ExportOutlined } from '@ant-design/icons'
import { getTask, getIterationStatus, startIteration, stopIteration, exportReport } from '@/api/task'
import { TASK_TYPE_LABEL, type Task, type TaskStatus, type IterationStatus } from '@/types'
import { downloadBlob, formatTime } from '@/utils'
import StatusBadge from '@/components/StatusBadge'
import TaskOverview from './TaskOverview'
import TaskIteration from './TaskIteration'
import TaskCases from './TaskCases'
import TaskReport from './TaskReport'

const CAN_START: TaskStatus[] = ['pending', 'stopped', 'completed', 'failed']

const TABS = [
  { key: 'overview', cn: '概览', en: 'overview' },
  { key: 'iteration', cn: '迭代过程', en: 'iteration' },
  { key: 'cases', cn: '用例集', en: 'cases' },
  { key: 'report', cn: '报告', en: 'report' },
] as const

type TabKey = (typeof TABS)[number]['key']

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const taskId = Number(id)
  const navigate = useNavigate()
  const app = App.useApp()
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [progress, setProgress] = useState<IterationStatus | null>(null)
  // 用 ref 记录当前运行状态，避免轮询闭包读取到旧值
  const statusRef = useRef<string | undefined>(task?.status)

  // 加载任务详情
  const loadTask = useCallback(async () => {
    if (!taskId) return
    setLoading(true)
    try {
      const data = await getTask(taskId)
      setTask(data)
      statusRef.current = data.status
    } catch {
      /* 错误统一提示 */
    } finally {
      setLoading(false)
    }
  }, [taskId])

  useEffect(() => {
    loadTask()
  }, [loadTask])

  // 运行中轮询迭代进度（每 1.5s），并监测状态是否结束以刷新任务
  useEffect(() => {
    if (!task || task.status !== 'running') return
    const timer = setInterval(async () => {
      try {
        const p = await getIterationStatus(taskId)
        setProgress(p)
        if (p.task_status !== 'running' && statusRef.current === 'running') {
          statusRef.current = p.task_status
          await loadTask()
        }
      } catch {
        /* 单个轮询失败不中断 */
      }
    }, 1500)
    return () => clearInterval(timer)
  }, [task, taskId, loadTask])

  // 开始 / 继续 / 重新迭代
  const handleStart = async () => {
    // “重新迭代”：completed 状态下点击会清空上一轮结果并从头优化，先确认
    if (task?.status === 'completed') {
      await new Promise<void>((resolve) => {
        app.modal.confirm({
          title: '重新迭代',
          content: '将清空上一轮的迭代记录，从最初的初始提示词重新开始优化，确定继续？',
          okText: '重新迭代',
          okButtonProps: { danger: true },
          cancelText: '取消',
          onOk: () => resolve(),
          onCancel: () => {},
        })
      })
    }
    try {
      await startIteration(taskId)
      app.message.success(task?.status === 'completed' ? '已重新开始迭代' : '迭代已开始')
      await loadTask()
    } catch {
      /* 错误统一提示 */
    }
  }

  // 停止迭代
  const handleStop = () => {
    app.modal.confirm({
      title: '停止迭代',
      content: '确定停止当前迭代吗？已产生的结果将被保留。',
      okText: '停止',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await stopIteration(taskId)
          app.message.success('已停止')
          await loadTask()
        } catch {
          /* 错误统一提示 */
        }
      },
    })
  }

  // 导出报告（markdown / json）
  const handleExport = async (format: 'markdown' | 'json') => {
    try {
      const blob = await exportReport(taskId, format)
      const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
      downloadBlob(blob, `report_task_${taskId}_${date}.${format === 'json' ? 'json' : 'md'}`)
    } catch {
      /* 错误统一提示 */
    }
  }

  if (loading && !task) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', padding: '120px 0' }}>
        <Spin />
      </div>
    )
  }
  if (!task) {
    return (
      <div style={{ textAlign: 'center', padding: '120px 0', color: 'var(--pe-muted-foreground)' }}>
        任务不存在或已删除
        <div style={{ marginTop: 16 }}>
          <button className="pe-btn pe-btn-line pe-btn-sm" onClick={() => navigate('/tasks')}>
            返回任务列表
          </button>
        </div>
      </div>
    )
  }

  const running = task.status === 'running'
  const liveRound = running ? progress?.current_round ?? task.current_round : task.current_round

  return (
    <div>
      <button className="pe-back" onClick={() => navigate('/tasks')}>
        <ArrowLeftOutlined />
        返回任务列表
      </button>

      {/* 看板头部 */}
      <div className="pe-board-head">
        <div>
          <h1 className="pe-board-title">{task.name}</h1>
          <div className="pe-board-sub">
            <span className="pe-sub-italic">/task detail · {task.task_type}</span>
            <StatusBadge status={task.status} />
            <span style={{ color: 'var(--pe-muted-foreground)', fontSize: 12.5 }}>
              {TASK_TYPE_LABEL[task.task_type] || task.task_type} · 创建于 {formatTime(task.created_at).slice(0, 16)}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 26, flexWrap: 'wrap' }}>
          <div className="pe-rounds">
            <div>
              <span className="r-label">ROUND</span>
              <span className="tnum">{String(liveRound).padStart(2, '0')}</span>
              <span className="pe-slash">／</span>
              <span className="r-total tnum">{String(task.max_rounds).padStart(2, '0')}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {CAN_START.includes(task.status) && (
              <button className="pe-btn pe-btn-blue pe-btn-sm" onClick={handleStart}>
                <CaretRightOutlined />
                {task.status === 'stopped' ? '继续迭代' : task.status === 'completed' ? '重新迭代' : '开始迭代'}
              </button>
            )}
            {running && (
              <button className="pe-btn pe-btn-danger pe-btn-sm" onClick={handleStop}>
                <StopOutlined />
                停止
              </button>
            )}
            {task.status === 'completed' && (
              <>
                <button className="pe-btn pe-btn-line pe-btn-sm" onClick={() => handleExport('markdown')}>
                  <ExportOutlined />
                  MD
                </button>
                <button className="pe-btn pe-btn-line pe-btn-sm" onClick={() => handleExport('json')}>
                  <ExportOutlined />
                  JSON
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 块状页签 */}
      <div className="pe-tabs" role="tablist">
        {TABS.map((t, i) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={activeTab === t.key}
            className={`pe-tab-block ${activeTab === t.key ? 'is-active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            <span className="tab-idx">{String(i + 1).padStart(2, '0')}</span>
            {t.cn}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <TaskOverview task={task} progress={progress} onStart={handleStart} onStop={handleStop} onExport={handleExport} />
      )}
      {activeTab === 'iteration' && (
        <TaskIteration taskId={taskId} task={task} progress={progress} onRefresh={loadTask} onStart={handleStart} />
      )}
      {activeTab === 'cases' && <TaskCases taskId={taskId} running={task.status === 'running'} onRefresh={loadTask} />}
      {activeTab === 'report' && <TaskReport taskId={taskId} onExport={handleExport} />}
    </div>
  )
}
