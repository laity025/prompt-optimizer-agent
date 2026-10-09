// ==========================================================
// 报告共享管理：查看我的分享链接、复制访问地址、撤销链接
// ==========================================================
import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Empty, Popconfirm, Space, Table, Tag, Tooltip, message } from 'antd'
import { CopyOutlined, LinkOutlined, StopOutlined } from '@ant-design/icons'
import type { TableColumnsType } from 'antd'
import PageHeader from '@/components/PageHeader'
import * as shareApi from '@/api/reportShare'
import { formatTime } from '@/utils'
import type { ReportShareItem, ReportShareType } from '@/types'

const TYPE_LABEL: Record<ReportShareType, string> = {
  benchmark: '评测对比',
  optimization: '步骤优化',
  task: '任务迭代',
}

const TYPE_COLOR: Record<ReportShareType, string> = {
  benchmark: 'blue',
  optimization: 'green',
  task: 'geekblue',
}

const copyText = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    message.success('链接已复制')
  } catch {
    message.error('复制失败，请手动复制')
  }
}

export default function ShareCenter() {
  const [rows, setRows] = useState<ReportShareItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await shareApi.listShares()
      setRows(d.items || [])
    } catch {
      /* 错误已统一提示 */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const revoke = async (id: number) => {
    try {
      await shareApi.revokeShare(id)
      message.success('已撤销该分享链接')
      load()
    } catch {
      /* 已统一提示 */
    }
  }

  const linkOf = (r: ReportShareItem) => `${window.location.origin}${r.url}`
  const valid = (r: ReportShareItem) => r.status === 'active'

  const columns: TableColumnsType<ReportShareItem> = [
    { title: '报告', dataIndex: 'title', ellipsis: true, render: (v, r) => (
      <Space size={6}>
        <Tag color={TYPE_COLOR[r.report_type]}>{TYPE_LABEL[r.report_type]}</Tag>
        <span>{v}</span>
      </Space>
    ) },
    { title: '访问次数', dataIndex: 'view_count', width: 90, align: 'right' },
    { title: '有效期', width: 130, render: (_, r) => (
      r.expires_at ? formatTime(r.expires_at).slice(0, 16) : <Tag>永久</Tag>
    ) },
    { title: '状态', dataIndex: 'status', width: 80, render: (v) => (
      <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '生效中' : '已撤销'}</Tag>
    ) },
    { title: '创建时间', dataIndex: 'created_at', width: 110, render: (v) => formatTime(v).slice(0, 16) },
    { title: '操作', width: 220, render: (_, r) => (
      <Space size={4}>
        <Tooltip title={valid(r) ? '复制公开访问链接' : '链接已失效'}>
          <Button size="small" icon={<CopyOutlined />} disabled={!valid(r)}
                  onClick={() => copyText(linkOf(r))}>复制链接</Button>
        </Tooltip>
        <Button size="small" type="link" icon={<LinkOutlined />}
                disabled={!valid(r)} onClick={() => window.open(linkOf(r), '_blank')}>打开</Button>
        <Popconfirm title="撤销分享" description="撤销后该链接将立即失效，确定？"
                    okText="撤销" cancelText="取消"
                    onConfirm={() => revoke(r.id)} disabled={!valid(r)}>
          <Button size="small" danger type="text" icon={<StopOutlined />} disabled={!valid(r)}>撤销</Button>
        </Popconfirm>
      </Space>
    ) },
  ]

  return (
    <div>
      <PageHeader title="报告共享" extra={<Button size="small" onClick={load}>刷新</Button>} />
      <Card size="small" title={`全部分享（${rows.length}）`}>
        <Table<ReportShareItem>
          rowKey="id" columns={columns} dataSource={rows}
          loading={loading} size="small"
          pagination={false}
          locale={{ emptyText: (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有分享记录。进入评测/优化/任务报告页点击「分享」即可生成链接" />
          ) }}
        />
      </Card>
    </div>
  )
}