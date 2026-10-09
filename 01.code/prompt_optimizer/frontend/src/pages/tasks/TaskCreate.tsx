// ==========================================================
// 创建任务页：蓝块步骤条「基础信息 → 测试用例 → 确认并创建」
// ==========================================================
import { useEffect, useRef, useState } from 'react'
import { Form, Input, InputNumber, Button, Select, Space, App, Upload, Table, Tag, Divider, Collapse, Switch } from 'antd'
import { InboxOutlined, DeleteOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getTemplates, getModels, createTask, addCase, startIteration } from '@/api/task'
import * as kbApi from '@/api/knowledge'
import { parseCaseContent, type CaseRow } from '@/utils/caseParser'
import PageHeader from '@/components/PageHeader'
import { modelOptionLabel } from '@/components/modelOptionLabel'
import { Panel, SectionTitle } from '@/components/ui'
import type { TaskType, ModelInfo, TaskTemplate, KnowledgeBase } from '@/types'
import { TASK_TYPE_LABEL } from '@/types'

// 本地文件解析（JSON/CSV）
function parseCaseFile(file: File): Promise<{ rows: Partial<CaseRow>[]; errors: string[] }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        resolve(parseCaseContent(String(reader.result), file.name))
      } catch (e) {
        reject(e)
      }
    }
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.readAsText(file)
  })
}

// 从路由 query 读取预选任务类型（由侧边栏带过来），非法值回退到默认文本生成
function resolveType(raw: string | null): TaskType {
  return (raw && TASK_TYPE_LABEL[raw as TaskType]) ? (raw as TaskType) : 'text_gen'
}

