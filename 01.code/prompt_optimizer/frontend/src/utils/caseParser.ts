// ==========================================================
// 用例文件解析器：将 JSON/CSV 文本内容解析为用例行数组
// 纯函数，便于单元测试与在页面前端复用
//   - JSON：顶层数组，字段 input_text/reference_output/keywords/run_test
//   - CSV ：首行表头 input_text,reference_output,keywords,run_test
//           其中 keywords 用竖线 | 分隔
// ==========================================================

export interface CaseRow {
  input_text: string
  reference_output?: string
  keywords?: string[]
  run_test?: string
}

export interface ParseResult {
  rows: Partial<CaseRow>[]
  errors: string[]
}

export function parseCaseContent(text: string, filename: string): ParseResult {
  const errors: string[] = []
  let rows: Partial<CaseRow>[] = []
  try {
    if (filename.toLowerCase().endsWith('.json')) {
      const arr = JSON.parse(text)
      if (!Array.isArray(arr)) throw new Error('JSON 顶层应为数组')
      rows = (arr as Record<string, unknown>[]).map((item) => ({
        input_text: String(item.input_text ?? ''),
        reference_output: item.reference_output != null ? String(item.reference_output) : undefined,
        keywords: Array.isArray(item.keywords) ? item.keywords.map(String) : undefined,
        run_test: item.run_test != null ? String(item.run_test) : undefined,
      }))
    } else {
      // CSV：支持首行表头 input_text/reference_output/keywords/run_test
      const lines = text.split(/\r?\n/)
      if (lines.length === 0) throw new Error('空文件')
      const header = lines[0].split(',').map((h) => h.trim())
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim()
        if (!line) continue
        const cols = line.split(',').map((c) => c.trim())
        const row: Partial<CaseRow> = {}
        header.forEach((h, idx) => {
          const val = cols[idx]
          if (val === undefined || val === '') return
          if (h === 'input_text') row.input_text = val
          else if (h === 'reference_output') row.reference_output = val
          else if (h === 'keywords') row.keywords = val.split('|').map((s) => s.trim())
          else if (h === 'run_test') row.run_test = val
        })
        rows.push(row)
      }
    }
    // 校验必填 input_text
    rows = rows.filter((r, idx) => {
      if (!r.input_text) {
        errors.push(`第 ${idx + 1} 条缺少 input_text`)
        return false
      }
      return true
    })
    return { rows, errors }
  } catch (e) {
    throw new Error('文件解析失败：' + (e as Error).message)
  }
}