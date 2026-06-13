/**
 * ──────────────────────────────────────────────────────────────────────────
 * On-device face model + real pixel analysis
 * ──────────────────────────────────────────────────────────────────────────
 * This module runs a genuine on-device computer-vision model — Google's
 * BlazeFace, executed locally via TensorFlow.js (`tfjs-react-native`, WebGL
 * backend) — to (1) confirm a face is present, (2) locate the face bounding
 * box and key landmarks, and (3) drive per-zone cropping of the real captured
 * frame. From those crops we compute **real per-pixel statistics** (mean RGB,
 * redness, luminance variance, specular highlight ratio, high-frequency local
 * contrast) instead of synthesized signals.
 *
 * The output `ImageSignals` are normalized into the same value ranges the
 * scoring engine (`skinAnalysis.ts`) already expects, so the concern math is
 * unchanged — only the source of the signals is now real device pixels.
 *
 * Runtime requirements: this path needs the native GL backend and therefore an
 * Expo dev/production build (it is not available in the Expo Go sandbox). The
 * analysis flow falls back to the heuristic engine if the model is unavailable.
 */
import '@tensorflow/tfjs-react-native';
import * as blazeface from '@tensorflow-models/blazeface';
import * as tf from '@tensorflow/tfjs';
import { decodeJpeg } from '@tensorflow/tfjs-react-native';
import * as FileSystem from 'expo-file-system';

import { ConcernId, FacialZoneId, ImageSignals } from '../types';
import { inferZoneConcerns, loadConcernModel } from './concernModel';

let tfReadyPromise: Promise<void> | null = null;
let modelPromise: Promise<blazeface.BlazeFaceModel> | null = null;

const MAX_WIDTH = 512; // downscale large captures for speed + memory

export async function ensureTfReady(): Promise<void> {
  if (!tfReadyPromise) tfReadyPromise = tf.ready().then(() => undefined);
  return tfReadyPromise;
}

export async function loadFaceModel(): Promise<blazeface.BlazeFaceModel> {
  await ensureTfReady();
  if (!modelPromise) {
    modelPromise = blazeface.load({ maxFaces: 1 });
  }
  return modelPromise;
}

/** Decode base64 → bytes without relying on atob (unavailable in RN). */
const B64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
const B64_LOOKUP = (() => {
  const t = new Uint8Array(256);
  for (let i = 0; i < B64_CHARS.length; i++) t[B64_CHARS.charCodeAt(i)] = i;
  return t;
})();

function base64ToBytes(b64: string): Uint8Array {
  const clean = b64.replace(/[^A-Za-z0-9+/]/g, '');
  const len = clean.length;
  const pad = clean.endsWith('==') ? 2 : clean.endsWith('=') ? 1 : 0;
  const byteLen = Math.floor((len * 3) / 4) - pad;
  const bytes = new Uint8Array(byteLen);
  let p = 0;
  for (let i = 0; i < len; i += 4) {
    const e0 = B64_LOOKUP[clean.charCodeAt(i)];
    const e1 = B64_LOOKUP[clean.charCodeAt(i + 1)];
    const e2 = B64_LOOKUP[clean.charCodeAt(i + 2)];
    const e3 = B64_LOOKUP[clean.charCodeAt(i + 3)];
    const n = (e0 << 18) | (e1 << 12) | (e2 << 6) | e3;
    if (p < byteLen) bytes[p++] = (n >> 16) & 0xff;
    if (p < byteLen) bytes[p++] = (n >> 8) & 0xff;
    if (p < byteLen) bytes[p++] = n & 0xff;
  }
  return bytes;
}

