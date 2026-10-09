// ==========================================================
// 黑色小人 IP：全身 / 头部 / 完成态 三个内联 SVG 版本
// ==========================================================

interface MascotProps {
  className?: string
  style?: React.CSSProperties
}

// 全身：登录主视觉 / 空态
export function MascotFull({ className, style }: MascotProps) {
  return (
    <svg className={`pe-mascot ${className || ''}`} style={style} viewBox="0 0 200 240" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M62 52 Q88 30 114 52 T166 50" stroke="#79A2FF" strokeWidth="4.5" strokeLinecap="round" />
      <path d="M70 40 Q96 20 122 42" stroke="#0E4AC3" strokeWidth="3.5" strokeLinecap="round" />
      <path
        fill="#0A0A0A"
        d="M108 14 C70 12 40 40 38 78 C37 96 44 110 52 120 C47 112 52 104 57 102 C53 114 60 122 67 124 C64 116 70 108 75 107 C73 120 82 129 91 128 C89 118 96 110 101 108 C101 121 112 128 120 123 C116 114 123 108 128 107 C131 119 141 123 146 115 C140 108 146 96 150 88 C161 104 163 128 154 144 C148 155 138 160 128 158 L80 158 C66 156 56 146 55 132 C42 122 34 104 36 82 C39 42 70 16 108 14 Z"
      />
      <path
        fill="#FFFFFF"
        stroke="#0A0A0A"
        strokeWidth="3.5"
        strokeLinejoin="round"
        d="M103 74 C95 88 92 100 85 110 L76 120 C83 122 86 124 84 129 L77 134 C84 136 90 139 92 146 C98 160 116 164 130 156 C144 147 147 126 139 106 C132 88 119 75 103 74 Z"
      />
      <ellipse cx="105" cy="101" rx="3.4" ry="4.2" fill="#0A0A0A" transform="rotate(-12 105 101)" />
      <path d="M99 92 Q105 89 111 91" stroke="#0A0A0A" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="112" cy="126" r="5.2" fill="#FD550C" />
      <path d="M86 136 Q90 139 94 136" stroke="#0A0A0A" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <circle cx="132" cy="120" r="6" fill="#FFFFFF" stroke="#0A0A0A" strokeWidth="3" />
      <path fill="#0A0A0A" d="M72 162 C58 172 50 196 53 232 L150 232 C153 196 145 172 131 162 C121 168 82 168 72 162 Z" />
      <path d="M76 196 Q102 186 128 196" stroke="#2E63D6" strokeWidth="4" strokeLinecap="round" />
      <circle cx="102" cy="214" r="3.4" fill="#79A2FF" />
    </svg>
  )
}

// 仅头部：登录卡片 / 迷你引导
export function MascotHead({ className, style }: MascotProps) {
  return (
    <svg className={`pe-mascot ${className || ''}`} style={style} viewBox="0 0 170 165" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M62 52 Q88 30 114 52 T160 48" stroke="#79A2FF" strokeWidth="4.5" strokeLinecap="round" />
      <path
        fill="#0A0A0A"
        d="M108 14 C70 12 40 40 38 78 C37 96 44 110 52 120 C47 112 52 104 57 102 C53 114 60 122 67 124 C64 116 70 108 75 107 C73 120 82 129 91 128 C89 118 96 110 101 108 C101 121 112 128 120 123 C116 114 123 108 128 107 C131 119 141 123 146 115 C140 108 146 96 150 88 C160 102 161 124 153 138 C146 151 132 157 118 154 L82 154 C66 152 55 140 55 124 C42 114 35 96 37 78 C40 42 70 16 108 14 Z"
      />
      <path
        fill="#FFFFFF"
        stroke="#0A0A0A"
        strokeWidth="3.5"
        strokeLinejoin="round"
        d="M103 74 C95 88 92 100 85 110 L76 120 C83 122 86 124 84 129 L77 134 C84 136 90 139 92 146 C98 160 116 164 130 156 C144 147 147 126 139 106 C132 88 119 75 103 74 Z"
      />
      <ellipse cx="105" cy="101" rx="3.4" ry="4.2" fill="#0A0A0A" transform="rotate(-12 105 101)" />
      <path d="M99 92 Q105 89 111 91" stroke="#0A0A0A" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="112" cy="126" r="5.2" fill="#FD550C" />
      <path d="M86 136 Q90 139 94 136" stroke="#0A0A0A" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <circle cx="132" cy="120" r="6" fill="#FFFFFF" stroke="#0A0A0A" strokeWidth="3" />
    </svg>
  )
}

// 完成态：举蓝球（报告 / 完成插画）
export function MascotDone({ className, style }: MascotProps) {
  return (
    <svg className={`pe-mascot ${className || ''}`} style={style} viewBox="0 0 220 240" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M62 52 Q88 30 114 52 T166 50" stroke="#79A2FF" strokeWidth="4.5" strokeLinecap="round" />
      <path
        fill="#0A0A0A"
        d="M108 14 C70 12 40 40 38 78 C37 96 44 110 52 120 C47 112 52 104 57 102 C53 114 60 122 67 124 C64 116 70 108 75 107 C73 120 82 129 91 128 C89 118 96 110 101 108 C101 121 112 128 120 123 C116 114 123 108 128 107 C131 119 141 123 146 115 C140 108 146 96 150 88 C161 104 163 128 154 144 C148 155 138 160 128 158 L80 158 C66 156 56 146 55 132 C42 122 34 104 36 82 C39 42 70 16 108 14 Z"
      />
      <path
        fill="#FFFFFF"
        stroke="#0A0A0A"
        strokeWidth="3.5"
        strokeLinejoin="round"
        d="M103 74 C95 88 92 100 85 110 L76 120 C83 122 86 124 84 129 L77 134 C84 136 90 139 92 146 C98 160 116 164 130 156 C144 147 147 126 139 106 C132 88 119 75 103 74 Z"
      />
      <ellipse cx="105" cy="101" rx="3.4" ry="4.2" fill="#0A0A0A" transform="rotate(-12 105 101)" />
      <path d="M99 92 Q105 89 111 91" stroke="#0A0A0A" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="112" cy="126" r="5.2" fill="#FD550C" />
      <path d="M85 135 Q90 140 95 135" stroke="#0A0A0A" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <circle cx="132" cy="120" r="6" fill="#FFFFFF" stroke="#0A0A0A" strokeWidth="3" />
      <path d="M140 168 C158 156 168 138 176 118" stroke="#0A0A0A" strokeWidth="13" strokeLinecap="round" fill="none" />
      <circle cx="180" cy="104" r="20" fill="url(#armOrb)" />
      <circle cx="173" cy="96" r="7" fill="#fff" opacity="0.75" />
      <defs>
        <radialGradient id="armOrb" cx="0.32" cy="0.28" r="0.8">
          <stop offset="0%" stopColor="#A9C2FF" />
          <stop offset="48%" stopColor="#2E63D6" />
          <stop offset="100%" stopColor="#0045BD" />
        </radialGradient>
      </defs>
      <path fill="#0A0A0A" d="M72 162 C58 172 50 196 53 232 L150 232 C153 196 145 172 131 162 C121 168 82 168 72 162 Z" />
      <path d="M76 196 Q102 186 128 196" stroke="#2E63D6" strokeWidth="4" strokeLinecap="round" fill="none" />
    </svg>
  )
}
