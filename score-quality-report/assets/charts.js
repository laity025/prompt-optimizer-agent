// ==========================================================
// charts.js — 得分波动与变体质量体检报告
// 一个调色板（Business Blue），三个折线图 + 变体质量表
// 所有颜色读取 :root 中的 concrete chart token
// ==========================================================
(function () {
  // 与 :root 一致的 chart palette（具体值，避免读 var()）
  var C = {
    s1: '#0969DA', s2: '#8250DF', s3: '#06B6D4', s4: '#BF3989',
    other: '#D7DEE8', accent: '#0969DA', accent2: '#8250DF',
    success: '#52C41A', warning: '#FAAD14', danger: '#FF4D4F',
    grid: 'rgba(26,35,50,0.12)', axis: '#66738A',
    label: '#66738A', tooltipBg: '#FFFFFF'
  };

  // 轮内最佳得分数据
  var DATA = {
    healthy: [
      { name: '#27 文本摘要', series: [74.84, 82.75, 80.42, 84.31] },
      { name: '#39 线上验证2', series: [67.74, 79.56] },
      { name: '#41 断点E2E', series: [44.83, 79.24, 79.34, 74.78, 78.76] }
    ],
    t37: { name: '#37 文生图文案', series: [100, 90, 20, 30, 100, 90, 100, 20, 100, 30] },
    t36: { name: '#36 金融新闻摘要', series: [90, 85, 90, 90, 85, 85, 95, null] }
  };

  var baseOpt = {
    animation: false,
    grid: { left: 46, right: 24, top: 36, bottom: 34 },
    tooltip: { trigger: 'axis', appendToBody: true, backgroundColor: C.tooltipBg },
    xAxis: {
      type: 'category', boundaryGap: false,
      axisLine: { lineStyle: { color: C.grid } },
      axisLabel: { color: C.label, fontSize: 12 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value', min: 0, max: 100,
      axisLabel: { color: C.label, fontSize: 12, formatter: '{value}' },
      splitLine: { lineStyle: { color: C.grid } }
    },
    legend: { top: 4, textStyle: { color: C.label, fontSize: 12 } }
  };

  // 健康对照（3 条 peer 系列）
  var elHealthy = document.getElementById('chart-healthy');
  if (elHealthy) {
    var chart = echarts.init(elHealthy, null, { renderer: 'svg' });
    chart.setOption(Object.assign({}, baseOpt, {
      legend: { ...baseOpt.legend, data: ['#27 文本摘要', '#39 线上验证2', '#41 断点E2E'] },
      xAxis: { ...baseOpt.xAxis, data: ['R1', 'R2', 'R3', 'R4', 'R5'] },
      series: [
        {
          name: '#27 文本摘要', type: 'line', smooth: true, symbolSize: 5,
          lineStyle: { width: 2, color: C.s1 }, itemStyle: { color: C.s1 },
          data: DATA.healthy[0].series, connectNulls: true
        },
        {
          name: '#39 线上验证2', type: 'line', smooth: true, symbolSize: 5,
          lineStyle: { width: 2, color: C.s2 }, itemStyle: { color: C.s2 },
          data: [DATA.healthy[1].series[0], DATA.healthy[1].series[1], null, null, null], connectNulls: false
        },
        {
          name: '#41 断点E2E', type: 'line', smooth: true, symbolSize: 5,
          lineStyle: { width: 2, color: C.s3 }, itemStyle: { color: C.s3 },
          data: DATA.healthy[2].series, connectNulls: true
        }
      ]
    }));
    window.addEventListener('resize', function () { chart.resize(); });
  }

  // 任务 #37：单系列振荡
  var el37 = document.getElementById('chart-t37');
  if (el37) {
    var chart37 = echarts.init(el37, null, { renderer: 'svg' });
    chart37.setOption(Object.assign({}, baseOpt, {
      xAxis: { ...baseOpt.xAxis, data: ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10'] },
      series: [{
        name: DATA.t37.name, type: 'line', smooth: true, symbolSize: 5,
        lineStyle: { width: 2, color: C.s1 }, itemStyle: { color: C.s1 },
        data: DATA.t37.series, connectNulls: true
      }]
    }));
    window.addEventListener('resize', function () { chart37.resize(); });
  }

  // 任务 #36：单系列，含空值（round8）
  var el36 = document.getElementById('chart-t36');
  if (el36) {
    var chart36 = echarts.init(el36, null, { renderer: 'svg' });
    chart36.setOption(Object.assign({}, baseOpt, {
      xAxis: { ...baseOpt.xAxis, data: ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8'] },
      series: [{
        name: DATA.t36.name, type: 'line', smooth: true, symbolSize: 5,
        lineStyle: { width: 2, color: C.s1 }, itemStyle: { color: C.s1 },
        data: DATA.t36.series, connectNulls: false
      }]
    }));
    window.addEventListener('resize', function () { chart36.resize(); });
  }

  // 变体质量表
  var Q = [
    { id: 22, name: '电商文案', v: 4, sc: 4, avg: 80.0, hi: 80.0, lo: 80.0, tags: 'rewrite / constraint', label: 'ok', note: '全部评估' },
    { id: 24, name: '任务#24(failed)', v: 2, sc: 0, avg: null, hi: null, lo: null, tags: 'rewrite 等', label: 'warn', note: '无评分' },
    { id: 25, name: '任务#25', v: 4, sc: 4, avg: 21.25, hi: 45.0, lo: 5.0, tags: 'rewrite / enhanced_structure', label: 'warn', note: '极差偏大' },
    { id: 26, name: '摘要测试', v: 4, sc: 4, avg: 30.0, hi: 50.0, lo: 5.0, tags: 'rewrite / 结构化增强', label: 'warn', note: '极差偏大' },
    { id: 27, name: '文本摘要优化示例', v: 8, sc: 8, avg: 76.38, hi: 84.31, lo: 58.7, tags: 'rewrite / 结构化', label: 'ok', note: '全部评估' },
    { id: 33, name: '金融新闻摘要', v: 4, sc: 4, avg: 83.33, hi: 86.67, lo: 80.0, tags: 'rewrite / 结构化步骤', label: 'ok', note: '全部评估' },
    { id: 34, name: '金融新闻摘要', v: 4, sc: 4, avg: 82.5, hi: 90.0, lo: 80.0, tags: 'rewrite', label: 'ok', note: '全部评估' },
    { id: 35, name: '金融新闻摘要', v: 4, sc: 4, avg: 85.0, hi: 90.0, lo: 80.0, tags: 'fewshot / step_by_step', label: 'ok', note: '全部评估' },
    { id: 36, name: '金融新闻摘要', v: 32, sc: 28, avg: 82.5, hi: 95.0, lo: 70.0, tags: 'rewrite(15) 等', label: 'danger', note: '4 未评分' },
    { id: 37, name: '文生图文案优化', v: 28, sc: 28, avg: 55.71, hi: 100.0, lo: 20.0, tags: 'baseline / failure_inject', label: 'danger', note: '评估口径振荡' },
    { id: 38, name: '线上验证_b24238', v: 4, sc: 4, avg: 58.03, hi: 70.28, lo: 45.11, tags: 'baseline / rewrite', label: 'ok', note: '全部评估' },
    { id: 39, name: '线上验证2_50773f', v: 4, sc: 4, avg: 59.97, hi: 79.56, lo: 45.34, tags: 'baseline / rewrite', label: 'ok', note: '全部评估' },
    { id: 40, name: '断点验证_69ddd5', v: 4, sc: 4, avg: 57.17, hi: 72.34, lo: 44.54, tags: 'baseline / rewrite', label: 'ok', note: '全部评估' },
    { id: 41, name: '断点E2E_953350', v: 12, sc: 12, avg: 56.19, hi: 79.34, lo: 24.02, tags: 'baseline / rewrite', label: 'ok', note: '全部评估' }
  ];
  var tagMap = {
    ok: '<span class="tag tag--ok">健康</span>',
    warn: '<span class="tag tag--warning">关注</span>',
    danger: '<span class="tag tag--danger">异常</span>'
  };
  var tb = document.getElementById('qual-body');
  if (tb) {
    var html = '';
    Q.forEach(function (q) {
      html += '<tr>'
        + '<td>#' + q.id + ' ' + q.name + '</td>'
        + '<td class="num">' + q.v + '</td>'
        + '<td class="num">' + q.sc + '</td>'
        + '<td class="num">' + (q.avg == null ? '—' : q.avg.toFixed(2)) + '</td>'
        + '<td class="num">' + (q.hi == null ? '—' : q.hi) + '</td>'
        + '<td class="num">' + (q.lo == null ? '—' : q.lo) + '</td>'
        + '<td>' + q.tags + '</td>'
        + '<td>' + tagMap[q.label] + ' ' + q.note + '</td>'
        + '</tr>';
    });
    tb.innerHTML = html;
  }
})();