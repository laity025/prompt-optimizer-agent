// ==========================================================
// 迭代过程子页：得分曲线 + 每轮变体展开 + 人工抽检 + 版本记录
// ==========================================================
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Collapse, Button, Table, Modal, Tag, InputNumber, Input, Space, App } from 'antd'
import { CheckSquareOutlined, CaretRightOutlined } from '@ant-design/icons'
import ScoreChart from '@/components/ScoreChart'
import { getScoreCurve, getRoundVariants, getEvalResults, reviewEval, listCases, listVersions, setVersionAction } from '@/api/task'
import { Panel, SectionTitle, EmptyArt } from '@/components/ui'
import type { ScorePoint, Task, IterationStatus, Variant, EvalResult, Version, TestCase } from '@/types'

interface Props {
  taskId: number
  task: Task
  progress: IterationStatus | null
  onRefresh: () => void
  onStart: () => void
}

export default function TaskIteration({ taskId, task, progress, onRefresh, onStart }: Props) {
  const app = App.useApp()
  const running = task.status === 'running'
  // 当前推进到的轮次（运行中取实时进度，否则取任务记录）
  const currentRound = running ? progress?.current_round ?? task.current_round : task.current_round

  const [curve, setCurve] = useState<ScorePoint[]>([])
  // 各轮变体缓存：round -> Variant[]
  const [variantsMap, setVariantsMap] = useState<Record<number, Variant[]>>({})
  const [versions, setVersions] = useState<Version[]>([])
  // 抽检弹窗状态
  const [modal, setModal] = useState<{ open: boolean; round: number; evals: EvalResult[]; caseMap: Record<number, TestCase> }>({
    open: false,
    round: 0,
    evals: [],
    caseMap: {},
  })
  const [manualScores, setManualScores] = useState<Record<number, number | null>>({})
  const [manualNotes, setManualNotes] = useState<Record<number, string>>({})

  // 加载得分曲线
  const loadCurve = useCallback(async () => {
    try {
      const data = await getScoreCurve(taskId, Math.max(currentRound, 1))
      setCurve(data.rounds)
    } catch {
      /* 未运行时可能无曲线 */
    }
  }, [taskId, currentRound])

  useEffect(() => {
    loadCurve()
    // 非运行中加载版本记录（用于冻结）
    if (!running) {
      listVersions(taskId).then(setVersions).catch(() => {})
    }
  }, [loadCurve, running, taskId])

  // 展开某轮时加载其变体
  const loadRoundVariants = async (round: number) => {
    if (variantsMap[round]) return
    try {
      const data = await getRoundVariants(taskId, round)
      setVariantsMap((m) => ({ ...m, [round]: data }))
    } catch {
      /* 错误统一提示 */
    }
  }

  // 刷新版本记录（冻结/回退后调用）
  const refreshVersions = async () => {
    try {
      setVersions(await listVersions(taskId))
    } catch {
      /* 错误统一提示 */
    }
  }

  // 版本操作：冻结为稳定版 / 回退到该版本（回退需确认，前置任务非运行）
  const handleVersionAction = async (v: Version, action: 'freeze' | 'revert') => {
    if (action === 'revert') {
      app.modal.confirm({
        title: '回退版本',
        content: `确定将该版本（第 ${v.version_no} 版${v.score != null ? `，${v.score.toFixed(1)} 分` : ''}）设为当前最优并回退吗？任务将重置为「待运行」。`,
        okText: '回退',
        cancelText: '取消',
        onOk: async () => {
          await setVersionAction(taskId, v.id, 'revert')
          app.message.success('已回退')
          await refreshVersions()
          onRefresh()
        },
      })
      return
    }
    await setVersionAction(taskId, v.id, 'freeze')
    app.message.success('已冻结该版本')
    await refreshVersions()
  }

  // 打开人工抽检弹窗
  const openReview = async (round: number) => {
    setModal({ open: true, round, evals: [], caseMap: {} })
    try {
      const [evalsData, casesData] = await Promise.all([
        getEvalResults(taskId, round),
        listCases(taskId, { page_size: 100 }),
      ])
      const caseMap: Record<number, TestCase> = {}
      casesData.items.forEach((c) => {
        caseMap[c.id] = c
      })
      setModal((m) => ({ ...m, evals: evalsData.items, caseMap }))
    } catch {
      /* 错误统一提示 */
    }
  }

  // 提交人工评分
  const submitReview = async (evalId: number) => {
    const score = manualScores[evalId]
    if (score == null) {
      app.message.warning('请先输入人工评分（1-10）')
      return
    }
    try {
      await reviewEval(taskId, evalId, { manual_score: score, manual_note: manualNotes[evalId] || undefined })
      app.message.success('已提交人工评分')
      openReview(modal.round)
    } catch {
      /* 错误统一提示 */
    }
  }

  // 各轮折叠面板（变体表 + 人工抽检入口）
  const panels = useMemo(() => {
    const list: { key: string; label: ReactNode; children: ReactNode }[] = []
    for (let r = 1; r <= Math.max(currentRound, 0); r++) {
      list.push({
        key: String(r),
        label: (
          <span>
            第 {String(r).padStart(2, '0')} 轮
            {r === currentRound && running && (
              <Tag color="processing" style={{ marginLeft: 10 }}>
                进行中
              </Tag>
            )}
          </span>
        ),
        children: (
          <div>
            <Table<Variant>
              size="small"
              rowKey="id"
              dataSource={variantsMap[r] || []}
              pagination={false}
              loading={!variantsMap[r]}
              columns={[
                { title: '变体号', dataIndex: 'variant_no', width: 80, render: (n: number) => <span className="seq-no">#{n}</span> },
                {
                  title: '策略',
                  dataIndex: 'strategy_tag',
                  width: 120,
                  render: (t: string | null) => (t ? <Tag>{t}</Tag> : '—'),
                },
                {
                  title: '得分',
                  dataIndex: 'score',
                  width: 100,
                  render: (s: number | null) => (s == null ? '—' : <b className="score-num">{s.toFixed(1)}</b>),
                },
                {
                  title: '状态',
                  dataIndex: 'status',
                  width: 100,
                  render: (s: string) => {
                    const color = s === 'completed' ? 'success' : s === 'failed' ? 'error' : 'processing'
                    return <Tag color={color}>{s}</Tag>
                  },
                },
                {
                  title: '提示词',
                  dataIndex: 'prompt_text',
                  ellipsis: true,
                  render: (t: string) => <span className="prompt-box" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{t}</span>,
                },
              ]}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
              <Button icon={<CheckSquareOutlined />} onClick={() => openReview(r)} disabled={variantsMap[r]?.length === 0}>
                人工抽检该轮
              </Button>
            </div>
          </div>
        ),
      })
    }
    return list
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentRound, variantsMap, running])

  // 抽检弹窗评估明细列
  const evalColumns = [
    { title: '变体', dataIndex: 'variant_no', width: 70, render: (n: number) => <span className="seq-no">#{n}</span> },
    {
      title: '用例输入',
      key: 'case',
      render: (_: unknown, r: EvalResult) => modal.caseMap[r.test_case_id]?.input_text?.slice(0, 60) ?? `#${r.test_case_id}`,
    },
    { title: '自动得分', dataIndex: 'total_score', width: 90, render: (v: number | null) => (v == null ? '—' : v.toFixed(1)) },
    { title: '评审分', dataIndex: 'judge_score', width: 80, render: (v: number | null) => v ?? '—' },
    { title: '评审理由', dataIndex: 'judge_reason', ellipsis: true, render: (v: string | null) => v || '—' },
    {
      title: '人工评分',
      width: 240,
      render: (_: unknown, r: EvalResult) =>
        r.manual_checked ? (
          <b style={{ color: 'var(--state-success)' }}>
            {r.manual_score}
            {r.manual_note ? `（${r.manual_note}）` : ''}
          </b>
        ) : (
          <Space>
            <InputNumber
              min={1}
              max={10}
              placeholder="1-10"
              style={{ width: 78 }}
              value={manualScores[r.id] ?? null}
              onChange={(v) => setManualScores((m) => ({ ...m, [r.id]: v }))}
            />
            <Input
              placeholder="备注"
              style={{ width: 130 }}
              value={manualNotes[r.id] ?? ''}
              onChange={(e) => setManualNotes((m) => ({ ...m, [r.id]: e.target.value }))}
            />
            <Button type="primary" size="small" onClick={() => submitReview(r.id)}>
              提交
            </Button>
          </Space>
        ),
    },
  ]

  return (
    <div>
      {/* 得分曲线 */}
      <Panel style={{ marginBottom: 20 }}>
        <SectionTitle title="得分曲线" en="score curve" extra={running ? <Tag color="processing">运行中</Tag> : undefined} />
        {curve.length > 0 ? (
          <ScoreChart rounds={curve} targetScore={task.target_score} />
        ) : (
          <div>
            <EmptyArt text="暂无迭代数据" />
            {task.status === 'pending' && (
              <div style={{ textAlign: 'center', paddingBottom: 20 }}>
                <button className="pe-btn pe-btn-blue pe-btn-sm" onClick={onStart}>
                  <CaretRightOutlined />
                  开始首次迭代
                </button>
              </div>
            )}
          </div>
        )}
      </Panel>

      {/* 迭代记录 */}
      <Panel style={{ marginBottom: 20 }}>
        <SectionTitle title="迭代记录" en="rounds" />
        {currentRound === 0 ? (
          <EmptyArt text="尚未开始迭代" />
        ) : (
          <Collapse
            items={panels}
            onChange={(keys) => {
              keys.forEach((k) => loadRoundVariants(Number(k)))
            }}
          />
        )}
      </Panel>

      {/* 版本记录 */}
      {versions.length > 0 && (
        <Panel tight>
          <div style={{ padding: '20px 22px 0' }}>
            <SectionTitle title="版本记录" en="versions" />
          </div>
          <Table<Version>
            size="small"
            rowKey="id"
            dataSource={versions}
            pagination={false}
            columns={[
              { title: '版本号', dataIndex: 'version_no', width: 90, render: (n: number) => <span className="seq-no">V{n}</span> },
              { title: '得分', dataIndex: 'score', width: 90, render: (s: number | null) => (s == null ? '—' : s.toFixed(1)) },
              { title: '最优', dataIndex: 'is_best', width: 80, render: (v: number) => (v ? <Tag color="gold">最优</Tag> : '—') },
              { title: '冻结', dataIndex: 'frozen', width: 80, render: (v: number) => (v ? <Tag color="blue">已冻结</Tag> : '—') },
              { title: '提示词', dataIndex: 'prompt_text', ellipsis: true },
              {
                title: '操作',
                key: 'op',
                width: 150,
                render: (_: unknown, v: Version) => (
                  <Space>
                    {v.frozen === 0 && (
                      <Button size="small" disabled={running} onClick={() => handleVersionAction(v, 'freeze')}>
                        冻结
                      </Button>
                    )}
                    <Button size="small" type="primary" ghost disabled={running} onClick={() => handleVersionAction(v, 'revert')}>
                      回退
                    </Button>
                  </Space>
                ),
              },
            ]}
          />
        </Panel>
      )}

      {/* 人工抽检弹窗 */}
      <Modal
        title={`第 ${modal.round} 轮 · 人工抽检`}
        open={modal.open}
        width={1000}
        onCancel={() => setModal((m) => ({ ...m, open: false }))}
        footer={null}
      >
        <Table<EvalResult>
          rowKey="id"
          dataSource={modal.evals}
          loading={modal.evals.length === 0}
          size="small"
          columns={evalColumns as never}
          pagination={{ pageSize: 8 }}
        />
      </Modal>
    </div>
  )
}
