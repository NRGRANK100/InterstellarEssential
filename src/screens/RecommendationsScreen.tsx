import { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '../components/Button';
import { useApp } from '../context/AppContext';
import { ETHNIC_BACKGROUNDS } from '../data/skinTones';
import { RootStackParamList } from '../navigation/types';
import { buildRecommendations } from '../services/recommendations';
import { colors, radius, spacing, typography } from '../theme';
import { RecommendedProduct } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'Recommendations'>;
type Tab = 'AM' | 'PM' | 'weekly';

export function RecommendationsScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const { history } = useApp();
  const analysis = history.find((a) => a.id === route.params.analysisId);
  const [tab, setTab] = useState<Tab>('AM');

  const recs = useMemo(() => (analysis ? buildRecommendations(analysis) : null), [analysis]);

  if (!analysis || !recs) {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>No recommendations available.</Text>
      </View>
    );
  }

  const ethLabel = ETHNIC_BACKGROUNDS.find(
    (e) => e.value === analysis.toneProfile.ethnicBackground,
  )?.label;

  const list = tab === 'AM' ? recs.am : tab === 'PM' ? recs.pm : recs.weekly;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}
    >
      <Text style={styles.title}>Your personalized routine</Text>
      <Text style={styles.intro}>
        Built for {analysis.skinType} skin and tailored to your {ethLabel ?? 'skin'}{' '}
        background. Products interact differently with each skin tone, so suitability,
        expected results and cautions below are adjusted for you.
      </Text>

      <View style={styles.tabs}>
        {(['AM', 'PM', 'weekly'] as Tab[]).map((t) => (
          <Pressable
            key={t}
            onPress={() => setTab(t)}
            style={[styles.tab, tab === t && styles.tabActive]}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === 'weekly' ? 'Weekly' : t}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.routineHint}>
        {tab === 'weekly'
          ? 'Use 1–2× per week, in the evening, in place of other actives.'
          : `Apply in this order, ${tab === 'AM' ? 'morning' : 'evening'}. Lower steps go first.`}
      </Text>

      {list.length === 0 && <Text style={styles.muted}>No items in this part of the routine.</Text>}

      {list.map((p, idx) => (
        <ProductCard key={p.id} product={p} index={idx + 1} ethLabel={ethLabel} />
      ))}

      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Why this routine</Text>
        <Text style={styles.summaryBody}>
          Your top concerns — {analysis.overallConcerns.slice(0, 3).map((c) => c.label.toLowerCase()).join(', ')} —
          drive the active ingredients chosen. Steps flagged with ⚠️ are effective but
          can cause post-inflammatory hyperpigmentation or irritation for your skin
          background if overused; introduce them slowly and patch test.
        </Text>
      </View>

      <Button
        label="Back to results"
        variant="secondary"
        onPress={() => navigation.navigate('Results', { analysisId: analysis.id })}
        style={{ marginTop: spacing.lg }}
      />

      <Text style={styles.disclaimer}>
        Recommendations are generic, ingredient-led archetypes for educational purposes,
        not specific medical or product endorsements. Patch test new actives and consult a
        dermatologist for medical concerns.
      </Text>
    </ScrollView>
  );
}

function ProductCard({
  product,
  index,
  ethLabel,
}: {
  product: RecommendedProduct;
  index: number;
  ethLabel?: string;
}) {
  const [open, setOpen] = useState(index <= 2);
  return (
    <Pressable style={styles.card} onPress={() => setOpen((o) => !o)}>
      <View style={styles.cardHeader}>
        <View style={styles.stepBadge}>
          <Text style={styles.stepText}>{index}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.productName}>{product.name}</Text>
          <Text style={styles.productMeta}>
            {product.category.replace('_', ' ')} • {product.usage}
          </Text>
        </View>
        <Text style={styles.chevron}>{open ? '▲' : '▼'}</Text>
      </View>

      <Text style={styles.rationale}>{product.rationale}</Text>

      {open && (
        <View style={styles.details}>
          <Detail label="Key ingredients" value={product.keyIngredients.join(', ')} />
          <Detail label="Expected results" value={product.expectedResults} />
          <Detail
            label={`For ${ethLabel ?? 'your'} skin`}
            value={product.ethnicityNote}
            highlight
          />
          <Detail label="Potential sensitivities" value={product.sensitivityNote} />
        </View>
      )}
    </Pressable>
  );
}

function Detail({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <View style={[styles.detailRow, highlight && styles.detailHighlight]}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  muted: { color: colors.textMuted },
  title: { ...typography.title, color: colors.text },
  intro: { color: colors.textMuted, marginTop: spacing.sm, lineHeight: 21 },
  tabs: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.pill,
    padding: 4,
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tab: { flex: 1, paddingVertical: spacing.sm, borderRadius: radius.pill, alignItems: 'center' },
  tabActive: { backgroundColor: colors.primary },
  tabText: { color: colors.textMuted, fontWeight: '700', fontSize: 14 },
  tabTextActive: { color: '#fff' },
  routineHint: { color: colors.textFaint, fontSize: 13, marginTop: spacing.md, marginBottom: spacing.sm },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  stepBadge: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.primaryDark,
  },
  stepText: { color: colors.primary, fontWeight: '800' },
  productName: { color: colors.text, fontWeight: '700', fontSize: 15 },
  productMeta: { color: colors.textFaint, fontSize: 12, marginTop: 2, textTransform: 'capitalize' },
  chevron: { color: colors.textFaint, fontSize: 12 },
  rationale: { color: colors.textMuted, fontSize: 13, marginTop: spacing.sm, lineHeight: 18 },
  details: { marginTop: spacing.md, gap: spacing.sm },
  detailRow: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
  },
  detailHighlight: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    borderTopWidth: 0,
    padding: spacing.sm,
  },
  detailLabel: { color: colors.primary, fontSize: 12, fontWeight: '700', marginBottom: 3 },
  detailValue: { color: colors.text, fontSize: 13, lineHeight: 19 },
  summaryCard: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  summaryTitle: { color: colors.text, fontWeight: '700', fontSize: 15, marginBottom: spacing.sm },
  summaryBody: { color: colors.textMuted, fontSize: 13, lineHeight: 19 },
  disclaimer: {
    color: colors.textFaint,
    fontSize: 11,
    lineHeight: 16,
    marginTop: spacing.lg,
    textAlign: 'center',
  },
});
