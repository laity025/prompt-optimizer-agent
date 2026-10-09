// ==========================================================
// 多步工作流页：选任务 → 编排步骤(支持 {{input}}/{{stepN.out}} 占位符) →
// 运行评测(异步) → 报告看板(端到端得分 + 步骤追踪 + 单 prompt 基线对照)
// ==========================================================
import { useCallback, useEffect, useState } from 'react'
import {
  App, Button, Card, Collapse, Empty, Input, List, Modal, Popconfirm,
  Select, Space, Spin, Switch, Tag, Tooltip,
} from 'antd'
import {
  DeleteOutlined, DownOutlined, PlusOutlined, RocketOutlined,
  SaveOutlined, UpOutlined, ApartmentOutlined, ThunderboltOutlined,
  HistoryOutlined, ShareAltOutlined,
} from '@ant-design/icons'
import PageHeader from '@/components/PageHeader'
import ShareModal from '@/components/ShareModal'
import { modelOptionLabel } from '@/components/modelOptionLabel'
import { getModels, listTasks } from '@/api/task'
import * as wfApi from '@/api/workflow'
import type { ModelInfo, TaskListItem, Workflow, WorkflowOptItem, WorkflowOptReport, WorkflowReport } from '@/types'
import { formatTime } from '@/utils'

const { TextArea } = Input

function scoreColor(v?: number | null) {
  const s = v ?? 0
  if (s >= 80) return '#16A34A'
  if (s >= 60) return '#F59E0B'
  return '#F03A3E'
}

const RUN_STATUS: Record<string, { text: string; color: string }> = {
  running: { text: '评测中', color: '#0E4AC3' },
  completed: { text: '已完成', color: '#16A34A' },
  failed: { text: '失败', color: '#F03A3E' },
}

const OPT_STATUS: Record<string, { text: string; color: string }> = {
  running: { text: '优化中', color: '#0E4AC3' },
  completed: { text: '已完成', color: '#16A34A' },
  failed: { text: '失败', color: '#F03A3E' },
}

interface StepDraft {
  seq: number
  name: string
  model: string
  output_var: string
  prompt_template: string
}

