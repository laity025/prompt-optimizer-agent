// ==========================================================
// 分享报告弹窗：选择有效期 → 生成免登录只读链接 → 一键复制
// 供「模型评测 / 步骤优化 / 任务迭代」报告页复用
// ==========================================================
import { useEffect, useState } from 'react'
import { Button, Input, Modal, Select, Space, message } from 'antd'
import { CopyOutlined, LinkOutlined } from '@ant-design/icons'
import * as shareApi from '@/api/reportShare'
import type { ReportShareType } from '@/types'

const EXPIRY_OPTIONS = [
  { label: '永久有效', value: 0 },
  { label: '1 小时', value: 1 },
  { label: '12 小时', value: 12 },
  { label: '24 小时', value: 24 },
  { label: '7 天', value: 168 },
  { label: '30 天', value: 720 },
]

interface Props {
  open: boolean
  onClose: () => void
  reportType: ReportShareType
  targetId: number
  /** 弹窗标题，如「分享评测报告」 */
  title: string
}

export default function ShareModal({ open, onClose, reportType, targetId, title }: Props) {
  const [expiry, setExpiry] = useState<number>(24)
  const [creating, setCreating] = useState(false)
  const [link, setLink] = useState('')
  const [copyOk, setCopyOk] = useState(false)

  // 每次打开时重置为未生成状态
  useEffect(() => {
    if (open) {
      setExpiry(24)
      setLink('')
      setCopyOk(false)
    }
  }, [open])

  const doCreate = async () => {
    setCreating(true)
    try {
      const share = await shareApi.createShare(reportType, targetId, expiry)
      setLink(`${window.location.origin}${share.url}`)
    } catch {
      /* 错误已统一提示 */
    } finally {
      setCreating(false)
    }
  }

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(link)
      setCopyOk(true)
    } catch {
      message.error('复制失败，请手动选择链接复制')
    }
  }

  return (
    <Modal title={title} open={open} onCancel={onClose} footer={null} width={520}>
      {!link ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>链接有效期</div>
            <Select style={{ width: '100%' }} value={expiry} onChange={setExpiry} options={EXPIRY_OPTIONS} />
          </div>
          <Button type="primary" block loading={creating} onClick={doCreate}>
            生成分享链接
          </Button>
          <div style={{ fontSize: 12, color: '#9ca3af' }}>
            分享后任何人打开链接即可免登录查看这份只读报告；过期或撤销后链接立即失效。
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Input
            value={link}
            readOnly
            addonBefore={<LinkOutlined />}
            onFocus={(e) => e.currentTarget.select()}
          />
          <Space>
            <Button type="primary" icon={<CopyOutlined />} onClick={copyLink}>
              {copyOk ? '已复制' : '复制链接'}
            </Button>
            <Button onClick={onClose}>完成</Button>
          </Space>
        </div>
      )}
    </Modal>
  )
}