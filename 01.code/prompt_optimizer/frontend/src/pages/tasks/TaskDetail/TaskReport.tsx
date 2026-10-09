// ==========================================================
// 报告子页：优化报告（总分/曲线/提示词/评审汇总/建议/版本差异）+ 导出
// ==========================================================
import { useEffect, useState } from 'react'
import { Spin, Timeline, Alert } from 'antd'
import { ExportOutlined, ShareAltOutlined } from '@ant-design/icons'
import { getReport } from '@/api/task'
import type { ReportData } from '@/types'
import ScoreChart from '@/components/ScoreChart'
import ShareModal from '@/components/ShareModal'
import { Panel, SectionTitle, StatCard, EmptyArt } from '@/components/ui'

interface Props {
  taskId: number
  onExport: (format: 'markdown' | 'json') => void
}

export default function TaskReport({ taskId, onExport }: Props) {
  const [report, setReport] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)

  useEffect(() => {
    setLoading(true)
    getReport(taskId)
      .then(setReport)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [taskId])

  if (loading) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', padding: '100px 0' }}>
        <Spin />
      </div>
    )
  }
  if (!report || report.score_curve.length === 0) {
    return (
      <Panel>
        <EmptyArt text="任务尚未完成迭代，暂无报告" />
      </Panel>
    )
  }

  const finalScore = report.score_curve[report.score_curve.length - 1]?.best_score

  return (
    <div>
      {/* 摘要 + 曲线 + 导出 */}
      <Panel style={{ marginBottom: 20 }}>
        <SectionTitle
          title={`优化报告 · ${report.task_name}`}
          en="report"
          extra={
            <span style={{ display: 'inline-flex', gap: 8 }}>
              <button className="pe-btn pe-btn-line pe-btn-sm" onClick={() => setShareOpen(true)}>
                <ShareAltOutlined />
                分享报告
              </button>
              <button className="pe-btn pe-btn-line pe-btn-sm" onClick={() => onExport('markdown')}>
                <ExportOutlined />
                Markdown
              </button>
              <button className="pe-btn pe-btn-line pe-btn-sm" onClick={() => onExport('json')}>
                <ExportOutlined />
                JSON
              </button>
            </span>
          }
        />

        <div className="pe-stat-row" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
          <StatCard label="最终最优得分" value={finalScore?.toFixed(1) ?? '—'} unit="分" />
          <StatCard label="迭代轮数" value={report.score_curve.length} unit="轮" />
        </div>

        <div style={{ marginTop: 4 }}>
          <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 8 }}>
            得分曲线 <span className="pe-sub-italic">/score curve</span>
          </div>
          <ScoreChart rounds={report.score_curve} height={260} />
        </div>
      </Panel>

      {/* 最优 / 初始提示词 */}
      <div className="pe-grid-2" style={{ marginBottom: 20 }}>
        <Panel>
          <SectionTitle title="最终最优提示词" en="final best" />
          <pre className="pe-prompt-box" style={{ margin: 0 }}>{report.best_prompt || '—'}</pre>
        </Panel>
        <Panel>
          <SectionTitle title="初始提示词" en="initial" />
          <pre className="pe-prompt-box" style={{ margin: 0 }}>{report.initial_prompt || '—'}</pre>
        </Panel>
      </div>

      {/* 优化建议 */}
      {report.suggestions.length > 0 && (
        <Panel style={{ marginBottom: 20 }}>
          <SectionTitle title="优化建议" en="suggestions" />
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 2, fontSize: 13.5, color: '#2a2a30' }}>
            {report.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Panel>
      )}

      {/* 各轮评审汇总 */}
      {report.judge_summary.length > 0 && (
        <Panel style={{ marginBottom: 20 }}>
          <SectionTitle title="各轮评审汇总" en="judge summary" />
          <Timeline
            items={report.judge_summary.map((j) => ({
              children: (
                <div>
                  <b>
                    第 {(j as { round?: number }).round ?? '?'} 轮 · 得分 {(j as { best_score?: number }).best_score ?? '—'}
                  </b>
                  <div className="prompt-box" style={{ fontSize: 13, color: 'var(--pe-muted-foreground)', marginTop: 4 }}>
                    {(j as { reason?: string }).reason || ''}
                  </div>
                </div>
              ),
            }))}
          />
        </Panel>
      )}

      {/* 版本差异 */}
      {report.version_diffs.length > 0 && (
        <Panel>
          <SectionTitle title="版本差异对比" en="version diff" />
          {report.version_diffs.map((d, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <Alert
                type="info"
                showIcon
                message={`从版本 ${(d as { from_no?: number }).from_no ?? '初始'} → 版本 ${(d as { to_no?: number }).to_no ?? '?'}`}
                description={
                  <div style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {(d as { added?: string })?.added && <div>新增：{(d as { added?: string }).added}</div>}
                    {(d as { removed?: string })?.removed && <div>删除：{(d as { removed?: string }).removed}</div>}
                    {(d as { changed?: string })?.changed && <div>调整：{(d as { changed?: string }).changed}</div>}
                  </div>
                }
              />
            </div>
          ))}
        </Panel>
      )}

      <ShareModal
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        reportType="task"
        targetId={taskId}
        title="分享任务迭代报告"
      />
    </div>
  )
}
