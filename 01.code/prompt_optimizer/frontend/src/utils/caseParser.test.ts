// ==========================================================
// 单元测试：用例文件解析器 parseCaseContent（JSON/CSV）
// ==========================================================
import { describe, it, expect } from 'vitest'
import { parseCaseContent } from '@/utils/caseParser'

describe('parseCaseContent (JSON)', () => {
  it('解析顶层 JSON 数组', () => {
    const { rows, errors } = parseCaseContent(
      JSON.stringify([{ input_text: 'a', reference_output: 'b', keywords: ['k1', 'k2'] }]),
      'c.json'
    )
    expect(errors).toHaveLength(0)
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ input_text: 'a', reference_output: 'b', keywords: ['k1', 'k2'] })
  })

  it('非法 JSON 报错', () => {
    expect(() => parseCaseContent('{not json', 'c.json')).toThrow(/解析失败/)
  })

  it('顶层非数组报错', () => {
    expect(() => parseCaseContent('{"a":1}', 'c.json')).toThrow(/顶层应为数组/)
  })

  it('缺 input_text 的行被剔除并记录错误', () => {
    const { rows, errors } = parseCaseContent(
      JSON.stringify([{ input_text: 'ok' }, { reference_output: 'no input' }]),
      'c.json'
    )
    expect(rows).toHaveLength(1)
    expect(errors).toHaveLength(1)
  })
})

describe('parseCaseContent (CSV)', () => {
  const csv = [
    'input_text,reference_output,keywords,run_test',
    '今天很好,今天不错,今天|不错,',
    ',缺少输入,今天,',
  ].join('\n')

  it('按表头解析并拆分关键词(竖线)', () => {
    const { rows, errors } = parseCaseContent(csv, 'c.csv')
    expect(rows).toHaveLength(1)
    expect(rows[0].input_text).toBe('今天很好')
    expect(rows[0].keywords).toEqual(['今天', '不错'])
    expect(errors).toHaveLength(1) // 第二行缺 input_text
  })

  it('空行被跳过', () => {
    const { rows } = parseCaseContent('input_text\n\na\n\nb\n', 'c.csv')
    expect(rows).toHaveLength(2)
  })

  it('大小写不敏感的文件名', () => {
    const { rows } = parseCaseContent(JSON.stringify([{ input_text: 'x' }]), 'CASE.JSON')
    expect(rows).toHaveLength(1)
  })
})