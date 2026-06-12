import { NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '../components/Button';
import { FaceZoneMap } from '../components/FaceZoneMap';
import { ScoreBar } from '../components/ScoreBar';
import { SeverityPill } from '../components/SeverityPill';
import { useApp } from '../context/AppContext';
import { fitzInfo } from '../data/skinTones';
import { ETHNIC_BACKGROUNDS } from '../data/skinTones';
import { RootStackParamList } from '../navigation/types';
import { colors, radius, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Results'>;

export function ResultsScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const { history } = useApp();
  const analysis = history.find((a) => a.id === route.params.analysisId) ?? history[0];

  if (!analysis) {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>No analysis found.</Text>
        <Button label="Back to start" onPress={() => navigation.navigate('Welcome')} style={{ marginTop: spacing.lg }} />
      </View>
    );
  }

  const fitz = fitzInfo(analysis.toneProfile.fitzpatrick);
  const ethLabel = ETHNIC_BACKGROUNDS.find(
    (e) => e.value === analysis.toneProfile.ethnicBackground,
  )?.label;
  const top3 = analysis.overallConcerns.slice(0, 3);
  const scoreColor =
    analysis.overallSkinScore >= 75
      ? colors.success
      : analysis.overallSkinScore >= 50
        ? colors.warning
        : colors.danger;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 120 }}
    >
      {/* Engine badge */}
      <View style={styles.engineRow}>
        <View
          style={[
            styles.engineBadge,
            { borderColor: analysis.engine === 'on_device' ? colors.success : colors.warning },
          ]}
        >
          <Text
            style={[
              styles.engineText,
              { color: analysis.engine === 'on_device' ? colors.success : colors.warning },
            ]}
          >
            {analysis.engine === 'on_device'
              ? `On-device model${
                  analysis.concernModelUsed ? ' (face + concern AI)' : ' (face detection)'
                }${
                  analysis.faceConfidence
                    ? ` • ${Math.round(analysis.faceConfidence * 100)}% face match`
                    : ''
                }`
              : 'Estimated (model unavailable)'}
          </Text>
        </View>
      </View>

      {/* Overall score */}
      <View style={styles.scoreCard}>
        <View style={[styles.scoreRing, { borderColor: scoreColor }]}>
          <Text style={[styles.scoreNum, { color: scoreColor }]}>{analysis.overallSkinScore}</Text>
          <Text style={styles.scoreOf}>/ 100</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.scoreTitle}>Overall skin score</Text>
          <Text style={styles.scoreSub}>
            {analysis.skinType[0].toUpperCase() + analysis.skinType.slice(1)} skin •{' '}
            {fitz.label.split('—')[0].trim()}
            {ethLabel ? ` • ${ethLabel}` : ''}
          </Text>
          <Text style={styles.scoreSub}>
            Calibrated to your {analysis.toneProfile.source === 'reference_photo' ? 'reference photo' : 'self-reported'} tone baseline.
          </Text>
        </View>
      </View>

      <View style={styles.metricsRow}>
        <Metric label="Hydration" value={analysis.hydrationLevel} suffix="%" good />
        <Metric label="Sebum / oil" value={analysis.sebumLevel} suffix="%" />
        <Metric label="Concerns" value={analysis.overallConcerns.filter((c) => c.severity !== 'minimal').length} />
      </View>

      {/* Zone heat map */}
      <Text style={styles.sectionTitle}>Facial zone map</Text>
      <Text style={styles.sectionHint}>Color shows the leading concern severity per zone.</Text>
      <FaceZoneMap
        zones={analysis.zones}
        onSelectZone={(zoneId) =>
          navigation.navigate('ZoneDetail', { analysisId: analysis.id, zoneId })
        }
      />
      <View style={styles.legend}>
        <Legend color={colors.good} label="Minimal" />
        <Legend color={colors.mild} label="Mild" />
        <Legend color={colors.moderate} label="Moderate" />
        <Legend color={colors.significant} label="Significant" />
      </View>

      {/* Top concerns */}
      <Text style={styles.sectionTitle}>Top concerns</Text>
      {top3.map((c) => (
        <View key={c.id} style={styles.concernCard}>
          <View style={styles.concernHeader}>
            <Text style={styles.concernName}>{c.label}</Text>
            <SeverityPill severity={c.severity} />
          </View>
          <ScoreBar label="Severity" score={c.score} severity={c.severity} />
          <Text style={styles.concernDesc}>{c.description}</Text>
        </View>
      ))}

      {/* Full breakdown */}
      <Text style={styles.sectionTitle}>Full breakdown</Text>
      <View style={styles.fullCard}>
        {analysis.overallConcerns.map((c) => (
          <ScoreBar key={c.id} label={c.label} score={c.score} severity={c.severity} />
        ))}
      </View>

      <Text style={styles.sectionTitle}>Per-zone summary</Text>
      {analysis.zones.map((z) => (
        <View key={z.id} style={styles.zoneRow}>
          <Text style={styles.zoneName}>{z.label}</Text>
          <Text style={styles.zoneSummary}>{z.summary}</Text>
          <Button
            label="View zone detail →"
            variant="ghost"
            onPress={() => navigation.navigate('ZoneDetail', { analysisId: analysis.id, zoneId: z.id })}
            style={styles.zoneBtn}
          />
        </View>
      ))}

      <Button
        label="See my personalized routine"
        onPress={() => navigation.navigate('Recommendations', { analysisId: analysis.id })}
        style={{ marginTop: spacing.lg }}
      />
      <Button
        label="Scan again"
        variant="secondary"
        onPress={() => navigation.navigate('Scan')}
        style={{ marginTop: spacing.sm }}
      />
      <Button
        label="Home"
        variant="ghost"
        onPress={() => navigation.navigate('Welcome')}
        style={{ marginTop: spacing.xs }}
      />

      <Text style={styles.disclaimer}>
        Cosmetic guidance only — not a medical diagnosis. Consult a dermatologist for
        persistent or concerning skin issues.
      </Text>
    </ScrollView>
  );
}

