// ==========================================================
// 在线服务页：把任务的最优/冻结提示词一键上线为可调用的 API
//   服务卡片（折叠）内含：密钥/调用地址/示例代码/页内试调用/日志/统计
// ==========================================================
import { useCallback, useEffect, useState } from 'react'
import {
  App, Button, Collapse, Input, Modal, Popconfirm, Select, Space, Switch,
  Table, Tag, Typography,
} from 'antd'
import type { TableColumnsType } from 'antd'
import {
  CopyOutlined, DeleteOutlined, FunctionOutlined, PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import PageHeader from '@/components/PageHeader'
import { modelOptionLabel } from '@/components/modelOptionLabel'
import * as epApi from '@/api/endpoint'
import { getModels, listTasks } from '@/api/task'
import type {
  EndpointCallLogItem, EndpointDetail, EndpointItem, EndpointStats,
  ModelInfo, TaskListItem, Version,
} from '@/types'
import { formatTime } from '@/utils'

const { Text } = Typography

// 获取调用地址（当前页面协议/主机 + 后端前缀）
function invokeUrl(id: number) {
  return `${window.location.origin}/api/v1/endpoints/${id}/invoke`
}

export default function OnlineService() {
  const app = App.useApp()
  const [items, setItems] = useState<EndpointItem[]>([])
  // 折叠区：key=服务id
  const [activeKeys, setActiveKeys] = useState<string[]>([])
  const [details, setDetails] = useState<Record<number, EndpointDetail>>({})
  const [stats, setStats] = useState<Record<number, EndpointStats>>({})
  const [logs, setLogs] = useState<Record<number, EndpointCallLogItem[]>>({})
  // 创建弹窗
  const [createOpen, setCreateOpen] = useState(false)
  const [tasks, setTasks] = useState<TaskListItem[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [ckTask, setCkTask] = useState<number>()
  const [ckName, setCkName] = useState('')
  const [ckDesc, setCkDesc] = useState('')
  const [ckVersions, setCkVersions] = useState<Version[]>([])
  const [ckVersion, setCkVersion] = useState<number | 'best'>('best')
  const [ckModel, setCkModel] = useState<string>()
  const [creating, setCreating] = useState(false)
  // 试调用
  const [testInput, setTestInput] = useState<Record<number, string>>({})
  const [testOutput, setTestOutput] = useState<Record<number, { output: string; latency: number } | null>>({})
  const [testing, setTesting] = useState<Record<number, boolean>>({})

  const loadList = useCallback(async () => {
    try {
      const d = await epApi.listEndpoints()
      setItems(d.items || [])
    } catch { /* 已统一提示 */ }
  }, [])

  useEffect(() => {
    loadList()
    listTasks({ page: 1, page_size: 100 }).then((d) => setTasks(d.items || [])).catch(() => {})
    getModels().then((d) => setModels(d || [])).catch(() => {})
  }, [loadList])

  // 展开服务时加载详情/统计/日志
  useEffect(() => {
    const keys = activeKeys.map(Number)
    keys.forEach(async (id) => {
      if (!details[id]) {
        try {
          const det = await epApi.getEndpoint(id)
          setDetails((m) => ({ ...m, [id]: det }))
        } catch { /* 忽略 */ }
      }
      try {
        const st = await epApi.getEndpointStats(id)
        setStats((m) => ({ ...m, [id]: st }))
      } catch { /* 忽略 */ }
      try {
        const d = await epApi.getEndpointLogs(id)
        setLogs((m) => ({ ...m, [id]: d.items || [] }))
      } catch { /* 忽略 */ }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKeys])

  // 选择任务后加载该任务版本列表（用于创建时选冻结版本）
  const handleTaskChange = async (tid?: number) => {
    setCkTask(tid)
    setCkVersion('best')
    setCkVersions([])
    if (!tid) return
    try { setCkVersions(await epApi.listEndpointVersions(tid)) } catch { /* 忽略 */ }
  }

  const handleCreate = async () => {
    if (!ckTask) { app.message.warning('请选择任务'); return }
    setCreating(true)
    try {
      const res = await epApi.createEndpoint({
        task_id: ckTask,
        name: ckName.trim(),
        description: ckDesc.trim(),
        version_id: ckVersion === 'best' ? null : ckVersion,
        model: ckModel,
      })
      app.message.success('在线服务创建成功')
      setCreateOpen(false)
      setCkName(''); setCkDesc(''); setCkTask(undefined); setCkModel(undefined)
      await loadList()
      if (res.id) setActiveKeys((k) => [String(res.id), ...k])
    } catch { /* 已统一提示 */ } finally {
      setCreating(false)
    }
  }

  const handleToggle = async (id: number, active: boolean) => {
    try {
      await epApi.updateEndpoint(id, { active: active ? 1 : 0 })
      app.message.success(active ? '已启用' : '已停用')
      await loadList()
    } catch { /* 已统一提示 */ }
  }

  const handleRotate = async (id: number) => {
    try {
      const res = await epApi.rotateEndpointKey(id)
      const d = details[id] ? { ...details[id], api_key: res.api_key } : details[id]
      setDetails((m) => ({ ...m, [id]: d as EndpointDetail }))
      app.message.success('密钥已轮换')
    } catch { /* 已统一提示 */ }
  }

  const handleDelete = async (id: number) => {
    try {
      await epApi.deleteEndpoint(id)
      app.message.success('已删除')
      setActiveKeys((k) => k.filter((x) => x !== String(id)))
      await loadList()
    } catch { /* 已统一提示 */ }
  }

  const handleInvoke = async (id: number) => {
    const input = (testInput[id] || '').trim()
    if (!input) { app.message.warning('请输入测试输入'); return }
    const d = details[id]
    if (!d) return
    setTesting((m) => ({ ...m, [id]: true }))
    try {
      const res = await epApi.invokeEndpoint(id, input, d.api_key)
      setTestOutput((m) => ({ ...m, [id]: { output: res.output, latency: res.latency_ms } }))
      await loadList()
      try {
        const lg = await epApi.getEndpointLogs(id)
        setLogs((m) => ({ ...m, [id]: lg.items || [] }))
      } catch { /* 忽略 */ }
    } catch {
      setTestOutput((m) => ({ ...m, [id]: { output: '（调用失败，请查看下方日志/错误提示）', latency: 0 } }))
    } finally {
      setTesting((m) => ({ ...m, [id]: false }))
    }
  }

  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => app.message.success('已复制')).catch(() => app.message.error('复制失败'))
  }

  const logColumns: TableColumnsType<EndpointCallLogItem> = [
    { title: '时间', dataIndex: 'created_at', width: 130, render: (v: string) => <span className="tnum">{formatTime(v)}</span> },
    { title: '状态', dataIndex: 'status', width: 70, render: (s: string) => <Tag color={s === 'success' ? 'green' : 'red'}>{s === 'success' ? '成功' : '失败'}</Tag> },
    { title: '耗时', dataIndex: 'latency_ms', width: 90, align: 'right' as const, render: (v: number | null) => <span className="tnum">{v == null ? '—' : `${v}ms`}</span> },
    {
      title: '输入', dataIndex: 'input_text',
      ellipsis: true, render: (v: string) => <span style={{ color: '#4b5563' }}>{v}</span>,
    },
    {
      title: '输出/错误', key: 'out',
      ellipsis: true,
      render: (_: unknown, r: EndpointCallLogItem) => <span style={{ color: r.error_reason ? '#F03A3E' : '#111827' }}>{r.error_reason || r.output}</span>,
    },
  ]

  return (
    <div>
      <PageHeader
        title="在线服务"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            创建在线服务
          </Button>
        }
      />

      {items.length === 0 ? (
        <div className="pe-card" style={{ padding: 48, textAlign: 'center', color: '#9ca3af' }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}><FunctionOutlined /></div>
          还没有在线服务。点击右上角「创建在线服务」，把任务的提示词一键封装为可调用的 API。
        </div>
      ) : (
        <Collapse
          ghost
          accordion={false}
          activeKey={activeKeys}
          onChange={(k) => setActiveKeys(k as string[])}
          items={items.map((it) => ({
            key: String(it.id),
            label: (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 700, color: '#111827' }}>{it.name}</span>
                <Tag color="geekblue">{it.model}</Tag>
                <Tag color={it.active === 1 ? 'green' : 'default'}>{it.active === 1 ? '启用' : '停用'}</Tag>
                <span className="tnum" style={{ color: '#6b7280', fontSize: 13 }}>调用 {it.call_count} 次</span>
                <span style={{ fontSize: 12, color: '#9ca3af' }}>{new Date(it.created_at).toLocaleString()}</span>
              </div>
            ),
            // 右侧操作：启停开关 + 删除
            extra: (
              <Space size={4}>
                <Switch size="small" checked={it.active === 1} onChange={(v) => handleToggle(it.id, v)} />
                <Popconfirm title="删除后不可恢复，确认删除该在线服务？" onConfirm={() => handleDelete(it.id)}>
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
            children: (() => {
              const d = details[it.id]
              const st = stats[it.id]
              const realLogs = logs[it.id] || []
              const curl = `curl -X POST "${invokeUrl(it.id)}" \\\n  -H "X-Api-Key: ${d?.api_key || ''}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"input":"你的输入"}'`
              return (
                <div style={{ paddingTop: 4 }}>
                  {/* 运行信息 */}
                  <div className="pe-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
                    <div className="pe-stat-card" style={{ padding: '12px 14px' }}>
                      <div className="ol-label">调用地址</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className="tnum" style={{ fontSize: 12, wordBreak: 'break-all' }}>{invokeUrl(it.id)}</span>
                        <Button size="small" type="text" icon={<CopyOutlined />} onClick={() => copy(invokeUrl(it.id))} />
                      </div>
                      <div className="ol-label" style={{ marginTop: 10 }}>API Key</div>
                      <Input.Password
                        size="small" value={d?.api_key || '加载中…'} readOnly
                        onClick={(e) => (e.target as HTMLInputElement).select()}
                        addonAfter={<Button size="small" type="text" icon={<CopyOutlined />} onClick={() => d && copy(d.api_key)} />}
                      />
                      <div style={{ marginTop: 8 }}>
                        <Button size="small" icon={<ReloadOutlined />} onClick={() => handleRotate(it.id)}>轮换密钥</Button>
                      </div>
                    </div>
                    <div className="pe-stat-card" style={{ padding: '12px 14px' }}>
                      <div className="ol-label">示例调用（curl）</div>
                      <pre className="ol-curl">{curl}</pre>
                    </div>
                    <div className="pe-stat-card" style={{ padding: '12px 14px' }}>
                      <div className="ol-label">统计概览</div>
                      <Space size="large" style={{ marginTop: 6 }}>
                        <div><div className="tnum" style={{ fontSize: 22, fontWeight: 800, color: '#0E4AC3' }}>{st?.call_count ?? it.call_count}</div><div className="ol-label">总调用</div></div>
                        <div><div className="tnum" style={{ fontSize: 22, fontWeight: 800, color: '#16A34A' }}>{st?.success ?? 0}</div><div className="ol-label">成功</div></div>
                        <div><div className="tnum" style={{ fontSize: 22, fontWeight: 800, color: '#F03A3E' }}>{st?.failed ?? 0}</div><div className="ol-label">失败</div></div>
                        <div><div className="tnum" style={{ fontSize: 22, fontWeight: 800 }}>{st?.avg_latency_ms != null ? `${st.avg_latency_ms}ms` : '—'}</div><div className="ol-label">平均耗时</div></div>
                      </Space>
                    </div>
                  </div>

                  {/* 部署提示词 */}
                  <div className="pe-card" style={{ padding: '12px 14px', marginBottom: 16 }}>
                    <div className="ol-label">已部署提示词</div>
                    <pre className="ol-prompt" style={{ maxHeight: 90 }}>{d?.prompt || '加载中…'}</pre>
                  </div>

                  {/* 页内试调用 */}
                  <div className="pe-card" style={{ padding: '12px 14px', marginBottom: 16 }}>
                    <div className="ol-label" style={{ marginBottom: 8 }}>页内试调用</div>
                    <Input.TextArea
                      rows={2}
                      placeholder="输入测试内容并点击调用"
                      value={testInput[it.id] || ''}
                      onChange={(e) => setTestInput((m) => ({ ...m, [it.id]: e.target.value }))}
                    />
                    <div style={{ display: 'flex', gap: 12, marginTop: 8, alignItems: 'center' }}>
                      <Button type="primary" icon={<FunctionOutlined />} loading={testing[it.id]}
                              disabled={it.active !== 1} onClick={() => handleInvoke(it.id)}>
                        调用
                      </Button>
                      {testOutput[it.id] && (
                        <Text type="secondary" className="tnum">耗时 {testOutput[it.id]?.latency || 0}ms</Text>
                      )}
                    </div>
                    {testOutput[it.id] && (
                      <pre className="ol-out" style={{ marginTop: 10, whiteSpace: 'pre-wrap' }}>{testOutput[it.id]?.output}</pre>
                    )}
                  </div>

                  {/* 调用日志 */}
                  <div className="pe-card" style={{ padding: 0, overflow: 'hidden' }}>
                    <div className="bm-card-head" style={{ padding: '10px 14px' }}>
                      <h3 className="pe-subtitle" style={{ fontSize: 14 }}>调用日志</h3>
                    </div>
                    <Table<EndpointCallLogItem>
                      rowKey="id" size="small" columns={logColumns} dataSource={realLogs}
                      pagination={{ pageSize: 5, showSizeChanger: false }}
                      locale={{ emptyText: '暂无调用日志' }}
                    />
                  </div>
                </div>
              )
            })(),
          }))}
        />
      )}

      {/* 创建弹窗 */}
      <Modal
        title="创建在线服务"
        open={createOpen}
        onOk={handleCreate}
        confirmLoading={creating}
        onCancel={() => setCreateOpen(false)}
        okText="创建" cancelText="取消"
        width={560}
      >
        <div style={{ marginTop: 8 }}>
          <div className="ol-label">任务</div>
          <Select
            showSearch optionFilterProp="label" style={{ width: '100%', marginBottom: 12 }}
            placeholder="选择要上线的任务" value={ckTask} onChange={handleTaskChange}
            options={tasks.map((t) => ({ label: t.name, value: t.id }))}
          />
          <div className="ol-label">名称</div>
          <Input style={{ marginBottom: 12 }} placeholder="在线服务名称（留空自动命名）" value={ckName} onChange={(e) => setCkName(e.target.value)} />
          <div className="ol-label">描述</div>
          <Input.TextArea rows={2} style={{ marginBottom: 12 }} placeholder="用途说明（可选）" value={ckDesc} onChange={(e) => setCkDesc(e.target.value)} />
          <div className="ol-label">发布提示词</div>
          <Select
            style={{ width: '100%', marginBottom: 12 }} value={ckVersion} onChange={setCkVersion}
            options={[
              { label: '当前最优/初始提示词', value: 'best' },
              ...ckVersions.map((v) => ({
                label: `V${v.version_no}·${(v.prompt_text || '').slice(0, 24)}${v.frozen === 1 ? '（已冻结）' : ''}`,
                value: v.id,
              })),
            ]}
          />
          <div className="ol-label">执行模型（可选）</div>
          <Select
            allowClear style={{ width: '100%' }} placeholder="留空则使用任务配置的执行模型"
            value={ckModel} onChange={setCkModel}
            options={models.map((m) => ({ label: modelOptionLabel(m), value: m.id }))}
          />
        </div>
      </Modal>
    </div>
  )
}
