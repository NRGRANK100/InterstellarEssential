import { NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '../components/Button';
import { useApp } from '../context/AppContext';
import { RootStackParamList } from '../navigation/types';
import { colors, radius, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Welcome'>;

const FEATURES = [
  { icon: '🔬', title: 'Deep facial analysis', body: '13 skin concerns mapped across 7 facial zones.' },
  { icon: '🎯', title: 'Tone & ethnicity aware', body: 'Baseline your skin tone so results and advice fit you.' },
  { icon: '🧴', title: 'Personalized routine', body: 'AM/PM product steps with expected results & cautions.' },
];

export function WelcomeScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const { toneProfile, latest, hydrated } = useApp();

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[
        styles.content,
        { paddingTop: insets.top + spacing.xl, paddingBottom: insets.bottom + spacing.lg },
      ]}
    >
      <View style={styles.brandMark}>
        <Text style={styles.brandGlyph}>✦</Text>
      </View>
      <Text style={styles.kicker}>INTERSTELLAR ESSENTIAL</Text>
      <Text style={styles.title}>Deep skin analysis, tailored to your tone</Text>
      <Text style={styles.subtitle}>
        Scan your whole face for texture, pores, redness, hydration, pigmentation, fine
        lines, breakouts and more — then get a routine built for your skin tone and
        ethnic background.
      </Text>

      <View style={styles.features}>
        {FEATURES.map((f) => (
          <View key={f.title} style={styles.feature}>
            <Text style={styles.featureIcon}>{f.icon}</Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.featureTitle}>{f.title}</Text>
              <Text style={styles.featureBody}>{f.body}</Text>
            </View>
          </View>
        ))}
      </View>

      <View style={styles.actions}>
        {toneProfile ? (
          <>
            <Button label="Start a new scan" onPress={() => navigation.navigate('Scan')} />
            {latest && (
              <Button
                label="View last results"
                variant="secondary"
                onPress={() => navigation.navigate('Results', { analysisId: latest.id })}
                style={{ marginTop: spacing.sm }}
              />
            )}
            <Button
              label="Edit skin profile"
              variant="ghost"
              onPress={() => navigation.navigate('SkinToneSetup')}
              style={{ marginTop: spacing.xs }}
            />
          </>
        ) : (
          <Button
            label="Get started"
            onPress={() => navigation.navigate('SkinToneSetup')}
            disabled={!hydrated}
          />
        )}
      </View>

      <Text style={styles.disclaimer}>
        Interstellar Essential offers cosmetic guidance only and is not a medical device.
        It does not diagnose skin conditions. See a dermatologist for medical concerns.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: spacing.lg },
  brandMark: {
    width: 64,
    height: 64,
    borderRadius: radius.lg,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  brandGlyph: { fontSize: 30, color: colors.primary },
  kicker: { color: colors.primary, letterSpacing: 2, fontSize: 12, fontWeight: '700' },
  title: { ...typography.title, color: colors.text, marginTop: spacing.sm },
  subtitle: { ...typography.body, color: colors.textMuted, marginTop: spacing.md, lineHeight: 22 },
  features: { marginTop: spacing.xl, gap: spacing.md },
  feature: {
    flexDirection: 'row',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  featureIcon: { fontSize: 24 },
  featureTitle: { color: colors.text, fontSize: 15, fontWeight: '700' },
  featureBody: { color: colors.textMuted, fontSize: 13, marginTop: 2, lineHeight: 18 },
  actions: { marginTop: spacing.xl },
  disclaimer: {
    color: colors.textFaint,
    fontSize: 11,
    lineHeight: 16,
    marginTop: spacing.lg,
    textAlign: 'center',
  },
});
