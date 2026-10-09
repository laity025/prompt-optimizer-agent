// ==========================================================
// 页头：大号中文黑体标题 + 蓝色斜体英文副题 + 1px 细线
// ==========================================================
import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  /** @deprecated 装饰性英文/路由副标题已全局停用，保留以免改造既有调用点 */
  en?: string
  extra?: ReactNode
}

export default function PageHeader({ title, extra }: PageHeaderProps) {
  return (
    <div className="pe-page-head">
      <div className="pe-page-head-row">
        <h1 className="pe-page-title">
          <span className="pe-page-cn">{title}</span>
        </h1>
        {extra && <div>{extra}</div>}
      </div>
      <hr className="hairline" />
    </div>
  )
}