async function loadImageTensor(uri: string): Promise<tf.Tensor3D> {
  const b64 = await FileSystem.readAsStringAsync(uri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  const bytes = base64ToBytes(b64);
  const decoded = decodeJpeg(bytes, 3) as tf.Tensor3D;
  const [h, w] = decoded.shape;
  if (w > MAX_WIDTH) {
    const nh = Math.round((h * MAX_WIDTH) / w);
    const resized = tf.tidy(() =>
      tf.image.resizeBilinear(decoded, [nh, MAX_WIDTH]).toInt(),
    ) as tf.Tensor3D;
    decoded.dispose();
    return resized;
  }
  return decoded;
}

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface CaptureAnalysis {
  faceDetected: boolean;
  faceConfidence: number;
  overallSignals: ImageSignals;
  zoneSignals: Record<FacialZoneId, ImageSignals>;
  /** Per-zone concern scores from the trained classifier, when available. */
  zoneConcernScores?: Record<FacialZoneId, Partial<Record<ConcernId, number>>>;
  /** True when the trained concern model contributed scores. */
  concernModelUsed: boolean;
}

function clampRect(r: Rect, imgW: number, imgH: number): Rect {
  const x = Math.max(0, Math.min(imgW - 2, Math.round(r.x)));
  const y = Math.max(0, Math.min(imgH - 2, Math.round(r.y)));
  const w = Math.max(2, Math.min(imgW - x, Math.round(r.w)));
  const h = Math.max(2, Math.min(imgH - y, Math.round(r.h)));
  return { x, y, w, h };
}

/** Build per-zone rectangles from the face box + eye landmarks. */
function zoneRects(
  box: Rect,
  eyeY: number | null,
  imgW: number,
  imgH: number,
): Record<FacialZoneId, Rect> {
  const { x: bx, y: by, w: bw, h: bh } = box;
  const ueTop = eyeY != null ? eyeY + bh * 0.03 : by + bh * 0.34;
  const rects: Record<FacialZoneId, Rect> = {
    forehead: { x: bx + bw * 0.18, y: by + bh * 0.02, w: bw * 0.64, h: bh * 0.22 },
    under_eyes: { x: bx + bw * 0.18, y: ueTop, w: bw * 0.64, h: bh * 0.12 },
    left_cheek: { x: bx + bw * 0.1, y: by + bh * 0.45, w: bw * 0.3, h: bh * 0.27 },
    right_cheek: { x: bx + bw * 0.6, y: by + bh * 0.45, w: bw * 0.3, h: bh * 0.27 },
    nose: { x: bx + bw * 0.42, y: by + bh * 0.36, w: bw * 0.16, h: bh * 0.3 },
    chin: { x: bx + bw * 0.34, y: by + bh * 0.82, w: bw * 0.32, h: bh * 0.16 },
    jawline: { x: bx + bw * 0.12, y: by + bh * 0.74, w: bw * 0.76, h: bh * 0.2 },
  };
  (Object.keys(rects) as FacialZoneId[]).forEach((k) => {
    rects[k] = clampRect(rects[k], imgW, imgH);
  });
  return rects;
}

function clamp(v: number, lo = 0, hi = 100): number {
  return Math.max(lo, Math.min(hi, v));
}

/**
 * Compute real per-pixel statistics for a rectangle of the image and normalize
 * them into the signal ranges the scoring engine expects.
 *
 * `data` is the flat RGB pixel buffer (length imgW*imgH*3, values 0–255).
 */
function regionSignals(
  data: ArrayLike<number>,
  imgW: number,
  imgH: number,
  rect: Rect,
): ImageSignals {
  const cols = Math.max(2, Math.min(64, rect.w));
  const rows = Math.max(2, Math.min(64, rect.h));
  const sx = rect.w / cols;
  const sy = rect.h / rows;

  const luma: number[] = new Array(rows * cols);
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let sumL = 0;
  let sumL2 = 0;
  let highlight = 0;
  const n = rows * cols;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const px = Math.min(imgW - 1, Math.floor(rect.x + c * sx));
      const py = Math.min(imgH - 1, Math.floor(rect.y + r * sy));
      const idx = (py * imgW + px) * 3;
      const R = data[idx];
      const G = data[idx + 1];
      const B = data[idx + 2];
      const L = 0.299 * R + 0.587 * G + 0.114 * B;
      luma[r * cols + c] = L;
      sumR += R;
      sumG += G;
      sumB += B;
      sumL += L;
      sumL2 += L * L;
      if (L > 200) highlight++;
    }
  }

  const meanR = sumR / n;
  const meanG = sumG / n;
  const meanB = sumB / n;
  const brightness = sumL / n;
  const variance = Math.max(0, sumL2 / n - brightness * brightness);
  const realStd = Math.sqrt(variance); // 0..~90

  // High-frequency local contrast: mean absolute neighbor gradient of luma.
  let grad = 0;
  let gradN = 0;
  for (let r = 1; r < rows; r++) {
    for (let c = 1; c < cols; c++) {
      const i = r * cols + c;
      grad += Math.abs(luma[i] - luma[i - 1]) + Math.abs(luma[i] - luma[i - cols]);
      gradN += 2;
    }
  }
  const realGrad = gradN ? grad / gradN : 0; // 0..~60

  const highlightRatio = highlight / n; // 0..1

  // Redness index, same formula/scale as the engine baseline.
  const rednessIndex = clamp(((meanR - (meanG + meanB) / 2) / 64) * 100, 0, 100);

  // Normalize device measurements into the engine's expected ranges so the
  // concern-scoring formulas remain calibrated.
  const lumaStdDev = 6 + clamp(realStd / 80, 0, 1) * 26; // → 6..32
  const localContrast = 8 + clamp(realGrad / 60, 0, 1) * 30; // → 8..38

  return {
    meanR,
    meanG,
    meanB,
    lumaStdDev,
    rednessIndex,
    highlightRatio: Math.min(0.6, highlightRatio),
    brightness,
    localContrast,
  };
}

