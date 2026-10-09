// ==========================================================
// 得分曲线组件：基于 ECharts 折线图，标注目标分数水平线
// ==========================================================
import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import type { ScorePoint } from '@/types'

interface Props {
  rounds: ScorePoint[]
  targetScore?: number | null
  height?: number
}

// 渲染得分曲线折线图（主色 #0E4AC3 皇家蓝，目标线为黑色虚线，空态居中提示）
export default function ScoreChart({ rounds, targetScore, height = 320 }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    chartRef.current = echarts.init(ref.current)
    return () => {
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    const data = [...rounds].sort((a, b) => a.round - b.round)

    // 单个 series：仅在存在目标分时附加水平虚线
    const series: echarts.SeriesOption = {
      name: '最优得分',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { color: '#0E4AC3', width: 3 },
      itemStyle: { color: '#0E4AC3' },
      data: data.map((d) => d.best_score),
    }
    if (targetScore != null) {
      ;(series as Record<string, unknown>).markLine = {
        silent: true,
        symbol: 'none',
        label: { formatter: '目标分 {c}', color: '#6E6E73', position: 'insideEndTop' },
        lineStyle: { color: '#0A0A0A', type: 'dashed' },
        data: [{ yAxis: targetScore }],
      }
    }

    const option: echarts.EChartsOption = {
      tooltip: { trigger: 'axis' },
      grid: { left: 48, right: 24, top: 32, bottom: 32 },
      xAxis: { type: 'category', name: '轮次', data: data.map((d) => `第${d.round}轮`) },
      yAxis: { type: 'value', name: '综合得分', min: 0, max: 100 },
      series: [series],
      // 空态：无数据时居中提示
      graphic:
        data.length === 0
          ? [
              {
                type: 'text',
                left: 'center',
                top: 'middle',
                style: { text: '暂无数据', fill: '#6E6E73', fontSize: 14 },
              },
            ]
          : [],
    }
    chart.setOption(option, true)
  }, [rounds, targetScore])

  return <div ref={ref} style={{ width: '100%', height }} />
}