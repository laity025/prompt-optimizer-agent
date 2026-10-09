// ==========================================================
// 登录 / 注册页：左 3D 主视觉（流体环+小人+巨型字）+ 右表单卡
// ==========================================================
import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { App } from 'antd'
import { login, register } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { MascotFull, MascotHead } from '@/components/Mascot'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const setAuth = useAuthStore((s) => s.setAuth)
  const { message } = App.useApp()

  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  const clearError = () => setErrorMsg('')

  // 登录：登录态写入 HttpOnly cookie（后端），前端仅保存用户信息并跳转
  const handleLogin = async () => {
    setLoading(true)
    try {
      const data = await login({ email: email.trim(), password })
      setAuth(data.user)
      message.success('登录成功')
      const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname
      navigate(from || '/tasks', { replace: true })
    } catch (e) {
      // 透传后端文案：密码错误、账号禁用、登录锁定（"尝试次数过多"）等提示都能正确显示
      setErrorMsg((e as Error).message || '邮箱或密码错误，请重试。')
    } finally {
      setLoading(false)
    }
  }

  // 注册：成功后自动登录
  const handleRegister = async () => {
    setLoading(true)
    try {
      await register({ email: email.trim(), password, full_name: fullName.trim() || undefined })
      const data = await login({ email: email.trim(), password })
      setAuth(data.user)
      message.success('注册成功，已自动登录')
      navigate('/tasks', { replace: true })
    } catch (e) {
      // 透传后端文案（如"该邮箱已被注册"）
      setErrorMsg((e as Error).message || '注册失败，请检查邮箱是否已被注册。')
    } finally {
      setLoading(false)
    }
  }

  // 前端校验 + 提交
  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setErrorMsg('邮箱格式不正确，请检查后重试。')
      return
    }
    if (password.length < 6) {
      setErrorMsg('密码至少 6 位。')
      return
    }
    if (mode === 'register' && password !== confirm) {
      setErrorMsg('两次输入的密码不一致。')
      return
    }
    if (mode === 'login') handleLogin()
    else handleRegister()
  }

  return (
    <main className="lg-wrap">
      {/* 左栏：品牌主视觉 */}
      <section className="lg-hero">
        <div className="pe-blob lg-blob-1" />
        <div className="pe-blob lg-blob-2" />

        <div className="lg-hero-top">
          <span className="lg-hero-mark" />
          <span className="en">PROMPT&nbsp;EVOLVER&nbsp;·&nbsp;V2.0</span>
        </div>

        <div className="lg-art">
          <div className="pe-ring3d lg-ring pe-float-slow" />
          <span className="pe-orb pe-orb-coral lg-orb lg-orb-1 pe-float" />
          <span className="pe-orb pe-orb-teal lg-orb lg-orb-2 pe-float-slow" />
          <span className="pe-orb pe-orb-purple lg-orb lg-orb-3 pe-float" />
          <span className="pe-orb pe-orb-pink lg-orb lg-orb-4 pe-float-slow" />
          <MascotFull className="lg-mascot" />
        </div>

        <div className="lg-word">
          <div className="pe-en">
            PROMPT
            <br />
            EVOLVER
          </div>
          <hr className="hairline" />
          <div className="lg-cn">提示词自动迭代优化智能体</div>
          <div className="lg-tagline">
            把上千次试错压缩成一次迭代 &nbsp;·&nbsp; <b>Auto Prompt Optimization</b>
          </div>
        </div>
      </section>

      {/* 右栏：登录 / 注册卡片 */}
      <section className="lg-panel">
        <div className="lg-card">
          <span className="lg-deco-line" />
          <div className="lg-card-head">
            <MascotHead />
            <div className="lg-card-title">
              <span className="pe-en">{mode === 'login' ? 'Login' : 'Register'}</span>
              <span className="pe-slash">／</span>
              <span className="cn">{mode === 'login' ? '登录' : '注册'}</span>
            </div>
          </div>
          <div className="pe-sub-italic">
            {mode === 'login' ? '/sign in to evolve your prompts' : '/create your evolver account'}
          </div>

          <div className="lg-tabs">
            <button type="button" className={`lg-tab ${mode === 'login' ? 'is-active' : ''}`} onClick={() => { setMode('login'); clearError() }}>
              登录
            </button>
            <button type="button" className={`lg-tab ${mode === 'register' ? 'is-active' : ''}`} onClick={() => { setMode('register'); clearError() }}>
              注册
            </button>
          </div>

          <div className={`lg-error ${errorMsg ? 'is-show' : ''}`}>
            <span>⚠</span>
            <span>{errorMsg}</span>
          </div>

          <form onSubmit={onSubmit} noValidate>
            {mode === 'register' && (
              <div className="lg-field">
                <label className="pe-label">姓名</label>
                <input
                  className="pe-input"
                  type="text"
                  placeholder="选填，将显示在侧边栏"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
            )}
            <div className="lg-field">
              <label className="pe-label">
                邮箱<span className="req">*</span>
              </label>
              <input
                className="pe-input"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => { setEmail(e.target.value); clearError() }}
                autoComplete="email"
              />
            </div>
            <div className="lg-field">
              <label className="pe-label">
                密码<span className="req">*</span>
              </label>
              <input
                className="pe-input"
                type="password"
                placeholder={mode === 'register' ? '至少 6 位' : '请输入密码'}
                value={password}
                onChange={(e) => { setPassword(e.target.value); clearError() }}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>
            {mode === 'register' && (
              <div className="lg-field">
                <label className="pe-label">
                  确认密码<span className="req">*</span>
                </label>
                <input
                  className="pe-input"
                  type="password"
                  placeholder="请再次输入密码"
                  value={confirm}
                  onChange={(e) => { setConfirm(e.target.value); clearError() }}
                  autoComplete="new-password"
                />
              </div>
            )}
            <button type="submit" className="pe-btn pe-btn-black lg-submit" disabled={loading}>
              {loading ? (
                <>
                  {mode === 'login' ? '登录中' : '注册中'}
                  <span className="pe-dots">
                    <i />
                    <i />
                    <i />
                  </span>
                </>
              ) : mode === 'login' ? (
                '登录 · Enter'
              ) : (
                '注册并自动登录'
              )}
            </button>
          </form>

          <div className="lg-foot">
            {mode === 'login' ? (
              <>
                还没有账号？<a onClick={() => { setMode('register'); clearError() }}>立即注册</a>
              </>
            ) : (
              <>
                已有账号？<a onClick={() => { setMode('login'); clearError() }}>直接登录</a>
              </>
            )}
            <br />
            登录即代表同意《迭代服务条款》与数据仅用于优化任务的约定
          </div>
        </div>
      </section>
    </main>
  )
}
