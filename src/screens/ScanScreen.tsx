import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { CameraView, useCameraPermissions } from 'expo-camera';
import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '../components/Button';
import { useApp } from '../context/AppContext';
import { RootStackParamList } from '../navigation/types';
import { hashSeed } from '../services/skinAnalysis';
import { colors, radius, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Scan'>;

const LIVE_ZONES = ['Forehead', 'T-zone', 'Cheeks', 'Under eyes', 'Nose', 'Chin', 'Jawline'];

export function ScanScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const { toneProfile } = useApp();
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [zoneIndex, setZoneIndex] = useState(0);
  const [signal, setSignal] = useState({ luminance: 0, redness: 0, texture: 0 });

  // Simulated live read-out while the user frames their face. A production
  // build would feed real per-frame CV stats into this same display.
  useEffect(() => {
    const id = setInterval(() => {
      setZoneIndex((i) => (i + 1) % LIVE_ZONES.length);
      setSignal({
        luminance: 40 + Math.round(Math.random() * 50),
        redness: 10 + Math.round(Math.random() * 40),
        texture: 15 + Math.round(Math.random() * 45),
      });
    }, 900);
    return () => clearInterval(id);
  }, []);

  if (!toneProfile) {
    // Shouldn't happen via normal flow, but guard anyway.
    return (
      <View style={[styles.center, { padding: spacing.lg }]}>
        <Text style={styles.permTitle}>Set up your skin profile first</Text>
        <Button
          label="Set up profile"
          onPress={() => navigation.replace('SkinToneSetup')}
          style={{ marginTop: spacing.lg }}
        />
      </View>
    );
  }

  if (!permission) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={[styles.center, { padding: spacing.lg }]}>
        <Text style={styles.permTitle}>Camera access needed</Text>
        <Text style={styles.permBody}>
          Interstellar Essential needs your camera to scan your face and analyze your skin.
        </Text>
        <Button label="Grant camera access" onPress={requestPermission} style={{ marginTop: spacing.lg }} />
      </View>
    );
  }

  const analyze = async () => {
    if (!cameraRef.current || busy) return;
    setBusy(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.6 });
      const seed = hashSeed(`${photo?.uri ?? Date.now()}:${photo?.width ?? 0}`);
      navigation.replace('Analyzing', { toneProfile, captureSeed: seed });
    } catch (e) {
      console.warn('scan capture failed', e);
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing="front"
        onCameraReady={() => setReady(true)}
      />

      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.faceGuide}>
          <View style={[styles.corner, styles.tl]} />
          <View style={[styles.corner, styles.tr]} />
          <View style={[styles.corner, styles.bl]} />
          <View style={[styles.corner, styles.br]} />
        </View>
        <View style={styles.scanLabel}>
          <Text style={styles.scanLabelText}>Analyzing: {LIVE_ZONES[zoneIndex]}</Text>
        </View>
      </View>

      <View style={[styles.livePanel, { top: insets.top + spacing.md }]} pointerEvents="none">
        <LiveStat label="Luminance" value={signal.luminance} />
        <LiveStat label="Redness" value={signal.redness} />
        <LiveStat label="Texture" value={signal.texture} />
      </View>

      <View style={[styles.bottom, { paddingBottom: insets.bottom + spacing.lg }]}>
        <Text style={styles.hint}>
          Hold steady in even light, no glasses, hair off your face. We’ll scan all 7
          facial zones.
        </Text>
        <Button
          label={busy ? 'Capturing…' : 'Analyze my face'}
          onPress={analyze}
          loading={busy}
          disabled={!ready}
        />
      </View>
    </View>
  );
}

function LiveStat({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.liveStat}>
      <Text style={styles.liveLabel}>{label}</Text>
      <View style={styles.liveTrack}>
        <View style={[styles.liveFill, { width: `${value}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  permTitle: { ...typography.heading, color: colors.text, textAlign: 'center' },
  permBody: { ...typography.body, color: colors.textMuted, textAlign: 'center', marginTop: spacing.sm, lineHeight: 21 },
  overlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  faceGuide: { width: 250, height: 320, borderRadius: 160 },
  corner: { position: 'absolute', width: 34, height: 34, borderColor: colors.primary },
  tl: { top: 0, left: 0, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 12 },
  tr: { top: 0, right: 0, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 12 },
  bl: { bottom: 0, left: 0, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 12 },
  br: { bottom: 0, right: 0, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 12 },
  scanLabel: {
    marginTop: spacing.lg,
    backgroundColor: 'rgba(11,14,26,0.7)',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
  },
  scanLabelText: { color: colors.text, fontWeight: '600', fontSize: 13 },
  livePanel: {
    position: 'absolute',
    right: spacing.md,
    width: 130,
    backgroundColor: 'rgba(11,14,26,0.7)',
    borderRadius: radius.md,
    padding: spacing.sm,
    gap: spacing.sm,
  },
  liveStat: {},
  liveLabel: { color: colors.textMuted, fontSize: 11, marginBottom: 4 },
  liveTrack: { height: 6, borderRadius: radius.pill, backgroundColor: 'rgba(255,255,255,0.15)', overflow: 'hidden' },
  liveFill: { height: '100%', backgroundColor: colors.primary, borderRadius: radius.pill },
  bottom: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    padding: spacing.lg,
    backgroundColor: 'rgba(11,14,26,0.85)',
  },
  hint: { color: colors.text, textAlign: 'center', marginBottom: spacing.md, lineHeight: 20 },
});