export default function TaskCreate() {
  const app = App.useApp()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [form] = Form.useForm()
  const [step, setStep] = useState(0)
  const [taskType, setTaskType] = useState<TaskType>(() => resolveType(searchParams.get('type')))

  // 侧边栏切换任务类型时同步；类型变化后回到基础信息一步，并回填对应模板，避免用例清单与类型错配
  useEffect(() => {
    const t = resolveType(searchParams.get('type'))
    setTaskType(t)
    setStep(0)
    applyTemplate(t)
  }, [searchParams])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [cases, setCases] = useState<CaseRow[]>([])
  const [caseInput, setCaseInput] = useState({ input_text: '', reference_output: '', keywords: '' })
  const [importing, setImporting] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const templatesRef = useRef<TaskTemplate[]>([])

  // 命中预置模板则回填描述与评分标准
  const applyTemplate = (t: TaskType) => {
    const tmpl = templatesRef.current.find((x) => x.task_type === t)
    if (tmpl) {
      form.setFieldsValue({ description: tmpl.description_template, criteria: tmpl.criteria_template })
    }
  }

  useEffect(() => {
    getTemplates()
      .then((ts) => {
        templatesRef.current = ts
        // 模板加载完成后，按初始任务类型回填
        applyTemplate(resolveType(searchParams.get('type')))
      })
      .catch(() => {})
    getModels().then(setModels).catch(() => {})
    kbApi.listKnowledgeBases().then((d) => setKbs(d.items || [])).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onImport = async (file: File) => {
    setImporting(true)
    try {
      const { rows, errors } = await parseCaseFile(file)
      setCases((prev) => [...prev, ...(rows as CaseRow[])])
      if (errors.length > 0) {
        app.message.warning(`解析成功 ${rows.length} 条，失败 ${errors.length} 条：${errors.slice(0, 3).join('；')}`)
      } else {
        app.message.success(`成功导入 ${rows.length} 条用例`)
      }
    } catch (e) {
      app.message.error((e as Error).message)
    } finally {
      setImporting(false)
    }
    return false
  }

  const onAddCase = () => {
    if (!caseInput.input_text.trim()) {
      app.message.warning('请先输入「输入」内容')
      return
    }
    setCases((prev) => [
      ...prev,
      {
        input_text: caseInput.input_text,
        reference_output: caseInput.reference_output || undefined,
        keywords: caseInput.keywords
          ? caseInput.keywords.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
          : undefined,
      },
    ])
    setCaseInput({ input_text: '', reference_output: '', keywords: '' })
  }

  const caseColumns = [
    { title: '#', key: 'idx', width: 56, render: (_: unknown, __: CaseRow, idx: number) => <span className="seq-no">{String(idx + 1).padStart(2, '0')}</span> },
    { title: '输入', dataIndex: 'input_text', key: 'input_text', ellipsis: true },
    {
      title: '关键词',
      key: 'keywords',
      render: (_: unknown, r: CaseRow) => r.keywords?.map((k) => <Tag key={k}>{k}</Tag>) ?? '—',
    },
    {
      title: '操作',
      key: 'op',
      width: 72,
      render: (_: unknown, _r: CaseRow, idx: number) => (
        <Button type="text" danger icon={<DeleteOutlined />} onClick={() => setCases((p) => p.filter((_, i) => i !== idx))} />
      ),
    },
  ]

  const nextStep = async () => {
    try {
      await form.validateFields()
      setStep(1)
    } catch {
      /* 校验失败停留 */
    }
  }

  const handleCreate = async (runImmediately: boolean = false) => {
    const values = form.getFieldsValue()
    setSubmitting(true)
    try {
      const task = await createTask({
        name: values.name,
        task_type: taskType,
        description: values.description,
        objective: values.objective,
        criteria: values.criteria,
        execution_model: values.execution_model || undefined,
        judge_model: values.judge_model || undefined,
        auto_weight: values.auto_weight ?? 0.5,
        judge_weight: values.judge_weight ?? 0.5,
        initial_prompt: values.initial_prompt || undefined,
        target_score: values.target_score ?? undefined,
        max_rounds: values.max_rounds ?? 5,
        variants_per_round: values.variants_per_round ?? 4,
        concurrency: values.concurrency ?? 2,
        stagnant_rounds: values.stagnant_rounds ?? 2,
        kb_id: values.enable_rag ? values.kb_id ?? null : null,
        enable_rag: values.enable_rag ? 1 : 0,
      })
      for (const c of cases) {
        await addCase(task.id, {
          input_text: c.input_text,
          reference_output: c.reference_output,
          keywords: c.keywords,
          run_test: c.run_test,
        })
      }
      // 一键创建并运行：创建成功后立即触发首轮迭代，省去"先创建再手动点开始"
      if (runImmediately) {
        await startIteration(task.id)
        app.message.success('任务已创建并开始迭代')
      } else {
        app.message.success('任务创建成功')
      }
      navigate(`/tasks/${task.id}`, { replace: true })
    } catch {
      /* 错误已统一提示 */
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader title="创建任务" en="create task" />

      {/* 步骤一：基础信息（Form 始终挂载，仅切换显隐，避免 store 丢失） */}
      <Form
        form={form}
        layout="vertical"
        style={{ display: step === 0 ? 'block' : 'none' }}
        initialValues={{ auto_weight: 0.5, judge_weight: 0.5, max_rounds: 5, variants_per_round: 4, concurrency: 2, stagnant_rounds: 2 }}
      >
        <Panel>
          {/* 任务类型由侧边栏预选，这里仅做只读回显 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
            <span style={{ fontSize: 13, color: 'var(--pe-muted)' }}>当前任务类型</span>
            <Tag color="blue" style={{ margin: 0 }}>{TASK_TYPE_LABEL[taskType]}</Tag>
          </div>

          <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }, { max: 50, message: '不超过 50 字' }]}>
            <Input placeholder="例如：电商客服话术优化" />
          </Form.Item>
          <Form.Item name="description" label="任务描述" rules={[{ required: true, message: '请输入任务描述' }]}>
            <Input.TextArea rows={4} placeholder="清晰地描述需要优化提示词的生成任务" />
          </Form.Item>
          <Form.Item name="objective" label="优化目标" rules={[{ required: true, message: '请输入优化目标' }]}>
            <Input.TextArea rows={2} placeholder="例如：提升回复的一次解决率与合规性" />
          </Form.Item>
          <Form.Item name="criteria" label="评分标准" rules={[{ required: true, message: '请输入评分标准' }]}>
            <Input.TextArea rows={4} placeholder="描述评判一份输出的标准（将用于评审打分）" />
          </Form.Item>
        </Panel>

        {/* 高级设置：默认折叠，降低普通用户配置门槛；forceRender 保证折叠时字段仍注册，避免值丢失 */}
        <Collapse
          ghost
          style={{ marginTop: 20, border: '1px solid var(--pe-border)' }}
          items={[
            {
              key: 'advanced',
              label: (
                <span style={{ fontWeight: 700 }}>
                  高级设置（模型 / 权重 / 迭代参数）
                </span>
              ),
              forceRender: true,
              children: (
                <div style={{ paddingTop: 8 }}>
                  <Divider orientation="left" plain style={{ marginTop: 0 }}>
                    模型与权重
                  </Divider>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Form.Item name="execution_model" label="执行模型">
                      <Select placeholder="系统推荐" options={models.map((m) => ({ label: modelOptionLabel(m, true), value: m.id }))} allowClear />
                    </Form.Item>
                    <Form.Item name="judge_model" label="评审模型">
                      <Select placeholder="沿用执行模型" options={models.map((m) => ({ label: modelOptionLabel(m, true), value: m.id }))} allowClear />
                    </Form.Item>
                    <Form.Item name="auto_weight" label="自动指标权重">
                      <InputNumber min={0} max={1} step={0.1} />
                    </Form.Item>
                    <Form.Item name="judge_weight" label="评审打分权重">
                      <InputNumber min={0} max={1} step={0.1} />
                    </Form.Item>
                  </div>

                  <Divider orientation="left" plain>
                    迭代参数
                  </Divider>
                  <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
                    <Form.Item name="variants_per_round" label="每轮变体数">
                      <InputNumber min={1} max={20} />
                    </Form.Item>
                    <Form.Item name="max_rounds" label="最大轮次">
                      <InputNumber min={1} max={100} />
                    </Form.Item>
                    <Form.Item name="concurrency" label="并发数">
                      <InputNumber min={1} max={10} />
                    </Form.Item>
                    <Form.Item name="stagnant_rounds" label="收敛判定轮数">
                      <InputNumber min={1} max={20} />
                    </Form.Item>
                    <Form.Item
                      name="target_score"
                      label="目标分数（可选）"
                      tooltip="留空（默认）则不含达标线，任务会持续迭代，直到连续 N 轮无提升或达到最大轮次。填写后达到该分即提前完成。"
                    >
                      <InputNumber min={0} max={100} placeholder="留空=靠收敛自动多跑" />
                    </Form.Item>
                  </div>

                  <Form.Item name="initial_prompt" label="初始提示词（可选）" style={{ marginBottom: 8 }}>
                    <Input.TextArea rows={4} placeholder="留空则由系统在首轮自动生成" />
                  </Form.Item>

                  <Divider orientation="left" plain>
                    RAG 检索增强
                  </Divider>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
                    <Form.Item name="enable_rag" label="启用知识库检索" valuePropName="checked" style={{ marginBottom: 0 }}>
                      <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                    </Form.Item>
                    <Form.Item
                      noStyle
                      shouldUpdate={(prev, cur) => prev.enable_rag !== cur.enable_rag}
                    >
                      {({ getFieldValue }) =>
                        getFieldValue('enable_rag') ? (
                          <Form.Item name="kb_id" label="绑定知识库" rules={[{ required: true, message: '请选择知识库' }]}>
                            <Select
                              style={{ minWidth: 260 }}
                              placeholder="选择知识库，评测时自动检索注入上下文"
                              options={kbs.map((b) => ({
                                label: `${b.name}（${b.chunk_count} 块）`,
                                value: b.id,
                              }))}
                            />
                          </Form.Item>
                        ) : null
                      }
                    </Form.Item>
                  </div>
                </div>
              ),
            },
          ]}
        />

        <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
          <button type="button" className="pe-btn pe-btn-blue" onClick={nextStep}>
            下一步：测试用例
          </button>
        </div>
      </Form>

      {/* 步骤二：测试用例 */}
      {step === 1 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <Panel>
            <SectionTitle title="添加用例" en="add case" />
            <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
              <input
                className="pe-input"
                placeholder="输入（必填）"
                value={caseInput.input_text}
                onChange={(e) => setCaseInput((s) => ({ ...s, input_text: e.target.value }))}
              />
              <input
                className="pe-input"
                placeholder="参考输出（可选）"
                value={caseInput.reference_output}
                onChange={(e) => setCaseInput((s) => ({ ...s, reference_output: e.target.value }))}
              />
              <input
                className="pe-input"
                placeholder="关键词（逗号分隔，可选）"
                value={caseInput.keywords}
                onChange={(e) => setCaseInput((s) => ({ ...s, keywords: e.target.value }))}
              />
              <button type="button" className="pe-btn pe-btn-blue" onClick={onAddCase}>
                添加
              </button>
            </div>
          </Panel>

          <Panel style={{ padding: 0 }}>
            <Upload.Dragger accept=".json,.csv" showUploadList={false} beforeUpload={onImport as never} disabled={importing} style={{ border: 0, background: 'transparent' }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件导入（支持 JSON / CSV）</p>
              <p className="ant-upload-hint">字段：input_text（必填）、reference_output、keywords、run_test（代码生成）</p>
            </Upload.Dragger>
          </Panel>

          <Panel tight>
            <div style={{ padding: '18px 22px 0' }}>
              <SectionTitle title={`已添加用例（${cases.length} 条）`} en="cases" />
            </div>
            <Table
              rowKey={(_, i) => String(i)}
              size="small"
              columns={caseColumns}
              dataSource={cases}
              pagination={false}
              locale={{ emptyText: '尚未添加用例' }}
            />
            {cases.length > 0 && (
              <div style={{ padding: '10px 22px 18px' }}>
                <Button size="small" danger onClick={() => setCases([])}>
                  清空全部
                </Button>
              </div>
            )}
          </Panel>

          <Space style={{ justifyContent: 'flex-end' }}>
            <button type="button" className="pe-btn pe-btn-line" onClick={() => setStep(0)}>
              上一步
            </button>
            <button type="button" className="pe-btn pe-btn-blue" disabled={cases.length === 0} onClick={() => setStep(2)}>
              下一步：确认创建
            </button>
          </Space>
        </div>
      )}

      {/* 步骤三：确认并创建 */}
      {step === 2 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <Panel>
            <SectionTitle title="任务摘要" en="summary" />
            <table className="pe-table">
              <tbody>
                <tr><td style={{ width: 150, color: 'var(--pe-muted-foreground)' }}>类型</td><td>{TASK_TYPE_LABEL[taskType]}（{taskType}）</td></tr>
                <tr><td style={{ color: 'var(--pe-muted-foreground)' }}>名称</td><td>{form.getFieldValue('name')}</td></tr>
                <tr><td style={{ color: 'var(--pe-muted-foreground)' }}>用例数</td><td>{cases.length} 条</td></tr>
                <tr><td style={{ color: 'var(--pe-muted-foreground)' }}>每轮变体</td><td>{form.getFieldValue('variants_per_round')} 个</td></tr>
                <tr><td style={{ color: 'var(--pe-muted-foreground)' }}>最大轮次</td><td>{form.getFieldValue('max_rounds')} 轮</td></tr>
                <tr><td style={{ color: 'var(--pe-muted-foreground)' }}>权重</td><td>自动 {form.getFieldValue('auto_weight')} / 评审 {form.getFieldValue('judge_weight')}</td></tr>
                <tr><td style={{ color: 'var(--pe-muted-foreground)' }}>目标分数</td><td>{form.getFieldValue('target_score') ?? '不设达标线（靠收敛自动停止）'}</td></tr>
                <tr><td style={{ color: 'var(--pe-muted-foreground)' }}>RAG 检索增强</td><td>{form.getFieldValue('enable_rag') ? `开启（知识库：${kbs.find((b) => b.id === form.getFieldValue('kb_id'))?.name ?? form.getFieldValue('kb_id') ?? '未选择'}）` : '关闭'}</td></tr>
              </tbody>
            </table>
          </Panel>
          <Space style={{ justifyContent: 'flex-end' }}>
            <button type="button" className="pe-btn pe-btn-line" onClick={() => setStep(1)}>
              上一步
            </button>
            <button type="button" className="pe-btn pe-btn-line" disabled={submitting} onClick={() => handleCreate(false)}>
              {submitting ? '创建中…' : '仅创建'}
            </button>
            <button type="button" className="pe-btn pe-btn-blue" disabled={submitting} onClick={() => handleCreate(true)}>
              <ThunderboltOutlined />
              {submitting ? '创建中…' : '创建并立即运行'}
            </button>
          </Space>
        </div>
      )}
    </div>
  )
}
