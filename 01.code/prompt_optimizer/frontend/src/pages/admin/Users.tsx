// ==========================================================
// 管理员 · 用户管理页：角色筛选 + 角色调整 + 账号启停（自身不可禁用）
// ==========================================================
import { useCallback, useEffect, useState } from 'react'
import { Table, Select, Tag, Button, App } from 'antd'
import { getAdminUsers, updateAdminUser } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/PageHeader'
import { Panel } from '@/components/ui'
import type { UserInfo } from '@/types'
import { formatTime } from '@/utils'

const ROLE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '普通用户', value: 'user' },
  { label: '管理员', value: 'admin' },
]

export default function AdminUsers() {
  const app = App.useApp()
  const me = useAuthStore((s) => s.user)
  const [items, setItems] = useState<UserInfo[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [role, setRole] = useState('')
  const [loading, setLoading] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getAdminUsers({ page, page_size: pageSize, role: role || undefined })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      /* 错误统一提示 */
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, role])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 切换用户角色
  const updRole = async (user: UserInfo, newRole: string) => {
    if (newRole === user.role) return
    await updateAdminUser(user.id, { role: newRole })
    app.message.success('角色已更新')
    fetchData()
  }

  // 禁用 / 启用账号（自身不可操作）
  const toggleActive = (user: UserInfo) => {
    const isSelf = user.id === me?.id
    if (isSelf) {
      app.message.warning('不能对自身账号执行启停操作')
      return
    }
    const disabling = user.is_active === 1
    app.modal.confirm({
      title: disabling ? '禁用账号' : '启用账号',
      content: disabling ? `禁用后用户「${user.email}」将无法登录，历史数据保留。确定继续？` : `确定启用用户「${user.email}」吗？`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: disabling ? { danger: true } : undefined,
      onOk: async () => {
        await updateAdminUser(user.id, { is_active: disabling ? 0 : 1 })
        app.message.success(disabling ? '账号已禁用' : '账号已启用')
        fetchData()
      },
    })
  }

  const columns = [
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    { title: '姓名', dataIndex: 'full_name', key: 'full_name', render: (v: string | null) => v || '—' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 140,
      render: (v: string, user: UserInfo) => (
        <Select
          size="small"
          value={v}
          style={{ width: 110 }}
          options={[
            { label: '普通用户', value: 'user' },
            { label: '管理员', value: 'admin' },
          ]}
          onChange={(nv) => updRole(user, nv)}
        />
      ),
    },
    {
      title: '账号状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (v: number) => (v === 1 ? <Tag color="success">正常</Tag> : <Tag>已禁用</Tag>),
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: (v: string) => <span className="tnum">{formatTime(v)}</span> },
    {
      title: '操作',
      key: 'op',
      width: 110,
      render: (_: unknown, user: UserInfo) =>
        user.id === me?.id ? (
          <span style={{ color: 'var(--pe-muted-foreground)', fontSize: 12.5 }}>当前账号</span>
        ) : user.is_active === 1 ? (
          <Button type="link" danger size="small" onClick={() => toggleActive(user)}>
            禁用
          </Button>
        ) : (
          <Button type="link" size="small" onClick={() => toggleActive(user)}>
            启用
          </Button>
        ),
    },
  ]

  return (
    <div>
      <PageHeader title="用户管理" en="user management" />
      <div className="pe-toolbar">
        <div className="pe-chips">
          {ROLE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`pe-chip ${role === opt.value ? 'is-active' : ''}`}
              onClick={() => {
                setRole(opt.value)
                setPage(1)
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <span className="pe-sub-italic">/accounts</span>
      </div>
      <Panel tight>
        <Table
          rowKey="id"
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
      </Panel>
    </div>
  )
}
