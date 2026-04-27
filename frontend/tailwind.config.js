/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#06080f',
        surface:  '#0c1321',
        surface2: '#111b2f',
        border:   '#1a2235',
        accent:   '#c9a84c',
        blue:     '#4a9eff',
        text:     '#e6e9f4',
        muted:    '#4d5e7a',
        muted2:   '#1e2c44',
        green:    '#4dc478',
        red:      '#e63946',
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Bebas Neue"', 'sans-serif'],
      },
      keyframes: {
        pageFadeIn: {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'page-enter': 'pageFadeIn 0.25s ease-out both',
        shimmer:      'shimmer 1.5s infinite',
      },
    },
  },
  plugins: [],
}
