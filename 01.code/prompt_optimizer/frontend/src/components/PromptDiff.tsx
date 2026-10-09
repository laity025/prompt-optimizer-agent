// ==========================================================
// 提示词差异对比组件：LCS 行级 diff，新增=增亮蓝、删除=淡红删除线（V2.0 皇家蓝）
// ==========================================================

interface DiffLine {
  op: 'keep' | 'add' | 'del'
  text: string
}

// 基于最长公共子序列(LCS)计算两段文本的行级差异标记
function diffLines(oldText: string, newText: string): { oldLines: DiffLine[]; newLines: DiffLine[] } {
  const oldLines = (oldText || '').split('\n')
  const newLines = (newText || '').split('\n')
  const m = oldLines.length
  const n = newLines.length

  // dp[i][j] 表示 old[0..i) 与 new[0..j) 的 LCS 长度
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (oldLines[i] === newLines[j]) dp[i][j] = dp[i + 1][j + 1] + 1
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  // 回溯生成行标记
  const oldMarked: DiffLine[] = []
  const newMarked: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (oldLines[i] === newLines[j]) {
      oldMarked.push({ op: 'keep', text: oldLines[i] })
      newMarked.push({ op: 'keep', text: newLines[j] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      oldMarked.push({ op: 'del', text: oldLines[i] })
      i++
    } else {
      newMarked.push({ op: 'add', text: newLines[j] })
      j++
    }
  }
  while (i < m) {
    oldMarked.push({ op: 'del', text: oldLines[i] })
    i++
  }
  while (j < n) {
    newMarked.push({ op: 'add', text: newLines[j] })
    j++
  }
  return { oldLines: oldMarked, newLines: newMarked }
}

// 将 diff 结果渲染为带高亮样式的多行块
function renderBlock(lines: DiffLine[]) {
  return (
    <pre className="prompt-box m-0 rounded p-3 text-sm" style={{ background: '#FFFFFF', border: '1px solid #D8D8DC' }}>
      {lines.map((line, idx) => {
        if (line.op === 'add') {
          return (
            <div key={idx} style={{ background: '#E3ECFF', color: '#0E4AC3' }}>
              + {line.text || ' '}
            </div>
          )
        }
        if (line.op === 'del') {
          return (
            <div key={idx} style={{ background: '#FFE7E9', color: '#F03A3E', textDecoration: 'line-through' }}>
              - {line.text || ' '}
            </div>
          )
        }
        return <div key={idx}>{line.text || ' '}</div>
      })}
    </pre>
  )
}

interface Props {
  oldText?: string | null
  newText?: string | null
  oldLabel?: string
  newLabel?: string
}

// 双栏差异对比：左旧右新，各自高亮
export default function PromptDiff({ oldText, newText, oldLabel = '初始提示词', newLabel = '当前最优' }: Props) {
  const { oldLines, newLines } = diffLines(oldText || '', newText || '')
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div>
        <div className="mb-1 text-sm font-semibold text-sub">{oldLabel}</div>
        {renderBlock(oldLines)}
      </div>
      <div>
        <div className="mb-1 text-sm font-semibold text-sub">{newLabel}</div>
        {renderBlock(newLines)}
      </div>
    </div>
  )
}