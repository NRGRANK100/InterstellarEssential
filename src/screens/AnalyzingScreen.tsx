import { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../components/Button';
import { useApp } from '../context/AppContext';
import { RootStackParamList } from '../navigation/types';
import { analyzeCapture } from '../services/faceModel';
import { runAnalysis, runAnalysisFromZones } from '../services/skinAnalysis';
import { colors, radius, spacing, typography } from '../theme';
import { AnalysisResult } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'Analyzing'>;

const STEPS = [
  'Warming up the on-device model',
  'Detecting your face',
  'Locating facial landmarks & zones',
  'Reading texture & pore distribution',
  'Measuring redness & inflammation',
  'Assessing hydration & sebum',
  'Scanning pigmentation & dark spots',
  'Evaluating fine lines & under-eye area',
  'Calibrating to your skin tone',
  'Compiling your report',
];

export function AnalyzingScreen({ navigation, route }: Props) {
  const { toneProfile, photoUri, captureSeed } = route.params;
  const { addAnalysis } = useApp();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<'no_face' | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const doneRef = useRef(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setStep((s) => Math.min(s + 1, STEPS.length - 1));
    }, 300);

    (async () => {
      let result: AnalysisResult;
      try {
        if (!photoUri) throw new Error('no photo uri');
        const capture = await analyzeCapture(photoUri);
        if (!capture.faceDetected) {
          clearInterval(interval);
          setError('no_face');
          return;
        }
        result = runAnalysisFromZones(
          toneProfile,
          capture.overallSignals,
          capture.zoneSignals,
          capture.faceConfidence,
        );
      } catch (e) {
        // GL backend / model unavailable (e.g. Expo Go) — degrade gracefully.
        console.warn('On-device model unavailable, using heuristic engine:', e);
        setNote('On-device model unavailable — used estimated analysis.');
        result = runAnalysis(toneProfile, captureSeed);
      }

      // Let the progress animation finish for a smooth hand-off.
      setTimeout(async () => {
        if (doneRef.current || !result) return;
        doneRef.current = true;
        clearInterval(interval);
        await addAnalysis(result);
        navigation.replace('Results', { analysisId: result.id });
      }, 600);
    })();

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error === 'no_face') {
    return (
      <View style={styles.container}>
        <View style={[styles.pulse, { borderColor: colors.warning }]}>
          <Text style={[styles.glyph, { color: colors.warning }]}>!</Text>
        </View>
        <Text style={styles.title}>No face detected</Text>
        <Text style={styles.step}>
          The on-device model couldn’t find a face. Center your face in the frame, remove
          glasses, and use even lighting.
        </Text>
        <Button label="Retake scan" onPress={() => navigation.replace('Scan')} style={{ marginTop: spacing.md, alignSelf: 'stretch' }} />
        <Button
          label="Continue with estimate"
          variant="ghost"
          onPress={async () => {
            const result = runAnalysis(toneProfile, captureSeed);
            await addAnalysis(result);
            navigation.replace('Results', { analysisId: result.id });
          }}
          style={{ marginTop: spacing.xs, alignSelf: 'stretch' }}
        />
      </View>
    );
  }

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
      {note && <Text style={styles.noteText}>{note}</Text>}
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
  glyph: { fontSize: 44, color: colors.primary, fontWeight: '800' },
  title: { ...typography.heading, color: colors.text, textAlign: 'center' },
  step: { color: colors.textMuted, marginTop: spacing.sm, marginBottom: spacing.lg, minHeight: 22, textAlign: 'center', lineHeight: 20 },
  track: {
    width: '100%',
    height: 10,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  fill: { height: '100%', backgroundColor: colors.primary, borderRadius: radius.pill },
  pct: { color: colors.textFaint, marginTop: spacing.sm, fontSize: 13 },
  noteText: { color: colors.warning, fontSize: 12, marginTop: spacing.md, textAlign: 'center' },
});
