// ==========================================================
// 用例集子页：用例表格 + 单条添加 + 批量导入 + 删除
// ==========================================================
import { useCallback, useEffect, useState } from 'react'
import { Table, Button, Modal, Form, Input, App, Tag, Upload } from 'antd'
import { PlusOutlined, InboxOutlined } from '@ant-design/icons'
import { listCases, addCase, importCases, deleteCase } from '@/api/task'
import { Panel, SectionTitle } from '@/components/ui'
import type { TestCase } from '@/types'

interface Props {
  taskId: number
  running: boolean
  onRefresh: () => void
}

export default function TaskCases({ taskId, running, onRefresh }: Props) {
  const app = App.useApp()
  const [form] = Form.useForm()
  const [items, setItems] = useState<TestCase[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [importing, setImporting] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listCases(taskId, { page, page_size: pageSize })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      /* 错误统一提示 */
    } finally {
      setLoading(false)
    }
  }, [taskId, page, pageSize])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 添加单条用例
  const handleAdd = async (values: { input_text: string; reference_output?: string; keywords?: string; run_test?: string }) => {
    try {
      await addCase(taskId, {
        input_text: values.input_text,
        reference_output: values.reference_output || undefined,
        keywords: values.keywords ? values.keywords.split(/[,，]/).map((s) => s.trim()).filter(Boolean) : undefined,
        run_test: values.run_test || undefined,
      })
      app.message.success('已添加用例')
      setModalOpen(false)
      form.resetFields()
      fetchData()
      onRefresh()
    } catch {
      /* 错误统一提示 */
    }
  }

  // 批量导入
  const onImport = async (file: File) => {
    setImporting(true)
    try {
      const data = await importCases(taskId, file)
      if (data.failed > 0) {
        app.message.warning(`导入成功 ${data.success} 条，失败 ${data.failed} 条`)
      } else {
        app.message.success(`成功导入 ${data.success} 条`)
      }
      fetchData()
      onRefresh()
    } catch {
      app.message.error('导入失败')
    } finally {
      setImporting(false)
    }
    return false
  }

  // 删除用例（运行中禁止）
  const handleDelete = (caseId: number) => {
    app.modal.confirm({
      title: '删除用例',
      content: '确定删除该用例吗？',
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        await deleteCase(taskId, caseId)
        app.message.success('已删除')
        fetchData()
        onRefresh()
      },
    })
  }

  const columns = [
    {
      title: '#',
      key: 'idx',
      width: 56,
      render: (_: unknown, __: TestCase, idx: number) => <span className="seq-no">{String((page - 1) * pageSize + idx + 1).padStart(2, '0')}</span>,
    },
    { title: '输入', dataIndex: 'input_text', key: 'input_text' },
    { title: '参考输出', dataIndex: 'reference_output', key: 'reference_output', ellipsis: true, render: (v: string | null) => v || '—' },
    {
      title: '关键词',
      dataIndex: 'keywords',
      key: 'keywords',
      render: (v: string | null) => {
        if (!v) return '—'
        return v
          .split(/[,，]/)
          .map((k) => k.trim())
          .filter(Boolean)
          .slice(0, 5)
          .map((k) => <Tag key={k}>{k}</Tag>)
      },
    },
    {
      title: '操作',
      key: 'op',
      width: 90,
      render: (_: unknown, r: TestCase) => (
        <Button type="link" danger disabled={running} onClick={() => handleDelete(r.id)}>
          删除
        </Button>
      ),
    },
  ]

  return (
    <Panel tight>
      <div style={{ padding: '20px 22px 0', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <SectionTitle title={`测试用例（${total} 条）`} en="test cases" />
        <div style={{ display: 'flex', gap: 10, paddingBottom: 14 }}>
          <Upload accept=".json,.csv" showUploadList={false} beforeUpload={onImport as never} disabled={running || importing}>
            <button className="pe-btn pe-btn-line pe-btn-sm" disabled={running || importing}>
              <InboxOutlined />
              批量导入
            </button>
          </Upload>
          <button className="pe-btn pe-btn-blue pe-btn-sm" disabled={running} onClick={() => setModalOpen(true)}>
            <PlusOutlined />
            添加用例
          </button>
        </div>
      </div>

      {running && (
        <div style={{ padding: '0 22px 12px', fontSize: 12.5, color: 'var(--pe-muted-foreground)' }}>
          任务运行中，用例暂不可修改，改动将在下次迭代生效。
        </div>
      )}

      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={items}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
      />

      {/* 添加用例弹窗 */}
      <Modal title="添加用例" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} okText="添加" cancelText="取消">
        <Form form={form} layout="vertical" onFinish={handleAdd} style={{ marginTop: 14 }}>
          <Form.Item name="input_text" label="输入" rules={[{ required: true, message: '请输入输入文本' }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="reference_output" label="参考输出（可选）">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="keywords" label="关键词（逗号分隔，可选）">
            <Input placeholder="降噪, 续航, 防水" />
          </Form.Item>
          <Form.Item name="run_test" label="单元测试（代码生成可选）">
            <Input.TextArea rows={2} placeholder={'JSON 字符串，例如：{"inputs":[["hello"],["aba"]],"expected":[false,true]}'} />
          </Form.Item>
        </Form>
      </Modal>
    </Panel>
  )
}
