/** @type {import('tailwindcss').Config} */
// TailwindCSS 配置：仅启用基础层，避免与 Ant Design 的 Preflight 冲突过多
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  corePlugins: {
    preflight: false, // 关闭 tailwind 的基础样式重置，交给 antd 统一控制
  },
  theme: {
    extend: {
      colors: {
        // 与 UIUX 设计文档（V2.0 皇家蓝）一致的品牌色板
        brand: '#0E4AC3', // 皇家蓝主色（实心块）
        brandDark: '#093A97', // 皇家蓝深一阶（hover/按下）
        brandDeeper: '#072F7C', // 皇家蓝更深一阶
        pagebg: '#E9E9EB', // 页面浅灰背景
        cardBg: '#FFFFFF',
        succ: '#16A34A',
        fail: '#F03A3E',
        warn: '#D97706',
        ink: '#0A0A0A', // 主文字近黑
        sub: '#6E6E73', // 次级文字浅灰
        line: '#D8D8DC', // 1px 细分隔线
        addBg: '#E3ECFF', // 提示词新增增亮蓝
        addInk: '#0E4AC3',
        delBg: '#FFE7E9',
        delInk: '#F03A3E',
      },
    },
  },
  plugins: [],
}