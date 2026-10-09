// ==========================================================
// 知识库（RAG 检索评测）页：
//   建库/列表/删除 → 库详情内：上传语料、一键导入示例语料、
//   检索命中预览、RAG 检索+生成评测（来源支撑度 + 忠实度）
// ==========================================================
import { useEffect, useState } from 'react'
import {
  App, Button, Card, Empty, Input, List, Modal, Popconfirm,
  Progress, Space, Spin, Tag,
} from 'antd'
import {
  CloudUploadOutlined, DatabaseOutlined, DeleteOutlined, PlusOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import PageHeader from '@/components/PageHeader'
import * as kbApi from '@/api/knowledge'
import type {
  KnowledgeBase, RetrieveHit, RagEvaluateResult,
} from '@/types'

const { TextArea } = Input

// 来源支撑度/忠实度 → 颜色
function scoreColor(v?: number) {
  const s = v ?? 0
  if (s >= 80) return '#16A34A'
  if (s >= 60) return '#F59E0B'
  return '#F03A3E'
}

export default function KnowledgeBasePage() {
  const app = App.useApp()
  const [items, setItems] = useState<KnowledgeBase[]>([])
  const [activeKb, setActiveKb] = useState<number>()
  const [detail, setDetail] = useState<KnowledgeBase>()
  const [detailLoading, setDetailLoading] = useState(false)
  // 创建弹窗
  const [createOpen, setCreateOpen] = useState(false)
  const [ckName, setCkName] = useState('')
  const [ckDesc, setCkDesc] = useState('')
  const [creating, setCreating] = useState(false)
  // 上传语料
  const [docOpen, setDocOpen] = useState(false)
  const [docTitle, setDocTitle] = useState('')
  const [docContent, setDocContent] = useState('')
  const [docSaving, setDocSaving] = useState(false)
  // 检索预览
  const [retrieveQuery, setRetrieveQuery] = useState('')
  const [retrieveHits, setRetrieveHits] = useState<RetrieveHit[]>([])
  const [retrieving, setRetrieving] = useState(false)
  // RAG 评测
  const [evalQuery, setEvalQuery] = useState('')
  const [evalResult, setEvalResult] = useState<RagEvaluateResult | null>(null)
  const [evaluating, setEvaluating] = useState(false)

  const loadList = async () => {
    try {
      const d = await kbApi.listKnowledgeBases()
      setItems(d.items || [])
    } catch { /* 已统一提示 */ }
  }

  useEffect(() => { loadList() }, [])

  // 选定知识库后加载详情（含文档列表）
  useEffect(() => {
    if (!activeKb) { setDetail(undefined); return }
    setDetailLoading(true)
    kbApi.getKnowledgeBase(activeKb)
      .then((d) => setDetail(d))
      .catch(() => {})
      .finally(() => setDetailLoading(false))
  }, [activeKb])

  const handleCreate = async () => {
    if (!ckName.trim()) { app.message.warning('请输入知识库名称'); return }
    setCreating(true)
    try {
      await kbApi.createKnowledgeBase({ name: ckName.trim(), description: ckDesc.trim() })
      app.message.success('知识库已创建')
      setCreateOpen(false)
      setCkName(''); setCkDesc('')
      await loadList()
    } catch { /* 已统一提示 */ } finally {
      setCreating(false)
    }
  }

  const handleUploadDoc = async () => {
    if (!activeKb) return
    if (!docContent.trim()) { app.message.warning('请输入语料内容'); return }
    setDocSaving(true)
    try {
      const r = await kbApi.addDoc(activeKb, { title: docTitle.trim(), content: docContent })
      app.message.success(`入库成功，切分为 ${r.chunk_count} 个检索块`)
      setDocOpen(false); setDocTitle(''); setDocContent('')
      await afterKbChange()
    } catch { /* 已统一提示 */ } finally {
      setDocSaving(false)
    }
  }

  const handleImportCorpus = async () => {
    if (!activeKb) return
    try {
      const r = await kbApi.importCorpus(activeKb)
      app.message.success(`示例语料导入完成：成功 ${r.success} / ${r.total}`)
      await afterKbChange()
    } catch { /* 已统一提示 */ }
  }

  const handleRetrieve = async () => {
    if (!activeKb) return
    const q = retrieveQuery.trim()
    if (!q) { app.message.warning('请输入检索问题'); return }
    setRetrieving(true)
    try {
      const r = await kbApi.retrieve(activeKb, q, 4)
      setRetrieveHits(r.hits || [])
    } catch { /* 已统一提示 */ } finally {
      setRetrieving(false)
    }
  }

  const handleEvaluate = async () => {
    if (!activeKb) return
    const q = evalQuery.trim()
    if (!q) { app.message.warning('请输入评测问题'); return }
    setEvaluating(true)
    try {
      const r = await kbApi.evaluate(activeKb, { query: q, top_k: 4 })
      setEvalResult(r)
    } catch { /* 已统一提示 */ } finally {
      setEvaluating(false)
    }
  }

  // 刷新列表与当前库详情（文档数/块数）
  const afterKbChange = async () => {
    await loadList()
    if (activeKb) {
      kbApi.getKnowledgeBase(activeKb).then(setDetail).catch(() => {})
    }
  }

  const active = detail ?? items.find((b) => b.id === activeKb)

  return (
    <div>
      <PageHeader
        title="知识库"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            创建知识库
          </Button>
        }
      />

      {items.length === 0 ? (
        <div className="pe-card" style={{ padding: 48, textAlign: 'center', color: '#9ca3af' }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}><DatabaseOutlined /></div>
          还没有知识库。创建知识库后上传语料，即可用于 RAG 检索与任务评测。
        </div>
      ) : (
        <Card
          size="small" title="我的知识库" style={{ marginBottom: 16 }}
          extra={<Tag>{items.length} 个</Tag>}
        >
          <List
            grid={{ gutter: 12, xs: 1, sm: 1, md: 2, lg: 3, xl: 3, xxl: 4 }}
            dataSource={items}
            renderItem={(kb) => (
              <List.Item>
                <Card
                  size="small"
                  hoverable
                  className="pe-rag-kb-card"
                  style={{ borderColor: activeKb === kb.id ? '#0E4AC3' : undefined }}
                  onClick={() => setActiveKb(kb.id)}
                  title={<span style={{ fontWeight: 700 }}>{kb.name}</span>}
                  extra={
                    <Popconfirm title="删除后语料与检索块一并清除，确认？"
                                onConfirm={async () => {
                                  await kbApi.deleteKnowledgeBase(kb.id)
                                  app.message.success('已删除')
                                  if (activeKb === kb.id) setActiveKb(undefined)
                                  loadList()
                                }}>
                      <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  }
                >
                  <div className="ol-label" style={{ color: '#6b7280', height: 20, overflow: 'hidden' }}>
                    {kb.description || '（无描述）'}
                  </div>
                  <Space size="large" style={{ marginTop: 6 }}>
                    <span className="tnum" style={{ color: '#6b7280', fontSize: 13 }}>
                      文档 {kb.doc_count}
                    </span>
                    <span className="tnum" style={{ color: '#6b7280', fontSize: 13 }}>
                      块 {kb.chunk_count}
                    </span>
                    <span style={{ fontSize: 12, color: kb.embed_model ? '#16A34A' : '#9ca3af' }}>
                      {kb.embed_model ? '向量检索' : '词法检索'}
                    </span>
                  </Space>
                </Card>
              </List.Item>
            )}
          />
        </Card>
      )}

      {active && (
        <div className="pe-rag-panel">
          <Spin spinning={detailLoading}>
          {/* 标题 + 操作 */}
          <div className="pe-card" style={{ padding: '14px 16px', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 800, fontSize: 16 }}>{active.name}</span>
              <Tag color={active.embed_model ? 'green' : 'default'}>
                {active.embed_model ? `向量检索 · ${active.embed_model}` : '词法检索（无外部依赖）'}
              </Tag>
              <span className="tnum" style={{ color: '#6b7280' }}>文档 {active.doc_count} · 块 {active.chunk_count}</span>
              <div style={{ flex: 1 }} />
              <Button icon={<RocketOutlined />} onClick={handleImportCorpus}>一键导入示例语料</Button>
              <Button type="primary" icon={<CloudUploadOutlined />} onClick={() => setDocOpen(true)}>
                上传语料
              </Button>
            </div>
            {/* 文档列表 */}
            {active.docs && active.docs.length > 0 && (
              <List
                size="small" style={{ marginTop: 12 }}
                dataSource={active.docs.slice(0, 8)}
                renderItem={(d) => (
                  <List.Item style={{ padding: '6px 0' }}>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {d.title}
                    </span>
                    <span className="tnum" style={{ color: '#9ca3af', fontSize: 13 }}>{d.content}</span>
                  </List.Item>
                )}
              />
            )}
          </div>

          {/* 检索预览 */}
          <div className="pe-card" style={{ padding: '14px 16px', marginBottom: 12 }}>
            <div className="ol-label" style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>检索命中预览</div>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入一个问题，查看知识库中命中的块（如：前端使用什么技术栈？）"
                value={retrieveQuery}
                onChange={(e) => setRetrieveQuery(e.target.value)}
                onPressEnter={handleRetrieve}
              />
              <Button type="primary" loading={retrieving} onClick={handleRetrieve}>检索</Button>
            </Space.Compact>
            {retrieveHits.length > 0 && (
              <List
                size="small" style={{ marginTop: 10 }}
                dataSource={retrieveHits}
                renderItem={(h) => (
                  <List.Item style={{ padding: '6px 0' }}>
                    <div style={{ width: '100%' }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
                        <Tag color="geekblue">#{h.score.toFixed(3)}</Tag>
                        <span className="ol-label" style={{ fontWeight: 600 }}>{h.doc_title}</span>
                        <span className="tnum" style={{ color: '#9ca3af', fontSize: 12 }}>块 {h.seq}</span>
                      </div>
                      <div style={{ fontSize: 13, color: '#374151' }}>{h.text}</div>
                    </div>
                  </List.Item>
                )}
              />
            )}
            {retrieveHits.length === 0 && !retrieving && (
              <Empty style={{ marginTop: 8 }} description="暂无检索结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </div>

          {/* RAG 检索+生成评测 */}
          <div className="pe-card" style={{ padding: '14px 16px' }}>
            <div className="ol-label" style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>
              RAG 检索 + 生成评测
            </div>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入一个问题，检索知识库后生成答案并评估忠实度（如：本项目整体架构？）"
                value={evalQuery}
                onChange={(e) => setEvalQuery(e.target.value)}
                onPressEnter={handleEvaluate}
              />
              <Button type="primary" loading={evaluating} onClick={handleEvaluate}>生成并评测</Button>
            </Space.Compact>

            {evalResult && (
              <div style={{ marginTop: 14 }}>
                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>生成答案</div>
                <pre className="ol-out" style={{ whiteSpace: 'pre-wrap', background: '#f6f7fb', padding: 12, borderRadius: 8 }}>
                  {evalResult.answer}
                </pre>
                <Space size="large" style={{ marginTop: 12 }}>
                  <div>
                    <div className="ol-label">来源支撑度（确定性）</div>
                    <Progress
                      percent={Math.round(evalResult.source_score)} size="small"
                      strokeColor={scoreColor(evalResult.source_score)}
                      format={() => `${evalResult.source_score}%`}
                      style={{ width: 200 }}
                    />
                  </div>
                  <div>
                    <div className="ol-label">忠实度（LLM 评审）</div>
                    <Progress
                      percent={Math.round(evalResult.faithfulness.score)} size="small"
                      strokeColor={scoreColor(evalResult.faithfulness.score)}
                      format={() => `${evalResult.faithfulness.score}%`}
                      style={{ width: 200 }}
                    />
                  </div>
                </Space>
                <div className="ol-label" style={{ marginTop: 8, color: '#6b7280' }}>
                  评审依据：{evalResult.faithfulness.reason}
                </div>
                <div className="ol-label" style={{ marginTop: 12, marginBottom: 4 }}>引用到的知识块</div>
                {evalResult.retrieved.map((h, i) => (
                  <div key={i} style={{ fontSize: 13, color: '#374151', padding: '4px 0' }}>
                    <Tag color="green">#[来源{i + 1}]</Tag>
                    <b>{h.doc_title}</b>（{h.score.toFixed(3)}）：{h.text}
                  </div>
                ))}
              </div>
            )}
          </div>
          </Spin>
        </div>
      )}

      {/* 创建弹窗 */}
      <Modal title="创建知识库" open={createOpen} onOk={handleCreate}
             confirmLoading={creating} onCancel={() => setCreateOpen(false)} okText="创建" cancelText="取消">
        <div style={{ marginTop: 8 }}>
          <div className="ol-label">名称</div>
          <Input style={{ marginBottom: 12 }} placeholder="知识库名称" value={ckName}
                 onChange={(e) => setCkName(e.target.value)} />
          <div className="ol-label">描述</div>
          <Input.TextArea rows={3} placeholder="用途说明（可选）" value={ckDesc}
                          onChange={(e) => setCkDesc(e.target.value)} />
        </div>
      </Modal>

      {/* 上传语料弹窗 */}
      <Modal title="上传语料" open={docOpen} onOk={handleUploadDoc} confirmLoading={docSaving}
             onCancel={() => setDocOpen(false)} okText="入库" cancelText="取消" width={620}>
        <div style={{ marginTop: 8 }}>
          <div className="ol-label">标题（可选）</div>
          <Input style={{ marginBottom: 12 }} placeholder="例如：系统架构说明" value={docTitle}
                 onChange={(e) => setDocTitle(e.target.value)} />
          <div className="ol-label">语料正文</div>
          <TextArea rows={10} placeholder="粘贴或输入语料内容，系统将自动分块并建立检索索引"
                    value={docContent} onChange={(e) => setDocContent(e.target.value)} />
        </div>
      </Modal>
    </div>
  )
}