// ==========================================================
// 通用展示件：Panel / SectionTitle / StatCard / EmptyArt
// ==========================================================
import type { ReactNode } from 'react'
import { MascotFull } from './Mascot'

// 白色描边面板（tight 时无内边距，用于包裹表格）
export function Panel({
  children,
  tight = false,
  className = '',
  style,
}: {
  children: ReactNode
  tight?: boolean
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <section className={`pe-panel ${tight ? 'pe-panel-tight' : ''} ${className}`} style={style}>
      {children}
    </section>
  )
}

// 区块标题：黑体中文 + 操作区
export function SectionTitle({
  title,
  extra,
}: {
  title: ReactNode
  /** @deprecated 装饰性英文/路由副标题已全局停用，保留以免改造既有调用点 */
  en?: string
  extra?: ReactNode
}) {
  return (
    <div className="pe-section-title">
      <h3>{title}</h3>
      {extra && <span className="spacer" />}
      {extra}
    </div>
  )
}

// 指标卡
export function StatCard({
  label,
  value,
  unit,
  delta,
  deltaType = 'flat',
}: {
  label: ReactNode
  value: ReactNode
  unit?: string
  delta?: string
  deltaType?: 'up' | 'flat'
}) {
  return (
    <div className="pe-stat">
      <div className="lab">{label}</div>
      <div className="num tnum">
        {value}
        {unit && <small>{unit}</small>}
      </div>
      {delta && <div className={`delta ${deltaType === 'up' ? 'delta-up' : 'delta-flat'}`}>{delta}</div>}
    </div>
  )
}

// 空态插画：流体环 + 小人 + 玻璃球
export function EmptyArt({ text }: { text?: string }) {
  return (
    <div className="pe-empty">
      <div className="pe-empty-art">
        <div className="pe-ring3d pe-float-slow" />
        <MascotFull />
        <span className="pe-orb pe-orb-coral pe-float" style={{ right: 4, top: 18 }} />
        <span className="pe-orb pe-orb-teal pe-float-slow" style={{ right: 150, top: 0, width: 26, height: 26 }} />
      </div>
      {text && <div className="pe-empty-text">{text}</div>}
    </div>
  )
}
