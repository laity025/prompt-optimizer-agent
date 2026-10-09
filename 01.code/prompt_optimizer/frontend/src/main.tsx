// ==========================================================
// 应用入口：AntD 国际化、全局样式、路由挂载
// ==========================================================
import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import App from './App'
import 'antd/dist/reset.css'
import './index.css'
import './styles/pe.css'

// 设置 dayjs 中文
dayjs.locale('zh-cn')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* AntD 中文化 + 皇家蓝作品集主题 */}
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#0E4AC3',
          colorSuccess: '#12A150',
          colorError: '#F03A3E',
          colorWarning: '#FD550C',
          colorInfo: '#017BA9',
          colorBgLayout: '#E9E9EB',
          colorText: '#0A0A0A',
          colorTextSecondary: '#6E6E76',
          colorBorder: '#D8D8DC',
          colorBorderSecondary: '#E6E6E9',
          borderRadius: 10,
          fontSize: 14,
          fontFamily:
            "'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC', 'Helvetica Neue', Arial, sans-serif",
        },
        components: {
          Button: { fontWeight: 700, primaryShadow: 'none', defaultShadow: 'none', dangerShadow: 'none' },
          Card: { borderRadiusLG: 12 },
          Modal: { borderRadiusLG: 12 },
          Table: { headerBg: '#F2F2F4', headerColor: '#0A0A0A', headerSplitColor: 'transparent' },
        },
      }}
    >
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
