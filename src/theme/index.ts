export const colors = {
  background: '#0B0E1A',
  surface: '#151A2E',
  surfaceAlt: '#1E2540',
  primary: '#6C8CFF',
  primaryDark: '#4A6BE0',
  accent: '#FF9EC4',
  text: '#F4F6FF',
  textMuted: '#A7AECB',
  textFaint: '#6B7299',
  border: '#2A3155',
  success: '#4ADE80',
  warning: '#FBBF24',
  danger: '#F87171',
  good: '#4ADE80',
  mild: '#A3E635',
  moderate: '#FBBF24',
  significant: '#F87171',
};

export const severityColor: Record<string, string> = {
  minimal: colors.good,
  mild: colors.mild,
  moderate: colors.moderate,
  significant: colors.significant,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const radius = {
  sm: 8,
  md: 14,
  lg: 22,
  pill: 999,
};

export const typography = {
  title: { fontSize: 28, fontWeight: '700' as const },
  heading: { fontSize: 20, fontWeight: '700' as const },
  subheading: { fontSize: 16, fontWeight: '600' as const },
  body: { fontSize: 15, fontWeight: '400' as const },
  caption: { fontSize: 13, fontWeight: '400' as const },
  label: { fontSize: 12, fontWeight: '600' as const },
};
