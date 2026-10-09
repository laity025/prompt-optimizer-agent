// ==========================================================
// 多模型对标评测页：选任务与模型 → 发起评测 → 全部历史(跨任务) → 结果详情/矩阵
// 进入页面即展示全部评测历史，任务选择仅作为筛选；历史全宽，详情+矩阵在下文全宽展示
// ==========================================================
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button, Card, Empty, Input, Radio, Select, Space, Spin, Table, Tag, App,
} from 'antd'
import {
  ExportOutlined, ShareAltOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import type { TableColumnsType } from 'antd'
import PageHeader from '@/components/PageHeader'
import ShareModal from '@/components/ShareModal'
import { modelOptionLabel } from '@/components/modelOptionLabel'
import {
  exportBenchmark, getBenchmark, getModels, listAllBenchmarks,
  listTasks, startBenchmark,
} from '@/api/task'
import {
  type BenchmarkMatrixRow, type BenchmarkReport, type BenchmarkRunItem,
  type ModelInfo, type TaskListItem,
} from '@/types'
import { downloadBlob, formatTime } from '@/utils'

// 评测提示词来源选项
const PROMPT_MODES = [
  { label: '当前最优', value: 'best' },
  { label: '初始提示词', value: 'initial' },
  { label: '自定义', value: 'custom' },
]

// 评测运行状态中文映射
const RUN_STATUS: Record<string, { text: string; color: string }> = {
  running: { text: '评测中', color: '#0E4AC3' },
  completed: { text: '已完成', color: '#16A34A' },
  failed: { text: '失败', color: '#F03A3E' },
}

function renderScore(v: number | null | undefined): React.ReactNode {
  return v == null ? '—' : v.toFixed(1)
}

// 汇总头“最优模型”显示：分数并列时不点名单一模型，展示“并列”
function bestModelText(report: BenchmarkReport | null): { label: string; tie: boolean } {
  if (!report?.run) return { label: '—', tie: false }
  const { best_model, best_score } = report.run
  if (best_model) return { label: best_model, tie: false }
  if (best_score != null) {
    const tied = (report.models || []).filter((m) => m.avg_score === best_score).length
    return { label: `并列（${tied || ''} 个模型）`, tie: tied > 0 }
  }
  return { label: '—', tie: false }
}

export default function ModelBenchmark() {
  const app = App.useApp()
  const [tasks, setTasks] = useState<TaskListItem[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  // 评测配置表单
  const [taskId, setTaskId] = useState<number>()
  const [selModels, setSelModels] = useState<string[]>([])
  const [promptMode, setPromptMode] = useState<string>('best')
  const [customPrompt, setCustomPrompt] = useState('')
  const [runName, setRunName] = useState('')
  const [starting, setStarting] = useState(false)
  // 全部评测历史（跨任务）
  const [allRuns, setAllRuns] = useState<BenchmarkRunItem[]>([])
  const [report, setReport] = useState<BenchmarkReport | null>(null)
  const [activeRunId, setActiveRunId] = useState<number>()
  const [detailLoading, setDetailLoading] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)

  // 首次加载：可选任务、模型列表、全部评测历史（无需先选任务）
  useEffect(() => {
    listTasks({ page: 1, page_size: 100 }).then((d) => setTasks(d.items || [])).catch(() => {})
    getModels().then((d) => setModels(d || [])).catch(() => {})
    refreshAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const refreshAll = useCallback(async () => {
    try {
      const d = await listAllBenchmarks()
      setAllRuns(d.items || [])
      return d.items || []
    } catch {
      return []
    }
  }, [])

  // 选中的任务作为筛选条件：展示该任务的评测；空则展示全部
  const filteredRuns = useMemo(
    () => (taskId ? allRuns.filter((r) => r.task_id === taskId) : allRuns),
    [allRuns, taskId],
  )

  // 切换任务筛选时，清空已选中的详情（避免展示其他任务的旧结果残留）
  useEffect(() => {
    setReport(null)
    setActiveRunId(undefined)
  }, [taskId])

  // 后台评测运行轮询：存在 running 时每 2.5s 刷新；结束后自动加载当前详情
  const anyRunning = allRuns.some((r) => r.status === 'running')
  useEffect(() => {
    if (!anyRunning) return
    const timer = setInterval(async () => {
      const items = await refreshAll()
      if (activeRunId) {
        const who = items.find((r) => r.id === activeRunId)
        if (who && who.task_id && who.status !== 'running') loadDetail(who.task_id, activeRunId)
      }
      if (!items.some((r) => r.status === 'running')) clearInterval(timer)
    }, 2500)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anyRunning, activeRunId, refreshAll])

  const loadDetail = async (tid: number, runId: number) => {
    setDetailLoading(true)
    try {
      const data = await getBenchmark(tid, runId)
      setReport(data)
      setActiveRunId(runId)
    } catch {
      /* 错误已统一提示 */
    } finally {
      setDetailLoading(false)
    }
  }

  // 发起评测：需要选定任务（评测是针对某个任务执行的）
  const handleStart = async () => {
    if (!taskId) {
      app.message.warning('请先选择需要进行评测的任务')
      return
    }
    if (selModels.length === 0) {
      app.message.warning('请至少选择一个参与对比的模型')
      return
    }
    if (promptMode === 'custom' && !customPrompt.trim()) {
      app.message.warning('自定义模式下请填写评测提示词')
      return
    }
    setStarting(true)
    try {
      await startBenchmark(taskId, {
        models: selModels,
        prompt_mode: promptMode,
        prompt: promptMode === 'custom' ? customPrompt : undefined,
        name: runName.trim(),
      })
      app.message.success('评测已启动，完成后将自动刷新结果')
      const items = await refreshAll()
      const newest = items.find((r) => r.task_id === taskId) ?? items[0]
      if (newest) loadDetail(newest.task_id ?? taskId, newest.id)
    } catch {
      /* 错误已统一提示 */
    } finally {
      setStarting(false)
    }
  }

  const handleExport = async (runId: number) => {
    const target = allRuns.find((r) => r.id === runId)
    if (!target?.task_id) return
    try {
      const blob = await exportBenchmark(target.task_id, runId)
      downloadBlob(blob, `benchmark_${target.task_id}_run_${runId}.md`)
    } catch {
      /* 错误已统一提示 */
    }
  }

  // 得分矩阵表格：行为用例，列为模型
  const matrixColumns = useMemo(() => {
    const base: TableColumnsType<BenchmarkMatrixRow> = [
      {
        title: '用例',
        dataIndex: 'case_id',
        width: '40%',
        render: (_v: number, row: BenchmarkMatrixRow) => {
          const info = report?.cases.find((c) => c.case_id === row.case_id)
          return (
            <div>
              <span className="tnum" style={{ color: '#0E4AC3', fontWeight: 700 }}>#{row.case_id}</span>
              <div style={{ color: '#4b5563', fontSize: 13, marginTop: 2 }}>{info?.input_text || ''}</div>
            </div>
          )
        },
      },
      ...(report?.models_order || []).map((m) => ({
        title: <Tag color="geekblue" style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>{m}</Tag>,
        key: m,
        width: '20%',
        align: 'center' as const,
        render: (_: unknown, row: BenchmarkMatrixRow) => {
          const cell = row.models.find((c) => c.model === m)
          const score = cell?.score
          const failed = cell?.error_reason
          return (
            <span className="tnum" style={{ fontWeight: 700, color: failed ? '#F03A3E' : '#0E4AC3' }}>
              {score == null ? (failed ? '失败' : '—') : score.toFixed(1)}
            </span>
          )
        },
      })),
    ]
    return base
  }, [report])

  // 展开行：展示各模型在该用例下的输出与评审理由
  const expandedRender = (row: BenchmarkMatrixRow) => (
    <div style={{ padding: '4px 8px' }}>
      {row.models.map((c) => (
        <Card
          key={c.model}
          size="small"
          style={{ marginBottom: 8 }}
          title={<Tag color="geekblue">{c.model}</Tag>}
        >
          {c.error_reason ? (
            <div style={{ color: '#F03A3E' }}>执行失败：{c.error_reason}</div>
          ) : (
            <>
              <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 2 }}>模型输出</div>
              <div style={{ whiteSpace: 'pre-wrap', marginBottom: 8 }}>{c.output || '（空）'}</div>
              {c.judge_reason && (
                <>
                  <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 2 }}>
                    评审（{c.judge_score == null ? '—' : `${c.judge_score}分`}）
                  </div>
                  <div style={{ color: '#4b5563', fontSize: 13 }}>{c.judge_reason}</div>
                </>
              )}
            </>
          )}
        </Card>
      ))}
    </div>
  )

  // 历史列表列（含所属任务展示，便于跨任务浏览）
  const runColumns: TableColumnsType<BenchmarkRunItem> = [
    { title: 'ID', dataIndex: 'id', width: 60, render: (v: number) => <span className="tnum">#{v}</span> },
    { title: '评测名称', dataIndex: 'name' },
    {
      title: '所属任务', dataIndex: 'task_name', width: 160,
      render: (v: string | undefined) => <span style={{ fontSize: 13 }}>{v || '—'}</span>,
    },
    {
      title: '对比模型', dataIndex: 'models',
      render: (ms: string[]) => (
        <Space size={4} wrap>
          {ms.slice(0, 4).map((m) => <Tag key={m} color="geekblue">{m}</Tag>)}
          {ms.length > 4 && <Tag>+{ms.length - 4}</Tag>}
        </Space>
      ),
    },
    {
      title: '状态', dataIndex: 'status',
      render: (s: string) => {
        const meta = RUN_STATUS[s] || { text: s, color: 'default' }
        return <Tag color={meta.color}>{meta.text}</Tag>
      },
    },
    {
      title: '最优模型', dataIndex: 'best_model',
      render: (_: unknown, r: BenchmarkRunItem) => (
        r.best_model
          ? <Tag color="blue">{r.best_model}</Tag>
          : (r.best_score != null ? <Tag color="purple">并列</Tag> : '—')
      ),
    },
    {
      title: '最优得分', dataIndex: 'best_score',
      align: 'right' as const,
      render: (v: number | null) => <span className="tnum" style={{ fontWeight: 700 }}>{renderScore(v)}</span>,
    },
    {
      title: '发起时间', dataIndex: 'created_at',
      render: (v: string) => <span className="tnum" style={{ color: '#6b7280' }}>{formatTime(v).slice(0, 16)}</span>,
    },
    {
      title: '操作',
      key: 'op',
      width: 150,
      render: (_: unknown, r: BenchmarkRunItem) => (
        <Space size={4}>
          <Button size="small" type={r.id === activeRunId ? 'primary' : 'default'} disabled={!r.task_id}
                  onClick={() => r.task_id && loadDetail(r.task_id, r.id)}>
            查看
          </Button>
          <Button size="small" icon={<ExportOutlined />} disabled={r.status !== 'completed' || !r.task_id}
                  onClick={() => handleExport(r.id)}>
            导出
          </Button>
        </Space>
      ),
    },
  ]

  const best = bestModelText(report)

  return (
    <div>
      <PageHeader
        title="模型评测"
        extra={
          <Button type="primary" icon={<ThunderboltOutlined />} loading={starting}
                  onClick={handleStart}>
            开始评测
          </Button>
        }
      />

      {/* 评测配置卡片 */}
      <div className="pe-card" style={{ padding: '18px 20px' }}>
        <Space size={24} wrap align="start">
          <div style={{ minWidth: 240 }}>
            <div className="bm-field-label">任务（发起评测时需要）</div>
            <Select
              showSearch
              style={{ width: 260 }}
              placeholder="选择要评测的任务"
              optionFilterProp="label"
              value={taskId}
              onChange={setTaskId}
              options={tasks.map((t) => ({ label: t.name, value: t.id }))}
            />
          </div>
          <div style={{ minWidth: 300 }}>
            <div className="bm-field-label">参与对比的模型（可多选）</div>
            <Select
              mode="multiple"
              style={{ width: 360 }}
              placeholder="选择模型，例如 DeepSeek-V4-Flash"
              value={selModels}
              onChange={setSelModels}
              options={models.map((m) => ({ label: modelOptionLabel(m), value: m.id }))}
            />
          </div>
          <div>
            <div className="bm-field-label">评测提示词来源</div>
            <Radio.Group value={promptMode} onChange={(e) => setPromptMode(e.target.value)}
                          options={PROMPT_MODES} optionType="button" />
          </div>
        </Space>
        {promptMode === 'custom' && (
          <div style={{ marginTop: 14 }}>
            <Input.TextArea
              rows={3}
              placeholder="输入用于评测的提示词（custom 模式）"
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
            />
          </div>
        )}
        <div style={{ marginTop: 12 }}>
          <div className="bm-field-label">评测名称（可选）</div>
          <Input
            style={{ width: 380 }}
            placeholder="留空则自动命名"
            value={runName}
            onChange={(e) => setRunName(e.target.value)}
            allowClear
          />
        </div>
      </div>

      {/* 历史：默认展示全部任务，选择任务后展示该任务 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '14px 2px 10px' }}>
        <span style={{ fontSize: 12, color: '#6b7280' }}>
          评测历史默认展示全部任务，选择任务可筛选；点击“查看”展示得分明细
        </span>
        {taskId && (
          <Tag closable onClose={() => setTaskId(undefined)} color="blue">
            筛选：{tasks.find((t) => t.id === taskId)?.name || ''}
          </Tag>
        )}
      </div>
      <div className="pe-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="bm-card-head" style={{ padding: '14px 18px' }}>
          <h3 className="pe-subtitle">评测历史（{filteredRuns.length}）</h3>
        </div>
        <Table<BenchmarkRunItem>
          rowKey="id"
          dataSource={filteredRuns}
          columns={runColumns}
          size="middle"
          pagination={{ pageSize: 8, showSizeChanger: false }}
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有评测记录" /> }}
        />
      </div>

      {/* 详情：选中某次评测后全宽展示 */}
      {report && (
        <div className="pe-card" style={{ marginTop: 18, padding: 0, overflow: 'hidden' }}>
          <div className="bm-card-head" style={{ padding: '14px 18px' }}>
            <h3 className="pe-subtitle">结果详情</h3>
            {report.run.status === 'completed' && (
              <Button size="small" icon={<ShareAltOutlined />} style={{ marginLeft: 'auto' }} onClick={() => setShareOpen(true)}>
                分享报告
              </Button>
            )}
          </div>
          <Spin spinning={detailLoading}>
            <div style={{ padding: 16 }}>
              <div className="bm-summary">
                <div className="bm-summary-block">
                  <div className="bm-field-label">最优模型</div>
                  <div style={{ fontSize: 18, fontWeight: 800 }}>
                    {best.tie
                      ? <Tag color="purple" style={{ fontSize: 14, padding: '2px 8px' }}>{best.label}</Tag>
                      : best.label !== '—' && (
                        <Tag color="blue" style={{ fontSize: 14, padding: '2px 8px' }}>{best.label}</Tag>
                      )}
                  </div>
                </div>
                <div className="bm-summary-block">
                  <div className="bm-field-label">最优得分</div>
                  <div className="tnum" style={{ fontSize: 22, fontWeight: 800, color: '#0E4AC3' }}>
                    {renderScore(report.run.best_score)}
                  </div>
                </div>
                <div className="bm-summary-block">
                  <div className="bm-field-label">状态</div>
                  <Tag color={(RUN_STATUS[report.run.status] || { color: 'default' }).color}>
                    {(RUN_STATUS[report.run.status] || { text: report.run.status }).text}
                  </Tag>
                </div>
                <div className="bm-summary-block" style={{ flex: 1, minWidth: 160 }}>
                  <div className="bm-field-label">发起时间</div>
                  <span className="tnum" style={{ color: '#6b7280' }}>{formatTime(report.run.created_at).slice(0, 16)}</span>
                </div>
              </div>

              {/* 各模型平均分横向条 */}
              <div style={{ margin: '14px 0 4px' }}>
                <div className="bm-field-label">各模型平均得分</div>
                {report.models.map((m) => {
                  const maxScore = Math.max(0.0001, ...report.models.map((x) => x.avg_score || 0))
                  const pct = m.avg_score ? Math.round((m.avg_score / maxScore) * 100) : 0
                  return (
                    <div key={m.model} style={{ marginTop: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#6b7280' }}>
                        <span style={{ maxWidth: '70%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {m.model}
                        </span>
                        <span className="tnum" style={{ fontWeight: 700, color: best.tie ? '#7C3AED' : (m.model === report.run.best_model ? '#16A34A' : '#111827') }}>
                          {renderScore(m.avg_score)}
                        </span>
                      </div>
                      <div style={{ height: 8, borderRadius: 4, background: '#eef2f9', marginTop: 3, overflow: 'hidden' }}>
                        <div
                          style={{ height: '100%', width: `${pct}%`, background: best.tie ? '#7C3AED' : (m.model === report.run.best_model ? '#16A34A' : '#0E4AC3'), borderRadius: 4 }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>

              <div style={{ marginTop: 14 }}>
                <div className="bm-field-label">评测提示词</div>
                <pre style={{ whiteSpace: 'pre-wrap', background: '#f6f8fc', borderRadius: 8, padding: 10, fontSize: 12, color: '#374151', maxHeight: 120, overflow: 'auto' }}>
                  {report.run.prompt_snapshot || '（无）'}
                </pre>
              </div>
            </div>
          </Spin>
        </div>
      )}

      {/* 用例×模型得分矩阵：选中后全宽展示 */}
      {report && (
        <div className="pe-card" style={{ padding: 0, overflow: 'hidden', marginTop: 14 }}>
          <div className="bm-card-head" style={{ padding: '14px 18px' }}>
            <h3 className="pe-subtitle">用例 × 模型得分矩阵</h3>
          </div>
          <Table<BenchmarkMatrixRow>
            rowKey="case_id"
            dataSource={report.matrix}
            columns={matrixColumns}
            size="middle"
            expandable={{ expandedRowRender: expandedRender }}
            pagination={false}
          />
        </div>
      )}
      <ShareModal
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        reportType="benchmark"
        targetId={report?.run.id ?? 0}
        title="分享评测报告"
      />
    </div>
  )
}