function Metric({
  label,
  value,
  suffix,
  good,
}: {
  label: string;
  value: number;
  suffix?: string;
  good?: boolean;
}) {
  return (
    <View style={styles.metric}>
      <Text style={[styles.metricValue, good && { color: colors.success }]}>
        {value}
        {suffix}
      </Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
      <Text style={styles.legendText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
  muted: { color: colors.textMuted },
  engineRow: { flexDirection: 'row', marginBottom: spacing.sm },
  engineBadge: {
    paddingHorizontal: spacing.md,
    paddingVertical: 5,
    borderRadius: radius.pill,
    borderWidth: 1,
    backgroundColor: colors.surface,
  },
  engineText: { fontSize: 11, fontWeight: '700' },
  scoreCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  scoreRing: {
    width: 96,
    height: 96,
    borderRadius: 48,
    borderWidth: 5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreNum: { fontSize: 32, fontWeight: '800' },
  scoreOf: { color: colors.textFaint, fontSize: 11 },
  scoreTitle: { ...typography.subheading, color: colors.text },
  scoreSub: { color: colors.textMuted, fontSize: 12, marginTop: 4, lineHeight: 17 },
  metricsRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  metric: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  metricValue: { color: colors.text, fontSize: 22, fontWeight: '800' },
  metricLabel: { color: colors.textFaint, fontSize: 11, marginTop: 4 },
  sectionTitle: { ...typography.heading, color: colors.text, marginTop: spacing.xl },
  sectionHint: { color: colors.textFaint, fontSize: 13, marginTop: 2, marginBottom: spacing.md },
  legend: { flexDirection: 'row', justifyContent: 'center', flexWrap: 'wrap', gap: spacing.md, marginTop: spacing.sm },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 12, height: 12, borderRadius: 6 },
  legendText: { color: colors.textMuted, fontSize: 12 },
  concernCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  concernHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  concernName: { color: colors.text, fontWeight: '700', fontSize: 15, flex: 1, paddingRight: spacing.sm },
  concernDesc: { color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  fullCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  zoneRow: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  zoneName: { color: colors.text, fontWeight: '700', fontSize: 15 },
  zoneSummary: { color: colors.textMuted, fontSize: 13, marginTop: 4, lineHeight: 18 },
  zoneBtn: { alignSelf: 'flex-start', paddingHorizontal: 0, minHeight: 36, marginTop: spacing.xs },
  disclaimer: {
    color: colors.textFaint,
    fontSize: 11,
    lineHeight: 16,
    marginTop: spacing.lg,
    textAlign: 'center',
  },
});
