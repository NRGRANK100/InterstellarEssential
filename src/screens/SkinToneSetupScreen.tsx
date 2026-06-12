import { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '../components/Button';
import { useApp } from '../context/AppContext';
import {
  ETHNIC_BACKGROUNDS,
  FITZPATRICK_TYPES,
  MONK_SCALE,
  UNDERTONES,
  fitzInfo,
} from '../data/skinTones';
import { RootStackParamList } from '../navigation/types';
import { colors, radius, spacing, typography } from '../theme';
import {
  EthnicBackground,
  FitzpatrickType,
  SkinToneProfile,
  Undertone,
} from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'SkinToneSetup'>;

export function SkinToneSetupScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const { toneProfile, setToneProfile } = useApp();
  const prefill = route.params?.prefill;
  const existing = prefill ?? toneProfile ?? undefined;

  const [fitz, setFitz] = useState<FitzpatrickType>(existing?.fitzpatrick ?? 'III');
  const [monk, setMonk] = useState<number>(existing?.monk ?? 4);
  const [undertone, setUndertone] = useState<Undertone>(existing?.undertone ?? 'neutral');
  const [ethnicity, setEthnicity] = useState<EthnicBackground | undefined>(
    existing?.ethnicBackground,
  );

  const info = fitzInfo(fitz);
  const canSave = !!ethnicity;

  const save = async () => {
    if (!ethnicity) return;
    const profile: SkinToneProfile = {
      fitzpatrick: fitz,
      monk,
      undertone,
      ethnicBackground: ethnicity,
      source: prefill ? 'reference_photo' : 'self_reported',
      referenceRgb: prefill?.referenceRgb,
      createdAt: Date.now(),
    };
    await setToneProfile(profile);
    navigation.navigate('Scan');
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 120 }}
    >
      {prefill?.referenceRgb && (
        <View style={styles.banner}>
          <View
            style={[
              styles.swatchLg,
              {
                backgroundColor: `rgb(${Math.round(prefill.referenceRgb.r)},${Math.round(
                  prefill.referenceRgb.g,
                )},${Math.round(prefill.referenceRgb.b)})`,
              },
            ]}
          />
          <Text style={styles.bannerText}>
            We estimated your baseline from your reference photo. Confirm or adjust below.
          </Text>
        </View>
      )}

      <Text style={styles.intro}>
        Establishing your baseline skin tone and background lets us read concerns
        accurately and recommend products that actually suit your skin — efficacy and
        sensitivity vary meaningfully across tones and ethnicities.
      </Text>

      <Pressable style={styles.photoCta} onPress={() => navigation.navigate('ReferencePhoto')}>
        <Text style={styles.photoCtaIcon}>📷</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.photoCtaTitle}>Use a reference photo instead</Text>
          <Text style={styles.photoCtaBody}>
            We’ll sample your skin color to pre-fill these fields.
          </Text>
        </View>
      </Pressable>

      <Section title="Fitzpatrick skin type" hint="How your skin responds to sun.">
        {FITZPATRICK_TYPES.map((f) => (
          <Pressable
            key={f.type}
            onPress={() => {
              setFitz(f.type);
              setMonk(Math.round((f.monkRange[0] + f.monkRange[1]) / 2));
            }}
            style={[styles.fitzRow, fitz === f.type && styles.fitzRowActive]}
          >
            <View style={[styles.swatch, { backgroundColor: f.swatch }]} />
            <View style={{ flex: 1 }}>
              <Text style={styles.fitzLabel}>{f.label}</Text>
              <Text style={styles.fitzSub}>{f.sunResponse}</Text>
            </View>
            <View style={[styles.radio, fitz === f.type && styles.radioActive]} />
          </Pressable>
        ))}
        <Text style={styles.note}>{info.description}</Text>
      </Section>

      <Section title="Skin tone (Monk scale)" hint="Tap the closest match to your skin.">
        <View style={styles.monkRow}>
          {MONK_SCALE.map((m) => (
            <Pressable key={m.value} onPress={() => setMonk(m.value)}>
              <View
                style={[
                  styles.monkSwatch,
                  { backgroundColor: m.hex },
                  monk === m.value && styles.monkSwatchActive,
                ]}
              />
            </Pressable>
          ))}
        </View>
        <Text style={styles.note}>Selected: tone {monk} of 10</Text>
      </Section>

      <Section title="Undertone">
        <View style={styles.chipRow}>
          {UNDERTONES.map((u) => (
            <Chip
              key={u.value}
              label={u.label}
              active={undertone === u.value}
              onPress={() => setUndertone(u.value)}
            />
          ))}
        </View>
        <Text style={styles.note}>
          {UNDERTONES.find((u) => u.value === undertone)?.hint}
        </Text>
      </Section>

      <Section title="Ethnic background" hint="Used to tailor ingredient suitability.">
        <View style={styles.chipRow}>
          {ETHNIC_BACKGROUNDS.map((e) => (
            <Chip
              key={e.value}
              label={e.label}
              active={ethnicity === e.value}
              onPress={() => setEthnicity(e.value)}
            />
          ))}
        </View>
      </Section>

      <Button
        label={canSave ? 'Save & start scan' : 'Select your background to continue'}
        onPress={save}
        disabled={!canSave}
        style={{ marginTop: spacing.lg }}
      />
    </ScrollView>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {hint && <Text style={styles.sectionHint}>{hint}</Text>}
      <View style={{ marginTop: spacing.sm }}>{children}</View>
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, active && styles.chipActive]}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  intro: { ...typography.body, color: colors.textMuted, lineHeight: 21, marginBottom: spacing.md },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bannerText: { flex: 1, color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  swatchLg: { width: 44, height: 44, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border },
  photoCta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.primaryDark,
  },
  photoCtaIcon: { fontSize: 26 },
  photoCtaTitle: { color: colors.text, fontWeight: '700', fontSize: 15 },
  photoCtaBody: { color: colors.textMuted, fontSize: 13, marginTop: 2 },
  section: { marginBottom: spacing.lg },
  sectionTitle: { ...typography.heading, color: colors.text },
  sectionHint: { color: colors.textFaint, fontSize: 13, marginTop: 2 },
  fitzRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  fitzRowActive: { backgroundColor: colors.surface, borderColor: colors.primary },
  swatch: { width: 34, height: 34, borderRadius: 17, borderWidth: 1, borderColor: colors.border },
  fitzLabel: { color: colors.text, fontSize: 14, fontWeight: '600' },
  fitzSub: { color: colors.textFaint, fontSize: 12 },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: colors.border,
  },
  radioActive: { borderColor: colors.primary, backgroundColor: colors.primary },
  note: { color: colors.textFaint, fontSize: 12, marginTop: spacing.sm, lineHeight: 17 },
  monkRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  monkSwatch: {
    width: 42,
    height: 42,
    borderRadius: radius.sm,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  monkSwatchActive: { borderColor: colors.text, transform: [{ scale: 1.08 }] },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textMuted, fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: '#fff' },
});
