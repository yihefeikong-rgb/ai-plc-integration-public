/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // 引用 src/styles/tokens.css 中定义的 CSS 变量，保持单一真相
        ide: {
          bg: 'var(--color-bg-base)',
          sidebar: 'var(--color-bg-sidebar)',
          panel: 'var(--color-bg-panel)',
          border: 'var(--color-border-default)',
          hover: 'var(--color-bg-hover)',
          active: 'var(--color-bg-active)',
          input: 'var(--color-bg-input)',
          elevated: 'var(--color-bg-elevated)',
        },
        accent: {
          DEFAULT: 'var(--color-accent)',
          hover: 'var(--color-accent-hover)',
          dim: 'var(--color-accent-dim)',
        },
        text: {
          primary: 'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
          dim: 'var(--color-text-dim)',
          bright: 'var(--color-text-bright)',
        },
        status: {
          ok: 'var(--color-status-ok)',
          warn: 'var(--color-status-warn)',
          error: 'var(--color-status-error)',
          info: 'var(--color-status-info)',
          danger: 'var(--color-status-danger)',
          neutral: 'var(--color-status-neutral)',
          unknown: 'var(--color-status-unknown)',
          offline: 'var(--color-status-offline)',
          connecting: 'var(--color-status-connecting)',
          connected: 'var(--color-status-connected)',
          running: 'var(--color-status-running)',
          paused: 'var(--color-status-paused)',
          readonly: 'var(--color-status-readonly)',
          disabled: 'var(--color-status-disabled)',
          ai: 'var(--color-status-ai)',
        },
        // 兼容旧 surface 类名（PromptTemplateModal/CodeTemplateModal/LadderTemplateModal 使用）
        surface: {
          DEFAULT: 'var(--color-bg-elevated)',
          alt: 'var(--color-bg-sidebar)',
          border: 'var(--color-border-default)',
          hover: 'var(--color-bg-hover)',
        },
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        DEFAULT: 'var(--radius-md)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
      fontFamily: {
        mono: ['var(--font-mono)'],
        sans: ['var(--font-sans)'],
      },
      fontSize: {
        '2xs': 'var(--text-2xs)',
        xs: 'var(--text-xs)',
        sm: 'var(--text-sm)',
        base: 'var(--text-base)',
      },
      spacing: {
        1: 'var(--space-1)',
        2: 'var(--space-2)',
        3: 'var(--space-3)',
        4: 'var(--space-4)',
        5: 'var(--space-5)',
        6: 'var(--space-6)',
        8: 'var(--space-8)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
      },
      transitionDuration: {
        fast: 'var(--duration-fast)',
        normal: 'var(--duration-normal)',
        slow: 'var(--duration-slow)',
      },
      zIndex: {
        dropdown: 'var(--z-dropdown)',
        modal: 'var(--z-modal)',
        tooltip: 'var(--z-tooltip)',
      },
    },
  },
  plugins: [],
}
