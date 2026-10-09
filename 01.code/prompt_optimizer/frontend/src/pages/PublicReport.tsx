// ==========================================================
// 公开报告页（免登录）：/share/:token
// 按分享类型渲染 模型评测 / 工作流优化 / 任务迭代 的只读报告
// 不在登录布局内，任何持有链接的人均可查看
// ==========================================================
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Button, Card, Col, Empty, Row, Spin, Tag } from 'antd'
import * as echarts from 'echarts'
import * as shareApi from '@/api/reportShare'
import { formatTime } from '@/utils'
import type {
  BenchmarkCell,
  BenchmarkMatrixRow,
  BenchmarkReport,
  PublicReportData,
  ReportData,
  ReportShareType,
  WorkflowOptReport,
} from '@/types'

const TYPE_LABEL: Record<ReportShareType, string> = {
  benchmark: '多模型对比评测',
  optimization: '工作流步骤优化',
  task: '任务迭代报告',
}

const renderScore = (v: number | null | undefined) =>
  v == null ? '—' : Number(v.toFixed(2))

export default function PublicReport() {
  const { token = '' } = useParams()
  const [data, setData] = useState<PublicReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    shareApi.getPublicReportData(token).then((d) => {
      if (!cancelled) { setData(d); setError(null) }
    }).catch(() => {
      if (!cancelled) { setData(null); setError('该分享链接不存在、已被撤销或已过期') }
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [token])

  if (loading) {
    return <Centered><Spin size="large" tip="报告加载中…" /></Centered>
  }
  if (error || !data) {
    return (
      <Centered>
        <Card style={{ width: 420, textAlign: 'center' }}>
          <Empty description={error || '无法读取报告'} />
          <Button type="primary" onClick={() => window.location.reload()} style={{ marginTop: 8 }}>
            重新加载
          </Button>
        </Card>
      </Centered>
    )
  }

  return (
    <div className="pub-wrap">
      <header className="pub-topbar">
        <div className="pub-brand">
          <span className="pub-brand-mark" />
          <span>
            <b>PROMPT EVOLVER</b>
            <span className="pub-brand-sub">提示词迭代智能体 · 公开报告</span>
          </span>
        </div>
        <div style={{ fontSize: 12, color: '#9ca3af' }}>
          只读分享 · 访问 {data.meta.view_count} 次
          {data.meta.expires_at ? ` · 有效期至 ${formatTime(data.meta.expires_at).slice(0, 16)}` : ''}
        </div>
      </header>

      <main className="pub-main">
        <div className="pub-head">
          <Tag color="geekblue">{TYPE_LABEL[data.meta.report_type]}</Tag>
          <h1 className="pub-title">{data.meta.title}</h1>
        </div>

        {data.meta.report_type === 'benchmark' && <BenchmarkBody data={data as PublicReportData<BenchmarkReport>} />}
        {data.meta.report_type === 'optimization' && <OptimizationBody data={data as PublicReportData<WorkflowOptReport>} />}
        {data.meta.report_type === 'task' && <TaskBody data={data as PublicReportData<ReportData>} />}
      </main>
      <style>{`body{margin:0;background:#f5f6f8}`}</style>
    </div>
  )
}

function BenchmarkBody({ data }: { data: PublicReportData<BenchmarkReport> }) {
  const p = data.payload
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Row gutter={12}>
        <Col xs={24} lg={8}>
          <Card size="small" title="各模型平均得分" styles={{ body: { padding: 8 } }}>
            <Bars models={p.models} />
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card size="small" title="评测信息" styles={{ body: { padding: 16 } }}>
            <InfoRow label="最优模型" value={p.run.best_model ? <Tag color="blue">{p.run.best_model}</Tag> : '—'} />
            <InfoRow label="最优得分" value={<b style={{ color: '#0E4AC3' }}>{renderScore(p.run.best_score)}</b>} />
            <InfoRow label="参与模型" value={p.models_order.join(' 、')} />
            <InfoRow label="发起时间" value={formatTime(p.run.created_at).slice(0, 16)} />
            <InfoRow label="评测提示词" value={p.run.prompt_snapshot || '—'} />
          </Card>
        </Col>
      </Row>

      <Card size="small" title={`用例 × 模型 得分矩阵（${p.cases.length} 用例）`} styles={{ body: { padding: 8 } }}>
        <TableLike data={p} />
      </Card>
    </div>
  )
}