const EMPTY_ZONES: FacialZoneId[] = [
  'forehead',
  'under_eyes',
  'left_cheek',
  'right_cheek',
  'nose',
  'chin',
  'jawline',
];

/**
 * Run the full on-device pipeline on a captured photo URI: real face detection
 * + real per-zone pixel statistics. Throws if the model/GL backend is
 * unavailable so the caller can fall back to the heuristic engine.
 */
export async function analyzeCapture(uri: string): Promise<CaptureAnalysis> {
  const model = await loadFaceModel();
  const img = await loadImageTensor(uri);
  try {
    const [h, w] = img.shape;
    const predictions = await model.estimateFaces(img, false);
    const data = (await img.data()) as unknown as ArrayLike<number>;

    if (!predictions.length) {
      // No face — still return whole-frame signals for an optional fallback.
      const whole: Rect = { x: 0, y: 0, w, h };
      const zoneSignals = {} as Record<FacialZoneId, ImageSignals>;
      EMPTY_ZONES.forEach((z) => (zoneSignals[z] = regionSignals(data, w, h, whole)));
      return {
        faceDetected: false,
        faceConfidence: 0,
        overallSignals: regionSignals(data, w, h, whole),
        zoneSignals,
        concernModelUsed: false,
      };
    }

    const face = predictions[0];
    const tl = face.topLeft as [number, number];
    const br = face.bottomRight as [number, number];
    const box = clampRect(
      { x: tl[0], y: tl[1], w: br[0] - tl[0], h: br[1] - tl[1] },
      w,
      h,
    );

    // Landmarks: [rightEye, leftEye, nose, mouth, rightEar, leftEar].
    let eyeY: number | null = null;
    const lm = face.landmarks as number[][] | undefined;
    if (lm && lm.length >= 2) {
      eyeY = (lm[0][1] + lm[1][1]) / 2;
    }

    const rects = zoneRects(box, eyeY, w, h);
    const zoneSignals = {} as Record<FacialZoneId, ImageSignals>;
    (Object.keys(rects) as FacialZoneId[]).forEach((z) => {
      zoneSignals[z] = regionSignals(data, w, h, rects[z]);
    });

    // If a trained concern classifier is configured, run it per zone on the
    // real image tensor; otherwise this is a no-op and the heuristic stands.
    let zoneConcernScores:
      | Record<FacialZoneId, Partial<Record<ConcernId, number>>>
      | undefined;
    let concernModelUsed = false;
    try {
      const concernModel = await loadConcernModel();
      if (concernModel) {
        zoneConcernScores = {} as Record<FacialZoneId, Partial<Record<ConcernId, number>>>;
        for (const z of Object.keys(rects) as FacialZoneId[]) {
          const scores = await inferZoneConcerns(concernModel, img, rects[z]);
          if (scores) {
            zoneConcernScores[z] = scores;
            concernModelUsed = true;
          }
        }
      }
    } catch (e) {
      console.warn('Concern model inference failed; using heuristic scores:', e);
    }

    const prob = face.probability as number[] | number | undefined;
    const faceConfidence = Array.isArray(prob) ? prob[0] : (prob ?? 0.9);

    return {
      faceDetected: true,
      faceConfidence,
      overallSignals: regionSignals(data, w, h, box),
      zoneSignals,
      zoneConcernScores,
      concernModelUsed,
    };
  } finally {
    img.dispose();
  }
}
