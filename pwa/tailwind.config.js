/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          PRIMARY: '#0d0d0d',
          SECONDARY: '#161616',
          TERTIARY: '#1f1f1f',
          CARD: '#1a1a1a',
          HOVER: '#262626',
        },
        fg: {
          PRIMARY: '#fafafa',
          SECONDARY: '#d4d4d4',
          MUTED: '#a3a3a3',
          DISABLED: '#737373',
        },
        accent: {
          DEFAULT: '#00d4aa',
          HOVER: '#00e8bb',
          LIGHT: '#00d4aa22',
          DARK: '#00a388',
        },
        danger: {
          DEFAULT: '#ff4d4f',
          HOVER: '#ff7875',
          LIGHT: '#ff4d4f22',
        },
        warning: {
          DEFAULT: '#ffa726',
          HOVER: '#ffb74d',
          LIGHT: '#ffa72622',
        },
        border: {
          DEFAULT: '#333333',
          LIGHT: '#404040',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      spacing: {
        'safe-top': 'env(safe-area-inset-top)',
        'safe-bottom': 'env(safe-area-inset-bottom)',
        'safe-left': 'env(safe-area-inset-left)',
        'safe-right': 'env(safe-area-inset-right)',
      },
      animation: {
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'shimmer': 'shimmer 1.5s infinite',
        'pulse-soft': 'pulseSoft 2s infinite',
      },
      keyframes: {
        slideUp: { '0%': { transform: 'translateY(100%)' }, '100%': { transform: 'translateY(0)' } },
        slideDown: { '0%': { transform: 'translateY(-100%)' }, '100%': { transform: 'translateY(0)' } },
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        scaleIn: { '0%': { transform: 'scale(0.95)', opacity: '0' }, '100%': { transform: 'scale(1)', opacity: '1' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        pulseSoft: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0.6' } },
      },
      boxShadow: {
        'glow': '0 0 20px rgba(0, 212, 170, 0.15)',
        'glow-lg': '0 0 40px rgba(0, 212, 170, 0.2)',
        'inner-glow': 'inset 0 0 20px rgba(0, 212, 170, 0.1)',
      },
    },
  },
  plugins: [],
}
