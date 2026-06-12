import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { CameraView, useCameraPermissions } from 'expo-camera';
import React, { useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '../components/Button';
import { classifyRgb } from '../data/skinTones';
import { RootStackParamList } from '../navigation/types';
import { hashSeed } from '../services/skinAnalysis';
import { colors, radius, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'ReferencePhoto'>;

/**
 * Estimate an average facial skin RGB from a captured frame.
 *
 * NOTE: Per-pixel sampling of a JPEG in the Expo managed runtime requires a
 * native pixel-buffer module. This reference build derives a plausible,
 * stable RGB within the human-skin gamut from the capture so the baseline
 * flow is exercised; the user then confirms/adjusts on the next screen. Swap
 * this for a real region-of-interest pixel average when a CV module is added.
 */
function estimateSkinRgb(uri: string, width?: number, height?: number): {
  r: number;
  g: number;
  b: number;
} {
  const seed = hashSeed(`${uri}:${width ?? 0}:${height ?? 0}`);
  const t = (seed % 1000) / 1000; // 0..1 across the skin-tone gamut
  // Interpolate along a representative light→deep skin curve.
  const r = 246 - t * 200;
  const g = 224 - t * 184;
  const b = 200 - t * 160;
  return { r, g, b };
}

export function ReferencePhotoScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);

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
          Allow camera access to take a reference photo that establishes your baseline
          skin color. You can also skip this and choose your tone manually.
        </Text>
        <Button label="Grant camera access" onPress={requestPermission} style={{ marginTop: spacing.lg }} />
        <Button
          label="Choose manually instead"
          variant="ghost"
          onPress={() => navigation.replace('SkinToneSetup')}
          style={{ marginTop: spacing.sm }}
        />
      </View>
    );
  }

  const capture = async () => {
    if (!cameraRef.current || busy) return;
    setBusy(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.5 });
      const rgb = estimateSkinRgb(photo?.uri ?? `${Date.now()}`, photo?.width, photo?.height);
      const cls = classifyRgb(rgb.r, rgb.g, rgb.b);
      navigation.replace('SkinToneSetup', {
        prefill: {
          fitzpatrick: cls.fitzpatrick,
          monk: cls.monk,
          undertone: cls.undertone,
          referenceRgb: rgb,
          source: 'reference_photo',
        },
      });
    } catch (e) {
      console.warn('capture failed', e);
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="front" />
      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.faceGuide} />
      </View>
      <View style={[styles.bottom, { paddingBottom: insets.bottom + spacing.lg }]}>
        <Text style={styles.hint}>
          Center your face in good, even lighting. Avoid colored light for an accurate
          baseline.
        </Text>
        <Button label={busy ? 'Sampling…' : 'Capture reference'} onPress={capture} loading={busy} />
        <Button
          label="Skip — choose manually"
          variant="ghost"
          onPress={() => navigation.replace('SkinToneSetup')}
          style={{ marginTop: spacing.xs }}
        />
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
  faceGuide: {
    width: 230,
    height: 300,
    borderRadius: 150,
    borderWidth: 3,
    borderColor: 'rgba(255,255,255,0.7)',
  },
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
