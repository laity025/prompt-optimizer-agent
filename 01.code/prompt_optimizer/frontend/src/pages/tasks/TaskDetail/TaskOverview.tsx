// ==========================================================
// 概览子页：指标卡 + 运行进度 + 最优提示词 + 初始/最优差异对比
// ==========================================================
import { App } from 'antd'
import { CopyOutlined, CaretRightOutlined, SyncOutlined } from '@ant-design/icons'
import StatusBadge from '@/components/StatusBadge'
import PromptDiff from '@/components/PromptDiff'
import { Panel, SectionTitle, StatCard } from '@/components/ui'
import type { Task, IterationStatus } from '@/types'

interface Props {
  task: Task
  progress: IterationStatus | null
  onStart: () => void
  onStop: () => void
  onExport: (format: 'markdown' | 'json') => void
}

export default function TaskOverview({ task, progress, onStart }: Props) {
  const app = App.useApp()
  const running = task.status === 'running'
  const liveRound = running ? progress?.current_round ?? task.current_round : task.current_round
  const percent =
    running && progress && progress.variants_total > 0
      ? Math.round((progress.variants_done / progress.variants_total) * 100)
      : 0

  // 复制文本到剪贴板
  const copyText = async (text?: string | null) => {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      app.message.success('已复制')
    } catch {
      app.message.error('复制失败')
    }
  }

  return (
    <div>
      {/* 指标卡 */}
      <div className="pe-stat-row">
        <StatCard label="任务状态" value={<StatusBadge status={task.status} />} />
        <StatCard label="当前轮次" value={String(liveRound).padStart(2, '0')} unit={`/ ${task.max_rounds} 轮`} />
        <StatCard label="最优得分" value={task.best_score == null ? '—' : task.best_score.toFixed(1)} unit={task.best_score == null ? '' : '分'} />
        <StatCard label="每轮变体" value={task.variants_per_round} unit={`个 · 并发 ${task.concurrency}`} />
      </div>

      {/* 运行中实时进度 */}
      {running && progress && (
        <Panel style={{ marginBottom: 20 }}>
          <SectionTitle title="本轮执行进度" en="running progress" extra={<span className="pe-sub-italic">live</span>} />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 10 }}>
            <span className="pe-score" style={{ fontSize: 56 }}>
              {percent}
              <small style={{ fontSize: 18, fontFamily: 'var(--pe-font-sans)', color: 'var(--pe-muted-foreground)' }}>%</small>
            </span>
            <span style={{ fontSize: 13, color: 'var(--pe-muted-foreground)' }}>
              变体 {progress.variants_done}/{progress.variants_total}
            </span>
          </div>
          <div className="pe-progress">
            <span style={{ width: `${percent}%` }} />
          </div>
          <div style={{ display: 'flex', gap: 22, marginTop: 14, fontSize: 12.5, color: 'var(--pe-muted-foreground)', flexWrap: 'wrap' }}>
            <span>用例 {progress.cases_done}/{progress.cases_total}</span>
            <span style={{ color: 'var(--state-success)', fontWeight: 700 }}>成功 {progress.cases_success}</span>
            <span style={{ color: 'var(--state-error)', fontWeight: 700 }}>失败 {progress.cases_failed}</span>
            <span>第 {progress.current_round} 轮</span>
          </div>
        </Panel>
      )}

      {/* 待运行引导 */}
      {task.status === 'pending' && (
        <Panel style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap' }}>
            <div>
              <SectionTitle title="任务就绪，开始首轮迭代" en="ready to start" />
              <div style={{ fontSize: 13, color: 'var(--pe-muted-foreground)' }}>
                系统将依据任务描述与评分标准自动生成初始提示词，并逐轮生成变体、执行评估、择优进化。
              </div>
            </div>
            <button className="pe-btn pe-btn-blue" onClick={onStart}>
              <CaretRightOutlined />
              开始首次迭代
            </button>
          </div>
        </Panel>
      )}

      {/* 最优提示词 */}
      <Panel style={{ marginBottom: 20 }}>
        <SectionTitle
          title="当前最优提示词"
          en="best prompt"
          extra={
            task.best_score != null ? (
              <span style={{ fontFamily: 'var(--pe-font-display)', fontWeight: 900, fontSize: 22, letterSpacing: '-0.02em' }}>
                {task.best_score.toFixed(1)}
                <small style={{ fontSize: 12, fontFamily: 'var(--pe-font-sans)', color: 'var(--pe-muted-foreground)', marginLeft: 3 }}>分</small>
              </span>
            ) : undefined
          }
        />
        <div className="pe-prompt-box">
          <button type="button" className="pe-ico-btn" title="复制" disabled={!task.best_prompt} onClick={() => copyText(task.best_prompt)}>
            <CopyOutlined />
          </button>
          {task.best_prompt || '尚未产生最优提示词'}
        </div>

        {task.initial_prompt && task.best_prompt && task.initial_prompt !== task.best_prompt && (
          <div style={{ marginTop: 22 }}>
            <SectionTitle title="初始与最优差异对比" en="diff" />
            <PromptDiff oldText={task.initial_prompt} newText={task.best_prompt} />
          </div>
        )}
      </Panel>

      {/* 停止 / 失败提示 */}
      {(task.status === 'stopped' || task.status === 'failed') && (
        <Panel>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--state-warning)', fontWeight: 700, fontSize: 13.5 }}>
            <SyncOutlined />
            {task.status === 'stopped'
              ? '任务已停止，可点击「继续迭代」从上次轮次断点续跑。'
              : `任务失败：${task.last_error || '未知错误'}`}
          </div>
        </Panel>
      )}
    </div>
  )
}
