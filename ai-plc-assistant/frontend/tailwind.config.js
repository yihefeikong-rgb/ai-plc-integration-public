/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ide: {
          bg: '#1E1E1E',
          sidebar: '#252526',
          panel: '#181818',
          border: '#333333',
          hover: '#2A2D2E',
          active: '#37373D',
          input: '#3C3C3C',
        },
        accent: {
          DEFAULT: '#007ACC',
          hover: '#1A8AD4',
          dim: '#264F78',
        },
        text: {
          primary: '#CCCCCC',
          secondary: '#9D9D9D',
          dim: '#6A6A6A',
          bright: '#E8E8E8',
        },
        status: {
          ok: '#4EC9B0',
          warn: '#CCA700',
          error: '#F14C4C',
          info: '#75BEFF',
        },
      },
      borderRadius: {
        sm: '4px',
        DEFAULT: '6px',
        md: '6px',
      },
      fontFamily: {
        mono: ['Consolas', 'Menlo', 'monospace'],
        sans: ['Segoe UI', 'Inter', 'sans-serif'],
      },
      fontSize: {
        '2xs': '11px',
      },
    },
  },
  plugins: [],
}
