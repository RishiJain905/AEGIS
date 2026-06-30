const preset = {
  theme: {
    extend: {
      colors: {
        surface: {
          base: 'var(--aegis-surface-base)',
          elevated: 'var(--aegis-surface-elevated)',
          panel: 'var(--aegis-surface-panel)',
          rail: 'var(--aegis-surface-rail)',
          overlay: 'var(--aegis-surface-overlay)',
        },
        text: {
          primary: 'var(--aegis-text-primary)',
          secondary: 'var(--aegis-text-secondary)',
          muted: 'var(--aegis-text-muted)',
        },
        focus: {
          ring: 'var(--aegis-focus-ring)',
        },
        risk: {
          low: 'var(--aegis-risk-low)',
          medium: 'var(--aegis-risk-medium)',
          high: 'var(--aegis-risk-high)',
          critical: 'var(--aegis-risk-critical)',
        },
      },
      fontFamily: {
        sans: ['var(--aegis-font-sans)'],
        mono: ['var(--aegis-font-mono)'],
      },
      borderRadius: {
        sm: 'var(--aegis-radius-sm)',
        md: 'var(--aegis-radius-md)',
        lg: 'var(--aegis-radius-lg)',
        xl: 'var(--aegis-radius-xl)',
      },
      boxShadow: {
        panel: 'var(--aegis-shadow-panel)',
        dialog: 'var(--aegis-shadow-dialog)',
        rail: 'var(--aegis-shadow-rail)',
      },
      screens: {
        md: '1024px',
        lg: '1280px',
        xl: '1536px',
      },
    },
  },
};

export default preset;
