import { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { useApp } from '../context/AppContext';
import { RootStackParamList } from '../navigation/types';
import { runAnalysis } from '../services/skinAnalysis';
import { colors, radius, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Analyzing'>;

const STEPS = [
  'Detecting facial landmarks',
  'Mapping the 7 facial zones',
  'Reading texture & pore distribution',
  'Measuring redness & inflammation',
  'Assessing hydration & sebum',
  'Scanning pigmentation & dark spots',
  'Evaluating fine lines & under-eye area',
  'Calibrating to your skin tone',
  'Compiling your report',
];

export function AnalyzingScreen({ navigation, route }: Props) {
  const { toneProfile, captureSeed } = route.params;
  const { addAnalysis } = useApp();
  const [step, setStep] = useState(0);
  const doneRef = useRef(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setStep((s) => Math.min(s + 1, STEPS.length - 1));
    }, 360);

    const timeout = setTimeout(async () => {
      if (doneRef.current) return;
      doneRef.current = true;
      const result = runAnalysis(toneProfile, captureSeed);
      await addAnalysis(result);
      navigation.replace('Results', { analysisId: result.id });
    }, STEPS.length * 360 + 200);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const progress = ((step + 1) / STEPS.length) * 100;

  return (
    <View style={styles.container}>
      <View style={styles.pulse}>
        <Text style={styles.glyph}>✦</Text>
      </View>
      <Text style={styles.title}>Analyzing your skin</Text>
      <Text style={styles.step}>{STEPS[step]}…</Text>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${progress}%` }]} />
      </View>
      <Text style={styles.pct}>{Math.round(progress)}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  pulse: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.primary,
    marginBottom: spacing.xl,
  },
  glyph: { fontSize: 44, color: colors.primary },
  title: { ...typography.heading, color: colors.text },
  step: { color: colors.textMuted, marginTop: spacing.sm, marginBottom: spacing.lg, minHeight: 22 },
  track: {
    width: '100%',
    height: 10,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  fill: { height: '100%', backgroundColor: colors.primary, borderRadius: radius.pill },
  pct: { color: colors.textFaint, marginTop: spacing.sm, fontSize: 13 },
});