function OptimizationBody({ data }: { data: PublicReportData<WorkflowOptReport> }) {
  const p = data.payload
  const improved = p.opt.improved
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Row gutter={12}>
        <Col xs={24} lg={8}>
          <Card size="small" title="优化效果" styles={{ body: { padding: 16 } }}>
            <InfoRow label="基准整链分" value={renderScore(p.opt.base_score)} />
            <InfoRow label="优化后整链分" value={<b style={{ color: improved ? '#16a34a' : '#d97706' }}>{renderScore(p.opt.best_score)}</b>} />
            <InfoRow label="提升" value={improved ? `+${renderScore((p.opt.best_score || 0) - (p.opt.base_score || 0))}` : '无提升'} />
            <InfoRow label="状态" value={p.opt.status === 'completed' ? '已完成' : p.opt.status} />
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card size="small" title={`指令前后对照（步骤 ${p.opt.step_seq}）`} styles={{ body: { padding: 16 } }}>
            <PromptBlock label="优化前" text={p.opt.base_prompt} />
            {p.opt.best_prompt && <PromptBlock label="优化后" text={p.opt.best_prompt} highlight />}
          </Card>
        </Col>
      </Row>
      <Card size="small" title={`各轮变体（${p.variants.length}）`} styles={{ body: { padding: 8 } }}>
        {(p.variants || []).map((v) => (
          <div key={v.id} className="pub-item">
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <Tag color="geekblue">R{v.round_no} #{v.variant_no}</Tag>
              <Tag>{v.strategy_tag}</Tag>
              {v.is_best === 1 && <Tag color="green">本轮最优</Tag>}
              {v.avg_score != null && <span className="pub-score">{v.avg_score.toFixed(1)} 分</span>}
            </div>
            <div className="pub-text">{v.prompt_text}</div>
          </div>
        ))}
      </Card>
    </div>
  )
}

function TaskBody({ data }: { data: PublicReportData<ReportData> }) {
  const p = data.payload
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card size="small" title="最优提示词" styles={{ body: { padding: 16 } }}>
        <PromptBlock label="最优" text={p.best_prompt || '（无）'} highlight />
        <PromptBlock label="初始" text={p.initial_prompt || '（无）'} />
      </Card>

      {(p.score_curve || []).length > 0 && (
        <Card size="small" title="迭代得分曲线" styles={{ body: { padding: 8 } }}>
          <CurveLine points={p.score_curve} />
        </Card>
      )}

      {(p.judge_summary || []).length > 0 && (
        <Card size="small" title="每轮评审总结" styles={{ body: { padding: 8 } }}>
          {(p.judge_summary as { round: number; best_score?: number | null; reason?: string }[]).map((j, i) => (
            <div key={i} className="pub-item">
              <div style={{ fontWeight: 600 }}>第 {j.round} 轮（{renderScore(j.best_score)} 分）</div>
              <div className="pub-reason">{j.reason || '（无评审理由）'}</div>
            </div>
          ))}
        </Card>
      )}

      {(p.suggestions || []).length > 0 && (
        <Card size="small" title="优化建议" styles={{ body: { padding: 8 } }}>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {(p.suggestions || []).map((s, i) => <li key={i} className="pub-reason">{s}</li>)}
          </ul>
        </Card>
      )}
    </div>
  )
}

/* ---------- 公开页辅助小组件 ---------- */

function Centered({ children }: { children: React.ReactNode }) {
  return <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{children}</div>
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, wordBreak: 'break-all' }}>{value}</div>
    </div>
  )
}

function PromptBlock({ label, text, highlight }: { label: string; text: string; highlight?: boolean }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 4 }}>{label}</div>
      <pre className={`pub-prompt${highlight ? ' is-highlight' : ''}`}>{text}</pre>
    </div>
  )
}

function Bars({ models }: { models: { model: string; avg_score?: number | null }[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 44, right: 12, top: 20, bottom: 8 },
      xAxis: {
        type: 'category', data: (models || []).map((m) => m.model),
        axisLabel: { fontSize: 10, interval: 0, width: 120, overflow: 'truncate' },
      },
      yAxis: { type: 'value', min: 0, max: 100 },
      series: [{ type: 'bar', barMaxWidth: 40, itemStyle: { color: '#0E4AC3' }, data: (models || []).map((m) => m.avg_score ?? 0) }],
    })
    return () => chart.dispose()
  }, [models])
  return <div ref={ref} style={{ height: 240, width: '100%' }} />
}

function CurveLine({ points }: { points: { round: number; best_score: number }[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    const data = [...points].sort((a, b) => a.round - b.round)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 44, right: 12, top: 20, bottom: 8 },
      xAxis: { type: 'category', data: data.map((c) => `第${c.round}轮`) },
      yAxis: { type: 'value', min: 0, max: 100 },
      series: [{ type: 'line', smooth: true, lineStyle: { color: '#0E4AC3', width: 3 }, data: data.map((c) => c.best_score) }],
    })
    return () => chart.dispose()
  }, [points])
  return <div ref={ref} style={{ height: 260, width: '100%' }} />
}

// 得分矩阵简易表格（避免引入额外表格组件复杂度）
function TableLike({ data }: { data: import('@/types').BenchmarkReport }) {
  const p = data
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="pub-table">
        <thead>
          <tr>
            <th>用例 / 模型</th>
            {p.models_order.map((m) => <th key={m}>{m}</th>)}
          </tr>
        </thead>
        <tbody>
          {p.matrix.map((row: BenchmarkMatrixRow) => (
            <tr key={row.case_id}>
              <td className="pub-case">
                {(p.cases.find((c) => c.case_id === row.case_id)?.input_text || '').slice(0, 40)}
              </td>
              {row.models.map((cell: BenchmarkCell) => (
                <td key={cell.model} className={cell.error_reason ? 'is-err' : ''}>
                  {cell.error_reason ? '失败' : renderScore(cell.score)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}