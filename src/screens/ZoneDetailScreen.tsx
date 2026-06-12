import { NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ScoreBar } from '../components/ScoreBar';
import { SeverityPill } from '../components/SeverityPill';
import { useApp } from '../context/AppContext';
import { RootStackParamList } from '../navigation/types';
import { colors, radius, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'ZoneDetail'>;

export function ZoneDetailScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const { history } = useApp();
  const analysis = history.find((a) => a.id === route.params.analysisId);
  const zone = analysis?.zones.find((z) => z.id === route.params.zoneId);

  if (!analysis || !zone) {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>Zone data unavailable.</Text>
      </View>
    );
  }

  const sorted = [...zone.concerns].sort((a, b) => b.score - a.score);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}
    >
      <Text style={styles.title}>{zone.label}</Text>
      <Text style={styles.summary}>{zone.summary}</Text>

      {sorted.map((c) => (
        <View key={c.id} style={styles.card}>
          <View style={styles.header}>
            <Text style={styles.name}>{c.label}</Text>
            <SeverityPill severity={c.severity} />
          </View>
          <ScoreBar label="Score" score={c.score} severity={c.severity} />
          <Text style={styles.desc}>{c.description}</Text>
        </View>
      ))}

      <Text style={styles.note}>
        Zone scores are localized: the same concern can read differently across the
        forehead, cheeks, nose, under-eyes, chin and jawline, which is why targeted
        application matters.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  muted: { color: colors.textMuted },
  title: { ...typography.title, color: colors.text },
  summary: { color: colors.textMuted, marginTop: spacing.sm, marginBottom: spacing.lg, lineHeight: 21 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  name: { color: colors.text, fontWeight: '700', fontSize: 15, flex: 1, paddingRight: spacing.sm },
  desc: { color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  note: { color: colors.textFaint, fontSize: 12, lineHeight: 18, marginTop: spacing.lg },
});
