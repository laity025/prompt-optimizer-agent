// ==========================================================
// 资产管理门户 / 汇总仪表盘
// 总览卡片 + 任务类型分布 + 近N天活动趋势 + 任务资产表 + 模型统计 + 版本库检索
// ==========================================================
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Card, Col, Input, Row, Select, Space, Statistic, Table, Tag,
} from 'antd'
import {
  ApiOutlined, BarChartOutlined, BookOutlined, DatabaseOutlined,
  ExperimentOutlined, FileTextOutlined, RocketOutlined, UnorderedListOutlined,
} from '@ant-design/icons'
import type { TableColumnsType } from 'antd'
import * as echarts from 'echarts'
import PageHeader from '@/components/PageHeader'
import * as dashApi from '@/api/dashboard'
import { listTasks } from '@/api/task'
import type {
  DashboardModelStat, DashboardOverview, DashboardTaskAsset,
  DashboardVersionItem, TaskListItem,
} from '@/types'
import { formatTime } from '@/utils'

// 任务类型中文标签（与类型定义保持一致）
const TYPE_LABEL: Record<string, string> = {
  text_gen: '文本生成', summary: '摘要', extraction: '信息抽取', code: '代码生成', custom: '自定义',
}

const CARD_COLORS = ['#0E4AC3', '#7C3AED', '#0EA5E9', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6', '#06B6D4']

function renderScore(v: number | null | undefined): React.ReactNode {
  return v == null ? '—' : v.toFixed(1)
}

// 迷你 ECharts 包装：处理初始化/销毁/尺寸自适应
function useEChart() {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  useEffect(() => {
    if (!ref.current) return
    chartRef.current = echarts.init(ref.current)
    const ro = new ResizeObserver(() => chartRef.current?.resize())
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])
  const setOption = useCallback((opt: echarts.EChartsOption) => {
    chartRef.current?.setOption(opt, true)
  }, [])
  return { ref, setOption }
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [tasks, setTasks] = useState<DashboardTaskAsset[]>([])
  const [taskTotal, setTaskTotal] = useState(0)
  const [keyword, setKeyword] = useState('')
  const [versions, setVersions] = useState<DashboardVersionItem[]>([])
  const [vKeyword, setVKeyword] = useState('')
  const [vTaskId, setVTaskId] = useState<number>()
  const [allTasks, setAllTasks] = useState<TaskListItem[]>([])
  const [modelStats, setModelStats] = useState<DashboardModelStat[]>([])
  const [bestDist, setBestDist] = useState<{ model: string; count: number }[]>([])
  const [trendDays, setTrendDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [vLoading, setVLoading] = useState(false)

  // 图表
  const typeChart = useEChart()
  const trendChart = useEChart()

  // 初次加载：总览 + 任务资产 + 模型统计
  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, ta, ms] = await Promise.all([
        dashApi.getOverview(),
        dashApi.getTaskAssets(''),
        dashApi.getModelStats(),
      ])
      setOverview(ov)
      setTasks(ta.items || [])
      setTaskTotal(ta.total || 0)
      setModelStats(ms.calls || [])
      setBestDist(ms.best_dist || [])
    } catch {
      /* 错误已统一提示 */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
    listTasks({ page: 1, page_size: 100 }).then((d) => setAllTasks(d.items || [])).catch(() => {})
  }, [loadAll])

  // 趋势图数据：按天渲染（series 由后端按实体类型分组）
  useEffect(() => {
    let cancelled = false
    dashApi.getTrend(trendDays).then((d) => {
      if (!cancelled) renderTrend(trendChart.setOption, d.series)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [trendDays, trendChart.setOption])

  // 任务类型分布图
  useEffect(() => {
    renderTypeDist(typeChart.setOption, tasks)
  }, [tasks, typeChart.setOption])

  // 任务资产表搜索
  const searchTasks = useCallback(async (kw: string) => {
    try {
      const d = await dashApi.getTaskAssets(kw)
      setTasks(d.items || [])
      setTaskTotal(d.total || 0)
    } catch {
      /* 统一提示 */
    }
  }, [])

  // 版本库检索
  const searchVersions = useCallback(async (kw: string, tid?: number) => {
    setVLoading(true)
    try {
      const d = await dashApi.searchVersions(kw, tid)
      setVersions(d.items || [])
    } catch {
      /* 统一提示 */
    } finally {
      setVLoading(false)
    }
  }, [])

  useEffect(() => {
    searchVersions('')
  }, [searchVersions])

  const taskColumns: TableColumnsType<DashboardTaskAsset> = [
    { title: '任务', dataIndex: 'name', ellipsis: true, render: (v, r) => <a onClick={() => navigate(`/tasks/${r.id}`)}>{v}</a> },
    { title: '类型', dataIndex: 'task_type', width: 90, render: (v) => <Tag>{TYPE_LABEL[v] || v}</Tag> },
    { title: '状态', dataIndex: 'status', width: 80, render: (v) => (
      <Tag color={v === 'completed' ? 'green' : v === 'running' ? 'blue' : v === 'failed' ? 'red' : 'default'}>
        {v === 'completed' ? '已完成' : v === 'running' ? '运行中' : v === 'failed' ? '失败' : '待运行'}
      </Tag>
    ) },
    { title: '用例', dataIndex: 'case_count', width: 60, align: 'right' },
    { title: '版本', dataIndex: 'version_count', width: 60, align: 'right' },
    { title: '评测', dataIndex: 'benchmark_count', width: 60, align: 'right' },
    { title: '工作流', dataIndex: 'workflow_count', width: 70, align: 'right' },
    { title: '最优分', dataIndex: 'best_score', width: 80, align: 'right', render: renderScore },
    { title: '迭代进度', width: 90, align: 'right', render: (_, r) => (
      <span className="tnum" style={{ fontSize: 12, color: '#6b7280' }}>{r.current_round}/{r.max_rounds}</span>
    ) },
    { title: '更新时间', dataIndex: 'updated_at', width: 120, render: (v) => formatTime(v) },
  ]

  const modelColumns: TableColumnsType<DashboardModelStat> = [
    { title: '模型', dataIndex: 'model', ellipsis: true },
    { title: '调用次数', dataIndex: 'calls', align: 'right', render: (v) => <span className="tnum">{v}</span> },
    { title: '成功率', dataIndex: 'success_rate', align: 'right', render: (v) => <span className="tnum">{v}%</span> },
    { title: '平均耗时', dataIndex: 'avg_latency_ms', align: 'right', render: (v) => <span className="tnum">{v} ms</span> },
  ]

  const statCards = useMemo(() => {
    const o = overview
    const cards = [
      { key: 'tasks', label: '任务', value: o?.tasks ?? 0, icon: <UnorderedListOutlined />, color: CARD_COLORS[0] },
      { key: 'cases', label: '用例', value: o?.cases ?? 0, icon: <FileTextOutlined />, color: CARD_COLORS[1] },
      { key: 'versions', label: 'Prompt 版本', value: o?.versions ?? 0, icon: <BookOutlined />, color: CARD_COLORS[2] },
      { key: 'benchmarks', label: '模型评测', value: o?.benchmarks ?? 0, icon: <ExperimentOutlined />, color: CARD_COLORS[3] },
      { key: 'workflows', label: '工作流', value: o?.workflows ?? 0, icon: <BarChartOutlined />, color: CARD_COLORS[4] },
      { key: 'kb', label: '知识库', value: o?.knowledge_bases ?? 0, icon: <DatabaseOutlined />, color: CARD_COLORS[5] },
      { key: 'endpoints', label: '在线端点', value: o?.endpoints ?? 0, icon: <ApiOutlined />, color: CARD_COLORS[6] },
      { key: 'calls', label: '累计调用', value: o?.calls ?? 0, icon: <RocketOutlined />, color: CARD_COLORS[7] },
    ]
    return cards
  }, [overview])

  return (
    <div>
      <PageHeader
        title="资产门户"
        extra={
          <Space>
            <span style={{ color: '#6b7280', fontSize: 13 }}>平均最优分</span>
            <span className="tnum" style={{ fontSize: 20, fontWeight: 800, color: '#0E4AC3' }}>
              {renderScore(overview?.best_score_avg ?? null)}
            </span>
            <Button size="small" onClick={loadAll}>刷新</Button>
          </Space>
        }
      />

      {/* 总览卡片 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {statCards.map((c) => (
          <Col key={c.key} xs={12} sm={8} md={6} lg={6} xl={3}>
            <Card size="small" styles={{ body: { padding: '14px 16px' } }}>
              <Statistic
                title={<span style={{ fontSize: 13, color: '#6b7280' }}>{c.label}</span>}
                value={c.value}
                valueStyle={{ fontSize: 24, fontWeight: 800, color: c.color }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 分布与趋势 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={9}>
          <Card size="small" title="任务类型分布" styles={{ body: { padding: 8 } }}>
            <div ref={typeChart.ref} style={{ width: '100%', height: 260 }} />
          </Card>
        </Col>
        <Col xs={24} lg={15}>
          <Card
            size="small"
            title={`近 ${trendDays} 天活动趋势`}
            extra={
              <Select size="small" value={trendDays} onChange={setTrendDays}
                      options={[{ label: '30 天', value: 30 }, { label: '60 天', value: 60 }, { label: '90 天', value: 90 }]} />
            }
            styles={{ body: { padding: 8 } }}
          >
            <div ref={trendChart.ref} style={{ width: '100%', height: 260 }} />
          </Card>
        </Col>
      </Row>

      {/* 任务资产表 */}
      <Card
        size="small"
        title={`任务资产（${taskTotal}）`}
        extra={
          <Input.Search allowClear placeholder="按任务名称搜索" style={{ width: 240 }}
                        value={keyword}
                        onChange={(e) => setKeyword(e.target.value)}
                        onSearch={(v) => searchTasks(v)} />
        }
        style={{ marginBottom: 16 }}
      >
        <Table size="small" rowKey="id" loading={loading} columns={taskColumns}
               dataSource={tasks} pagination={{ pageSize: 8, showSizeChanger: false }} />
      </Card>

      <Row gutter={[12, 12]}>
        {/* 模型统计 */}
        <Col xs={24} lg={10}>
          <Card size="small" title="模型调用统计" styles={{ body: { padding: 8 } }}>
            <Table size="small" rowKey="model" columns={modelColumns} dataSource={modelStats}
                   pagination={false} locale={{ emptyText: '暂无端点调用' }} />
            {bestDist.length > 0 && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #f0f0f0' }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>评测最优模型分布</div>
                <Space wrap>
                  {bestDist.map((b) => (
                    <Tag key={b.model} color="geekblue">{b.model} × {b.count}</Tag>
                  ))}
                </Space>
              </div>
            )}
          </Card>
        </Col>

        {/* 版本库检索 */}
        <Col xs={24} lg={14}>
          <Card
            size="small"
            title="Prompt 版本库"
            extra={
              <Space>
                <Select allowClear placeholder="按任务筛选" style={{ width: 160 }} size="small"
                        value={vTaskId} onChange={(v) => { setVTaskId(v); searchVersions(vKeyword, v) }}
                        options={allTasks.map((t) => ({ label: t.name, value: t.id }))} />
                <Input.Search allowClear placeholder="搜索 prompt 内容/任务名" style={{ width: 240 }} size="small"
                              onSearch={(v) => { setVKeyword(v); searchVersions(v, vTaskId) }} />
              </Space>
            }
            styles={{ body: { padding: 8 } }}
          >
            <div style={{ maxHeight: 360, overflow: 'auto' }}>
              {vLoading && <div style={{ textAlign: 'center', padding: 24, color: '#9ca3af' }}>检索中…</div>}
              {!vLoading && versions.length === 0 && (
                <div style={{ textAlign: 'center', padding: 24, color: '#9ca3af' }}>暂无版本</div>
              )}
              {!vLoading && versions.map((v) => (
                <div key={v.id} style={{ padding: '8px 10px', borderBottom: '1px solid #f3f4f6' }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4, flexWrap: 'wrap' }}>
                    <Tag color="geekblue">{v.task_name} · V{v.version_no}</Tag>
                    {v.frozen === 1 && <Tag color="gold">已冻结</Tag>}
                    {v.is_best === 1 && <Tag color="green">最优</Tag>}
                    {v.score != null && (
                      <span className="tnum" style={{ fontSize: 12, color: '#0E4AC3', fontWeight: 700 }}>{v.score.toFixed(1)} 分</span>
                    )}
                    <span style={{ flex: 1 }} />
                    <span className="tnum" style={{ fontSize: 12, color: '#9ca3af' }}>{formatTime(v.created_at)}</span>
                  </div>
                  <div style={{ fontSize: 12.5, color: '#374151', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {v.prompt_text.length > 160 ? `${v.prompt_text.slice(0, 160)}…` : v.prompt_text}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

// 任务类型分布（环形图）
function renderTypeDist(setOption: (o: echarts.EChartsOption) => void, tasks: DashboardTaskAsset[]) {
  const counts = new Map<string, number>()
  tasks.forEach((t) => counts.set(t.task_type, (counts.get(t.task_type) || 0) + 1))
  const data = [...counts.entries()].map(([k, v], i) => ({
    name: TYPE_LABEL[k] || k, value: v, itemStyle: { color: CARD_COLORS[i % CARD_COLORS.length] },
  }))
  setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 个 ({d}%)' },
    legend: { bottom: 0, icon: 'circle', textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
      label: { show: false }, itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      data: data.length ? data : [{ name: '暂无任务', value: 1, itemStyle: { color: '#E5E7EB' } }],
    }],
    graphic: data.length ? [] : [{
      type: 'text', left: 'center', top: '42%', style: { text: '暂无任务', fill: '#9CA3AF', fontSize: 13 },
    }],
  })
}

// 近 N 天活动趋势（多系列柱状图：任务/评测/调用/工作流）
function renderTrend(setOption: (o: echarts.EChartsOption) => void, series: Record<string, Record<string, number>>) {
  const keys = new Set<string>()
  Object.values(series).forEach((m) => Object.keys(m).forEach((d) => keys.add(d)))
  const dates = [...keys].sort()
  const seriesDefs: { key: string; name: string; color: string }[] = [
    { key: 'task', name: '新建任务', color: '#0E4AC3' },
    { key: 'benchmark', name: '模型评测', color: '#7C3AED' },
    { key: 'call', name: '端点调用', color: '#0EA5E9' },
    { key: 'workflow_run', name: '工作流运行', color: '#F59E0B' },
    { key: 'optimization', name: '步骤优化', color: '#10B981' },
  ]
  setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, icon: 'circle', textStyle: { fontSize: 12 } },
    grid: { left: 40, right: 16, top: 24, bottom: 44 },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { fontSize: 11, formatter: (v: string) => v.slice(5) },
    },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#F3F4F6' } } },
    series: seriesDefs.map((s) => ({
      name: s.name, type: 'bar', stack: 'total', barMaxWidth: 22,
      itemStyle: { color: s.color }, data: dates.map((d) => series[s.key]?.[d] || 0),
    })),
    graphic: dates.length ? [] : [{
      type: 'text', left: 'center', top: 'middle', style: { text: '暂无活动', fill: '#9CA3AF', fontSize: 13 },
    }],
  })
}