export default function WorkflowBoard() {
  const app = App.useApp()
  const [tasks, setTasks] = useState<TaskListItem[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [taskId, setTaskId] = useState<number>()
  const [wfs, setWfs] = useState<Workflow[]>([])
  const [activeWf, setActiveWf] = useState<Workflow>()
  // 编辑器草稿
  const [wfName, setWfName] = useState('')
  const [wfDesc, setWfDesc] = useState('')
  const [steps, setSteps] = useState<StepDraft[]>([])
  const [saving, setSaving] = useState(false)
  // 新建弹窗
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  // 运行
  const [runBaseline, setRunBaseline] = useState(true)
  const [running, setRunning] = useState(false)
  // 报告
  const [report, setReport] = useState<WorkflowReport | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [recentRunId, setRecentRunId] = useState<number>()
  // 步骤优化（Phase 5）
  const [optSetupOpen, setOptSetupOpen] = useState(false)       // 优化参数弹窗
  const [optStepSeq, setOptStepSeq] = useState<number>()
  const [optRounds, setOptRounds] = useState(3)
  const [optStarting, setOptStarting] = useState(false)
  const [optReport, setOptReport] = useState<WorkflowOptReport | null>(null) // 优化报告弹窗数据
  const [optReportOpen, setOptReportOpen] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const [optPolling, setOptPolling] = useState(false)
  const [optHistory, setOptHistory] = useState<WorkflowOptItem[]>([])        // 优化历史

  useEffect(() => {
    listTasks({ page: 1, page_size: 100 }).then((d) => setTasks(d.items || [])).catch(() => {})
    getModels().then((d) => setModels(d || [])).catch(() => {})
  }, [])

  const refreshWfs = useCallback(async (tid: number) => {
    try {
      const d = await wfApi.listWorkflows(tid)
      setWfs(d.items || [])
      return d.items || []
    } catch { return [] }
  }, [])

  useEffect(() => {
    if (!taskId) return
    setActiveWf(undefined); setReport(null); setRecentRunId(undefined)
    setOptReport(null); setOptHistory([]); setOptReportOpen(false)
    refreshWfs(taskId)
  }, [taskId, refreshWfs])

  const loadWf = async (wf: Workflow) => {
    setActiveWf(wf)
    setReport(null); setRecentRunId(undefined)
    setOptReport(null); setOptHistory([]); setOptReportOpen(false)
    try {
      const d = await wfApi.getWorkflow(taskId!, wf.id)
      setWfName(d.name); setWfDesc(d.description || '')
      setSteps((d.steps || []).map((s) => ({
        seq: s.seq, name: s.name, model: s.model || '',
        output_var: s.output_var || '', prompt_template: s.prompt_template,
      })))
    } catch { /* 统一提示 */ }
  }

  const startReportPoll = useCallback((tid: number, wfId: number, runId: number) => {
    setReportLoading(true)
    const timer = setInterval(async () => {
      try {
        const d = await wfApi.getRunReport(tid, wfId, runId)
        setReport(d)
        if (d.run.status === 'completed' || d.run.status === 'failed') {
          clearInterval(timer)
          setReportLoading(false)
        }
      } catch { clearInterval(timer); setReportLoading(false) }
    }, 2000)
    return () => clearInterval(timer)
  }, [])

  // 新建工作流
  const handleCreate = async () => {
    if (!taskId) return
    if (!newName.trim()) { app.message.warning('请输入工作流名称'); return }
    setCreating(true)
    try {
      const d = await wfApi.createWorkflow(taskId, { name: newName.trim() })
      app.message.success('工作流已创建')
      setCreateOpen(false); setNewName('')
      const list = await refreshWfs(taskId)
      const created = list.find((w) => w.id === d.id)
      if (created) await loadWf(created)
    } catch { /* 统一提示 */ } finally { setCreating(false) }
  }

  // 保存步骤编排（整体替换）
  const handleSave = async () => {
    if (!taskId || !activeWf) return
    const clean = steps.filter((s) => s.prompt_template.trim())
    if (clean.length === 0) { app.message.warning('至少保留一个含指令的步骤'); return }
    setSaving(true)
    try {
      const d = await wfApi.updateWorkflow(taskId, activeWf.id, {
        name: wfName.trim(), description: wfDesc.trim(),
        steps: clean.map((s, i) => ({ seq: i + 1, name: s.name, model: s.model, output_var: s.output_var, prompt_template: s.prompt_template })),
      })
      app.message.success('已保存')
      await refreshWfs(taskId)
      setActiveWf((prev) => prev ? { ...prev, name: d.name, step_count: d.step_count, steps: d.steps } : prev)
    } catch { /* 统一提示 */ } finally { setSaving(false) }
  }

  // 运行评测
  const handleRun = async () => {
    if (!taskId || !activeWf) return
    setRunning(true)
    try {
      const r = await wfApi.runWorkflow(taskId, activeWf.id, runBaseline)
      setRecentRunId(r.run_id)
      setReport(null)
      startReportPoll(taskId, activeWf.id, r.run_id)
    } catch { /* 统一提示 */ } finally { setRunning(false) }
  }

  const moveStep = (idx: number, dir: -1 | 1) => {
    setSteps((prev) => {
      const nxt = prev.slice()
      const to = idx + dir
      if (to < 0 || to >= nxt.length) return prev
      ;[nxt[idx], nxt[to]] = [nxt[to], nxt[idx]]
      return nxt.map((s, i) => ({ ...s, seq: i + 1 }))
    })
  }

  const setStep = (idx: number, patch: Partial<StepDraft>) => {
    setSteps((prev) => prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)))
  }

  // ---------- 步骤自动迭代优化（Phase 5） ----------
  // 优化完成后刷新步骤草稿，展示回写后的最优 prompt
  const reloadStepsFromWf = async (wfId: number) => {
    if (!taskId) return
    try {
      const d = await wfApi.getWorkflow(taskId, wfId)
      setSteps((d.steps || []).map((s) => ({
        seq: s.seq, name: s.name, model: s.model || '',
        output_var: s.output_var || '', prompt_template: s.prompt_template,
      })))
    } catch { /* 统一提示 */ }
  }

  const refreshOptHistory = useCallback(async (wfId: number) => {
    if (!taskId) return
    try {
      const d = await wfApi.listOptimizations(taskId, wfId)
      setOptHistory(d.items || [])
    } catch { /* 统一提示 */ }
  }, [taskId])

  // 轮询优化报告直至终态；完成后刷新历史与步骤（回写结果）
  const pollOptReport = useCallback((wfId: number, optId: number) => {
    setOptPolling(true)
    const timer = setInterval(async () => {
      try {
        const d = await wfApi.getOptReport(taskId!, wfId, optId)
        setOptReport(d)
        if (d.opt.status === 'completed' || d.opt.status === 'failed') {
          clearInterval(timer)
          setOptPolling(false)
          refreshOptHistory(wfId)
          reloadStepsFromWf(wfId)
        }
      } catch { clearInterval(timer); setOptPolling(false) }
    }, 2000)
  }, [taskId, refreshOptHistory])

  const openOptSetup = (seq: number) => {
    setOptStepSeq(seq)
    setOptRounds(3)
    setOptSetupOpen(true)
  }

  // 启动优化：关闭参数弹窗 → 打开报告弹窗并轮询
  const handleStartOpt = async () => {
    if (!taskId || !activeWf || optStepSeq == null) return
    setOptStarting(true)
    try {
      const r = await wfApi.startStepOptimization(taskId, activeWf.id, optStepSeq, optRounds)
      setOptSetupOpen(false)
      setOptReport(null)
      setOptReportOpen(true)
      pollOptReport(activeWf.id, r.opt_id)
    } catch { /* 统一提示 */ } finally { setOptStarting(false) }
  }

  // 从历史列表查看某次优化报告
  const viewOptHistory = (optId: number) => {
    if (!taskId || !activeWf) return
    setOptReport(null)
    setOptReportOpen(true)
    pollOptReport(activeWf.id, optId)
  }

  return (
    <div>
      <PageHeader title="工作流" extra={
        <Tag style={{ fontSize: 13 }}>线性多步 · 上步输出即下步输入</Tag>
      } />

      <div className="pe-card" style={{ padding: '14px 16px', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <span className="ol-label">选择任务</span>
          <Select
            placeholder="选择要编排工作流的任务"
            style={{ width: 320 }} showSearch optionFilterProp="label"
            value={taskId}
            onChange={(v) => setTaskId(v)}
            options={tasks.map((t) => ({ label: `${t.name}`, value: t.id }))}
          />
          <Button type="primary" icon={<PlusOutlined />} disabled={!taskId}
                  onClick={() => setCreateOpen(true)}>新建工作流</Button>
        </div>
      </div>

      {!taskId ? (
        <Empty style={{ padding: 40 }} description="请先选择一个任务" />
      ) : (
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }} className="pe-rag-split">
          {/* 左：工作流列表 */}
          <Card size="small" title={<span className="ol-label">工作流</span>} style={{ width: 300 }}
                className="pe-card">
            <List
              size="small" dataSource={wfs} locale={{ emptyText: '暂无工作流' }}
              renderItem={(w) => (
                <List.Item
                  onClick={() => loadWf(w)}
                  style={{ cursor: 'pointer',
                           background: activeWf?.id === w.id ? '#eaf0fe' : undefined,
                           borderRadius: 6, padding: '6px 8px' }}
                  actions={[
                    <Popconfirm key="del" title="删除工作流？" okText="删除" cancelText="取消"
                                onConfirm={async () => {
                                  if (!taskId) return
                                  await wfApi.deleteWorkflow(taskId, w.id)
                                  if (activeWf?.id === w.id) { setActiveWf(undefined); setReport(null) }
                                  refreshWfs(taskId)
                                }}>
                      <DeleteOutlined style={{ color: '#c0392b' }} />
                    </Popconfirm>,
                  ]}
                >
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <ApartmentOutlined style={{ color: '#0E4AC3' }} />
                      <span style={{ fontWeight: 600 }}>{w.name}</span>
                    </div>
                    <div className="tnum" style={{ color: '#6b7280', fontSize: 12 }}>
                      {w.step_count} 步 · {formatTime(w.created_at)}
                    </div>
                  </div>
                </List.Item>
              )}
            />
          </Card>

          {/* 右：编辑器 + 报告 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {!activeWf ? (
              <Empty style={{ padding: 40 }} description="选择或以步骤编排一个工作流" />
            ) : (
              <>
                <Card size="small" className="pe-card"
                      title={<span className="ol-label">步骤编排</span>}
                      extra={<Space>
                        <Tooltip title={runBaseline ? '将同时以任务最优/初始 prompt 跑单次对照' : '仅评测工作流'}>
                          <span style={{ fontSize: 13, color: '#6b7280' }}>基线对照</span>
                        </Tooltip>
                        <Switch size="small" checked={runBaseline} onChange={setRunBaseline} />
                        <Button icon={<HistoryOutlined />} onClick={async () => {
                          if (!taskId || !activeWf) return
                          await refreshOptHistory(activeWf.id)
                          setOptReport(null)
                          setOptReportOpen(true)
                        }}>优化记录</Button>
                        <Button type="primary" icon={<RocketOutlined />} loading={running} onClick={handleRun}>
                          运行评测
                        </Button>
                      </Space>}>
                  <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                    <Input placeholder="工作流名称" value={wfName} onChange={(e) => setWfName(e.target.value)} style={{ width: 240 }} />
                    <Input placeholder="描述（可选）" value={wfDesc} onChange={(e) => setWfDesc(e.target.value)} style={{ flex: 1 }} />
                    <Button icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存</Button>
                  </div>

                  <div className="ol-label" style={{ color: '#6b7280', fontSize: 12, marginBottom: 8 }}>
                    占位符：<Tag>{'{{input}}'}</Tag> 用例输入 · <Tag>{'{{stepN.out}}'}</Tag> 第 N 步输出（N 为步骤序号）
                  </div>

                  {steps.map((s, idx) => (
                    <div key={idx} className="pe-card" style={{ padding: 10, marginBottom: 8, border: '1px solid #e5e7eb' }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                        <Tag color="geekblue">Step {idx + 1}</Tag>
                        <Input placeholder="步骤名（如：翻译→润色）" value={s.name}
                               onChange={(e) => setStep(idx, { name: e.target.value })} style={{ width: 180 }} />
                        <Select placeholder="模型(留空用默认)" allowClear value={s.model || undefined}
                                onChange={(v) => setStep(idx, { model: v || '' })} style={{ width: 220 }}
                                options={models.map((m) => ({ label: modelOptionLabel(m), value: m.id }))} />
                        <span style={{ flex: 1 }} />
                        <Tooltip title="自动迭代优化该步骤指令，整链评测择优回写">
                          <Button size="small" icon={<ThunderboltOutlined />}
                                  disabled={!s.prompt_template.trim()}
                                  onClick={() => openOptSetup(s.seq)}>优化</Button>
                        </Tooltip>
                        <Button size="small" icon={<UpOutlined />} disabled={idx === 0} onClick={() => moveStep(idx, -1)} />
                        <Button size="small" icon={<DownOutlined />} disabled={idx === steps.length - 1} onClick={() => moveStep(idx, 1)} />
                        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => setSteps((p) => p.filter((_, i) => i !== idx).map((x, i) => ({ ...x, seq: i + 1 })))} />
                      </div>
                      <TextArea rows={2} placeholder="指令模板，如：请把下面内容翻译成英文：{{input}}"
                                value={s.prompt_template}
                                onChange={(e) => setStep(idx, { prompt_template: e.target.value })} />
                    </div>
                  ))}
                  <Button block icon={<PlusOutlined />} type="dashed" onClick={() => setSteps((p) => [...p, {
                    seq: p.length + 1, name: `步骤${p.length + 1}`, model: '', output_var: '', prompt_template: '',
                  }])}>添加步骤</Button>
                </Card>

                {report && <ReportView report={report} loading={!!reportLoading} />}
                {recentRunId && !report && (
                  <Card size="small" className="pe-card"><Spin tip="评测运行中，正在生成报告…">
                    <div style={{ height: 60 }} />
                  </Spin></Card>
                )}
              </>
            )}
          </div>
        </div>
      )}

      <Modal title="新建工作流" open={createOpen} onOk={handleCreate} confirmLoading={creating}
             onCancel={() => setCreateOpen(false)} okText="创建" cancelText="取消">
        <div style={{ marginTop: 8 }}>
          <div className="ol-label">名称</div>
          <Input placeholder="输入工作流名称" value={newName} onChange={(e) => setNewName(e.target.value)} />
        </div>
      </Modal>

      {/* 步骤优化参数弹窗 */}
      <Modal title={`优化 Step ${optStepSeq ?? ''}`} open={optSetupOpen}
             onOk={handleStartOpt} confirmLoading={optStarting} okText="开始优化" cancelText="取消">
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="ol-label" style={{ color: '#6b7280', fontSize: 13 }}>
            将以该步骤当前指令为基准，多轮生成变体并重跑整条工作流评测，
            择优回写该步骤指令模板。终止条件：达到最大轮数或连续两轮无提升。
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="ol-label">迭代轮数</span>
            <Select style={{ width: 120 }} value={optRounds} onChange={setOptRounds}
                    options={[1, 2, 3, 5].map((n) => ({ label: `${n} 轮`, value: n }))} />
          </div>
        </div>
      </Modal>

      {/* 步骤优化报告弹窗（含历史） */}
      <Modal title={<span>步骤优化报告
        {optReport && (
          <Tag color={OPT_STATUS[optReport.opt.status]?.color} style={{ marginLeft: 8 }}>
            {OPT_STATUS[optReport.opt.status]?.text}
          </Tag>
        )}
        {optReport && optReport.opt.status === 'completed' && (
          <Button size="small" icon={<ShareAltOutlined />} style={{ marginLeft: 12 }}
                  onClick={() => setShareOpen(true)}>分享报告</Button>
        )}
      </span>} open={optReportOpen} footer={null} width={760}
             onCancel={() => setOptReportOpen(false)}>
        <Spin spinning={optPolling} tip="优化运行中，正在生成报告…">
          {optReport && <OptReportView report={optReport} />}
          {!optReport && !optPolling && <Empty style={{ padding: 24 }} description="暂无优化记录" />}
          {optHistory.length > 0 && (
            <div style={{ marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
              <div className="ol-label" style={{ marginBottom: 8 }}>历史优化记录</div>
              <List
                size="small" dataSource={optHistory}
                locale={{ emptyText: '暂无历史' }}
                renderItem={(o) => (
                  <List.Item
                    style={{ cursor: 'pointer' }}
                    onClick={() => viewOptHistory(o.id)}
                    actions={[
                      <Button key="view" size="small" onClick={() => viewOptHistory(o.id)}>查看</Button>,
                    ]}
                  >
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                      <Tag color="geekblue">Step {o.step_seq}</Tag>
                      <Tag color={OPT_STATUS[o.status]?.color}>{OPT_STATUS[o.status]?.text}</Tag>
                      <span className="tnum" style={{ fontSize: 12, color: '#6b7280' }}>
                        基准 {o.base_score?.toFixed(1) ?? '—'} → 最优 {o.best_score?.toFixed(1) ?? '—'}
                      </span>
                      {o.improved === 1 && <Tag color="green">已提升</Tag>}
                      <span className="tnum" style={{ fontSize: 12, color: '#9ca3af' }}>
                        {formatTime(o.created_at)}
                      </span>
                    </div>
                  </List.Item>
                )}
              />
            </div>
          )}
        </Spin>
      </Modal>
      <ShareModal
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        reportType="optimization"
        targetId={optReport?.opt.id ?? 0}
        title="分享步骤优化报告"
      />
    </div>
  )
}

// 步骤优化报告内容：基准/最优分对比 + 变体明细
function OptReportView({ report }: { report: WorkflowOptReport }) {
  const o = report.opt
  const base = o.base_score ?? 0
  const best = o.best_score ?? 0
  const improved = o.improved === 1 && best > base
  return (
    <div>
      {/* 分数对比 */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        <div className="ol-label">基准整链分</div>
        <span className="tnum" style={{ fontSize: 22, fontWeight: 800, color: scoreColor(base) }}>{base.toFixed(1)}</span>
        <div className="ol-label" style={{ marginLeft: 16 }}>最优整链分</div>
        <span className="tnum" style={{ fontSize: 22, fontWeight: 800, color: scoreColor(best) }}>{best.toFixed(1)}</span>
        <Tag color={improved ? 'green' : 'orange'}>
          {improved ? `提升 ${(best - base).toFixed(1)} 分` : '无提升'}
        </Tag>
        <span className="tnum" style={{ fontSize: 12, color: '#9ca3af' }}>
          {o.current_round}/{o.max_rounds} 轮 · {report.workflow?.name ?? ''}
        </span>
      </div>

      {/* prompt 对比 */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <div className="ol-label" style={{ marginBottom: 4 }}>优化前指令</div>
          <pre className="ol-out" style={{ whiteSpace: 'pre-wrap', background: '#f6f7fb', padding: 8, borderRadius: 6, fontSize: 12, margin: 0 }}>{o.base_prompt}</pre>
        </div>
        <div style={{ flex: 1 }}>
          <div className="ol-label" style={{ marginBottom: 4 }}>优化后指令（已回写）</div>
          <pre className="ol-out" style={{ whiteSpace: 'pre-wrap', background: '#ecfdf5', border: '1px solid #a7f3d0', padding: 8, borderRadius: 6, fontSize: 12, margin: 0 }}>
            {o.best_prompt || '—'}
          </pre>
        </div>
      </div>

      {/* 变体明细 */}
      <div className="ol-label" style={{ marginBottom: 6 }}>变体评测明细</div>
      {report.variants.length === 0 && <Empty description="本轮无有效变体" />}
      {[...report.variants].reverse().map((v) => (
        <div key={v.id} className="pe-card" style={{ padding: 8, marginBottom: 6, border: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 4 }}>
            <Tag color="blue">R{v.round_no}-V{v.variant_no}</Tag>
            <Tag>{v.strategy_tag}</Tag>
            {v.is_best === 1 && <Tag color="green">本轮最优</Tag>}
            <span style={{ flex: 1 }} />
            <span className="tnum" style={{ fontWeight: 700, color: scoreColor(v.avg_score) }}>
              {v.avg_score?.toFixed(1) ?? '—'}
            </span>
            {v.status === 'failed' && <Tag color="red" style={{ marginLeft: 4 }}>失败</Tag>}
          </div>
          <div style={{ fontSize: 12, whiteSpace: 'pre-wrap', color: '#374151' }}>{v.prompt_text}</div>
          {v.error_reason && <div style={{ fontSize: 12, color: '#c0392b', marginTop: 4 }}>{v.error_reason}</div>}
        </div>
      ))}
    </div>
  )
}

// 报告看板
function ReportView({ report, loading }: { report: WorkflowReport; loading: boolean }) {
  const r = report.run
  const wfBest = r.avg_score ?? 0
  const baseBest = r.baseline_avg_score ?? 0
  const hasBase = r.baseline_avg_score != null
  const cmp = hasBase ? (wfBest - baseBest) : null

  return (
    <Card size="small" className="pe-card"
          title={<span className="ol-label">评测报告
            <Tag color={RUN_STATUS[r.status]?.color} style={{ marginLeft: 8 }}>{RUN_STATUS[r.status]?.text}</Tag>
          </span>}>
      <Spin spinning={loading}>
        {/* 平均分对比 */}
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
          <div className="ol-label">端到端平均分</div>
          <span className="tnum" style={{ fontSize: 22, fontWeight: 800, color: scoreColor(wfBest) }}>{wfBest.toFixed(1)}</span>
          {hasBase && (
            <>
              <div className="ol-label" style={{ marginLeft: 16 }}>单 prompt 基线</div>
              <span className="tnum" style={{ fontSize: 22, fontWeight: 800, color: scoreColor(baseBest) }}>{baseBest.toFixed(1)}</span>
              <Tag color={cmp != null && cmp >= 0 ? 'green' : 'orange'}>
                工作流 {cmp != null && cmp >= 0 ? '优于' : '逊于'}基线
                {cmp != null ? ` ${Math.abs(cmp).toFixed(1)}分` : ''}
              </Tag>
            </>
          )}
        </div>

        <Collapse
          items={report.cases.map((c, i) => ({
            key: i,
            label: (
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', width: '100%' }}>
                <span className="tnum" style={{ color: '#6b7280' }}>#{c.case_id}</span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.input_text}
                </span>
                {c.error_reason ? (
                  <Tag color="red">失败</Tag>
                ) : (
                  <>
                    <span className="tnum" style={{ fontWeight: 700, color: scoreColor(c.total_score) }}>
                      {c.total_score?.toFixed(1) ?? '—'}
                    </span>
                    {c.baseline_score != null && (
                      <span className="tnum" style={{ color: '#9ca3af', fontSize: 12 }}>
                        基线 {c.baseline_score.toFixed(1)}
                      </span>
                    )}
                  </>
                )}
              </div>
            ),
            children: <CaseDetail c={c} />,
          }))}
        />

        {report.cases.length === 0 && <Empty description="本任务没有用例，无法评测" />}
      </Spin>
    </Card>
  )
}

function CaseDetail({ c }: { c: WorkflowReport['cases'][number] }) {
  return (
    <div>
      {c.error_reason ? (
        <div style={{ color: '#c0392b' }}>执行失败：{c.error_reason}</div>
      ) : (
        <>
          <div className="ol-label">最终输出</div>
          <pre className="ol-out" style={{ whiteSpace: 'pre-wrap', background: '#f6f7fb', padding: 10, borderRadius: 6, fontSize: 13 }}>{c.final_output}</pre>
          {c.judge_reason && (
            <div className="ol-label" style={{ color: '#6b7280', marginTop: 6 }}>评审：{c.judge_reason}</div>
          )}

          <div className="ol-label" style={{ marginTop: 12 }}>步骤追踪</div>
          {c.step_trace.map((t) => (
            <div key={t.seq} className="pe-card" style={{ padding: 8, marginBottom: 6, border: '1px solid #e5e7eb' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                <Tag color="blue">Step {t.seq}</Tag>
                <b>{t.name || `步骤${t.seq}`}</b>
                <span className="tnum" style={{ color: '#9ca3af', fontSize: 12 }}>{t.output_var}</span>
              </div>
              <div style={{ fontSize: 12, whiteSpace: 'pre-wrap', color: '#374151' }}>{t.output}</div>
            </div>
          ))}
        </>
      )}

      {c.baseline_output != null && (
        <>
          <div className="ol-label" style={{ marginTop: 12 }}>基线（单 prompt）输出</div>
          <pre className="ol-out" style={{ whiteSpace: 'pre-wrap', background: '#f3f4f6', padding: 10, borderRadius: 6, fontSize: 13 }}>
            {c.baseline_output}
          </pre>
        </>
      )}
    </div>
  )
}