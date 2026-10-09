// ==========================================================
// 模型下拉选项统一渲染：默认模型追加“默认”绿色标签，方便用户一眼识别
// ==========================================================
import { Tag } from 'antd'
import type { ReactNode } from 'react'
import type { ModelInfo } from '@/types'

export function modelOptionLabel(m: ModelInfo, showId = false): ReactNode {
  return (
    <span>
      {m.name || m.id}
      {showId && <span style={{ color: '#8a94a6' }}>（{m.id}）</span>}
      {m.is_default ? (
        <Tag color="green" style={{ marginInlineStart: 6, fontSize: 12, lineHeight: '16px' }}>默认</Tag>
      ) : null}
    </span>
  )
}