import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, severityColor } from '../theme';
import { ConcernResult } from '../types';

interface Props {
  label: string;
  /** 0–100 concern score (higher = more concern). */
  score: number;
  severity?: ConcernResult['severity'];
  /** If true, treat the value as a "good" metric (higher = better). */
  positive?: boolean;
}

export function ScoreBar({ label, score, severity, positive }: Props) {
  const pct = Math.max(2, Math.min(100, score));
  const barColor = positive
    ? colors.success
    : severity
      ? severityColor[severity]
      : colors.primary;
  return (
    <View style={styles.row}>
      <View style={styles.header}>
        <Text style={styles.label}>{label}</Text>
        <Text style={[styles.value, { color: barColor }]}>{Math.round(score)}</Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${pct}%`, backgroundColor: barColor }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { marginBottom: 14 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginBottom: 6,
  },
  label: { color: colors.text, fontSize: 14, fontWeight: '600', flex: 1, paddingRight: 8 },
  value: { fontSize: 14, fontWeight: '700' },
  track: {
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    overflow: 'hidden',
  },
  fill: { height: '100%', borderRadius: radius.pill },
});
