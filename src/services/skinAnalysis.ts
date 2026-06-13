import {
  AnalysisResult,
  ConcernId,
  ConcernResult,
  FacialZoneId,
  ImageSignals,
  SkinToneProfile,
  SkinType,
  ZoneResult,
} from '../types';
import { fitzInfo } from '../data/skinTones';

/**
 * ──────────────────────────────────────────────────────────────────────────
 * Skin analysis engine
 * ──────────────────────────────────────────────────────────────────────────
 * This module turns image-derived signals + the user's tone profile into a
 * structured, per-zone breakdown of skin concerns.
 *
 * IMPORTANT — about the signal source:
 * A production deployment plugs a computer-vision / ML model into
 * `extractSignals()` (e.g. an on-device TensorFlow Lite / Core ML model or a
 * server inference call) to read true per-pixel statistics from the frame.
 * In this reference build we compute deterministic, plausible signals from a
 * capture seed combined with documented tone predispositions, so the full UX —
 * capture → real-time read-out → per-zone results → recommendations — is
 * exercised end-to-end without requiring native model binaries. The scoring
 * math below is identical regardless of where the signals come from, so
 * swapping in a real model is a one-function change.
 */

const CONCERN_LABELS: Record<ConcernId, string> = {
  texture: 'Texture Irregularities',
  pores: 'Pore Size & Distribution',
  redness: 'Redness & Inflammation',
  dryness: 'Dryness & Hydration',
  oiliness: 'Oiliness & Sebum',
  hyperpigmentation: 'Hyperpigmentation',
  dark_spots: 'Dark Spots',
  under_eye: 'Under-Eye Bags & Discoloration',
  fine_lines: 'Fine Lines & Wrinkles',
  acne: 'Acne & Blemishes',
  scarring: 'Scarring',
  sensitivity: 'Sensitivity Indicators',
  tone_evenness: 'Skin Tone Evenness',
};

const ZONE_LABELS: Record<FacialZoneId, string> = {
  forehead: 'Forehead',
  left_cheek: 'Left Cheek',
  right_cheek: 'Right Cheek',
  nose: 'Nose & T-Zone',
  under_eyes: 'Under Eyes',
  chin: 'Chin',
  jawline: 'Jawline',
};

// Which concerns each zone is meaningfully able to express.
const ZONE_CONCERNS: Record<FacialZoneId, ConcernId[]> = {
  forehead: ['oiliness', 'pores', 'fine_lines', 'texture', 'acne', 'redness'],
  left_cheek: ['redness', 'dryness', 'hyperpigmentation', 'dark_spots', 'texture', 'sensitivity', 'tone_evenness'],
  right_cheek: ['redness', 'dryness', 'hyperpigmentation', 'dark_spots', 'texture', 'sensitivity', 'tone_evenness'],
  nose: ['pores', 'oiliness', 'redness', 'acne', 'texture'],
  under_eyes: ['under_eye', 'fine_lines', 'dryness', 'hyperpigmentation'],
  chin: ['acne', 'oiliness', 'scarring', 'texture', 'pores'],
  jawline: ['acne', 'scarring', 'redness', 'hyperpigmentation', 'texture'],
};

const ALL_CONCERNS: ConcernId[] = [
  'texture',
  'pores',
  'redness',
  'dryness',
  'oiliness',
  'hyperpigmentation',
  'dark_spots',
  'under_eye',
  'fine_lines',
  'acne',
  'scarring',
  'sensitivity',
  'tone_evenness',
];

/** Deterministic seeded PRNG (mulberry32). */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashSeed(input: string): number {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function clamp(v: number, lo = 0, hi = 100): number {
  return Math.max(lo, Math.min(hi, v));
}

function severityFor(score: number): ConcernResult['severity'] {
  if (score < 20) return 'minimal';
  if (score < 40) return 'mild';
  if (score < 65) return 'moderate';
  return 'significant';
}

/**
 * Produce aggregate image signals. In production, replace the body with a real
 * CV/ML read of the captured frame; the return shape stays the same.
 */
export function extractSignals(captureSeed: number, tone: SkinToneProfile): ImageSignals {
  const rng = mulberry32(captureSeed);

  // Baseline brightness tracks the user's tone (deeper skin → lower luma).
  const toneBrightness = 235 - (tone.monk - 1) * 19; // monk 1≈235 → monk 10≈64
  const brightness = clamp(toneBrightness + (rng() - 0.5) * 24, 20, 250);

  const warm = tone.undertone === 'warm' ? 14 : tone.undertone === 'cool' ? -6 : 4;
  const meanR = clamp(brightness * 0.78 + warm + (rng() - 0.5) * 10, 0, 255);
  const meanG = clamp(brightness * 0.7 + (rng() - 0.5) * 10, 0, 255);
  const meanB = clamp(brightness * 0.62 - warm + (rng() - 0.5) * 10, 0, 255);

  const rednessIndex = clamp(((meanR - (meanG + meanB) / 2) / 64) * 100 + (rng() - 0.5) * 30, 0, 100);
  const lumaStdDev = 6 + rng() * 26; // texture proxy
  const highlightRatio = rng() * 0.45; // oily/specular proxy
  const localContrast = 8 + rng() * 30; // pores/lines proxy

  return {
    meanR,
    meanG,
    meanB,
    lumaStdDev,
    rednessIndex,
    highlightRatio,
    brightness,
    localContrast,
  };
}

/**
 * Map signals + tone predisposition into a single concern score (0–100).
 * Each concern has its own evidence formula plus a tone-driven bias.
 */
function scoreConcern(
  concern: ConcernId,
  s: ImageSignals,
  tone: SkinToneProfile,
  jitter: number,
): number {
  const fitz = fitzInfo(tone.fitzpatrick);
  const predisposed = fitz.predisposition.includes(concern) ? 12 : 0;
  let base = 0;

  switch (concern) {
    case 'texture':
      base = s.lumaStdDev * 2.2 + s.localContrast * 0.6;
      break;
    case 'pores':
      base = s.localContrast * 1.8 + s.highlightRatio * 40;
      break;
    case 'redness':
      base = s.rednessIndex * 0.9;
      break;
    case 'dryness':
      base = (1 - s.highlightRatio) * 55 + (s.lumaStdDev - 10) * 1.4;
      break;
    case 'oiliness':
      base = s.highlightRatio * 130;
      break;
    case 'hyperpigmentation':
      base = s.lumaStdDev * 1.6 + (s.localContrast - 12) * 1.1;
      break;
    case 'dark_spots':
      base = s.localContrast * 1.5 + s.lumaStdDev * 0.8;
      break;
    case 'under_eye':
      base = (255 - s.brightness) * 0.12 + s.localContrast * 0.7;
      break;
    case 'fine_lines':
      base = s.localContrast * 1.5 + s.lumaStdDev * 0.7;
      break;
    case 'acne':
      base = s.rednessIndex * 0.5 + s.highlightRatio * 45 + s.localContrast * 0.5;
      break;
    case 'scarring':
      base = s.localContrast * 1.2 + s.lumaStdDev * 0.6;
      break;
    case 'sensitivity':
      base = s.rednessIndex * 0.7 + (1 - s.highlightRatio) * 18;
      break;
    case 'tone_evenness':
      base = s.lumaStdDev * 1.9 + s.localContrast * 0.7;
      break;
  }

  return clamp(base + predisposed + jitter);
}

function makeConcernResult(id: ConcernId, score: number): ConcernResult {
  const rounded = Math.round(score);
  return {
    id,
    label: CONCERN_LABELS[id],
    score: rounded,
    severity: severityFor(rounded),
    description: describeConcern(id, rounded),
  };
}

function describeConcern(id: ConcernId, score: number): string {
  const sev = severityFor(score);
  const lead =
    sev === 'minimal'
      ? 'Looking healthy here'
      : sev === 'mild'
        ? 'A few early signs'
        : sev === 'moderate'
          ? 'Noticeable and worth targeting'
          : 'A primary area to address';
  const detail: Record<ConcernId, string> = {
    texture: 'surface smoothness and uniformity',
    pores: 'pore visibility and size',
    redness: 'diffuse redness and inflammation',
    dryness: 'moisture levels and flaking',
    oiliness: 'sebum production and shine',
    hyperpigmentation: 'patchy excess pigment',
    dark_spots: 'discrete dark marks and PIH',
    under_eye: 'puffiness and under-eye shadowing',
    fine_lines: 'fine lines and early wrinkling',
    acne: 'active blemishes and congestion',
    scarring: 'textural and pigmented scarring',
    sensitivity: 'reactivity and barrier stress',
    tone_evenness: 'overall evenness of skin tone',
  };
  return `${lead} — assessed on ${detail[id]} (${score}/100).`;
}

function zoneSummary(zone: FacialZoneId, concerns: ConcernResult[]): string {
  const top = [...concerns].sort((a, b) => b.score - a.score)[0];
  if (!top || top.severity === 'minimal') {
    return `${ZONE_LABELS[zone]} looks balanced with no standout concerns.`;
  }
  return `${ZONE_LABELS[zone]}: ${top.label.toLowerCase()} is the leading concern in this zone.`;
}

function deriveSkinType(s: ImageSignals): { skinType: SkinType; hydration: number; sebum: number } {
  const sebum = Math.round(clamp(s.highlightRatio * 140));
  const hydration = Math.round(clamp(60 - (s.lumaStdDev - 10) * 2 + (s.highlightRatio - 0.2) * 30));
  let skinType: SkinType;
  if (s.rednessIndex > 55) skinType = 'sensitive';
  else if (sebum > 60) skinType = 'oily';
  else if (sebum > 35) skinType = 'combination';
  else if (hydration < 40) skinType = 'dry';
  else skinType = 'normal';
  return { skinType, hydration, sebum };
}

/** Assemble a full report from finished per-zone results + overall signals. */
function assemble(
  tone: SkinToneProfile,
  zones: ZoneResult[],
  overallSignals: ImageSignals,
  engine: AnalysisResult['engine'],
  id: string,
  faceConfidence?: number,
  concernModelUsed?: boolean,
): AnalysisResult {
  // Overall concern = average of that concern across the zones that express it.
  const overallConcerns: ConcernResult[] = ALL_CONCERNS.map((cid) => {
    const scores: number[] = [];
    zones.forEach((z) => {
      const found = z.concerns.find((c) => c.id === cid);
      if (found) scores.push(found.score);
    });
    const avg = scores.length
      ? scores.reduce((a, b) => a + b, 0) / scores.length
      : scoreConcern(cid, overallSignals, tone, 0);
    return makeConcernResult(cid, avg);
  }).sort((a, b) => b.score - a.score);

  const { skinType, hydration, sebum } = deriveSkinType(overallSignals);
  const avgConcern =
    overallConcerns.reduce((a, c) => a + c.score, 0) / overallConcerns.length;
  const overallSkinScore = Math.round(clamp(100 - avgConcern));

  return {
    id,
    createdAt: Date.now(),
    toneProfile: tone,
    overallConcerns,
    zones,
    skinType,
    hydrationLevel: hydration,
    sebumLevel: sebum,
    overallSkinScore,
    signals: overallSignals,
    engine,
    faceConfidence,
    concernModelUsed,
  };
}

/**
 * Build a report from REAL per-zone signals produced by the on-device model
 * (`faceModel.analyzeCapture`). Each zone is scored from its own measured
 * pixels — no synthetic jitter.
 */
export function runAnalysisFromZones(
  tone: SkinToneProfile,
  overallSignals: ImageSignals,
  zoneSignals: Record<FacialZoneId, ImageSignals>,
  faceConfidence?: number,
  zoneConcernScores?: Record<FacialZoneId, Partial<Record<ConcernId, number>>>,
): AnalysisResult {
  const concernModelUsed = !!zoneConcernScores;
  const zones: ZoneResult[] = (Object.keys(ZONE_CONCERNS) as FacialZoneId[]).map((zoneId) => {
    const sig = zoneSignals[zoneId] ?? overallSignals;
    const modelScores = zoneConcernScores?.[zoneId];
    const concerns = ZONE_CONCERNS[zoneId].map((c) => {
      // Trained classifier score wins when present; otherwise score from the
      // physically-measured pixel signals for this zone.
      const modelScore = modelScores?.[c];
      const score =
        modelScore != null ? modelScore : scoreConcern(c, sig, tone, 0);
      return makeConcernResult(c, score);
    });
    return {
      id: zoneId,
      label: ZONE_LABELS[zoneId],
      concerns,
      summary: zoneSummary(zoneId, concerns),
    };
  });

  return assemble(
    tone,
    zones,
    overallSignals,
    'on_device',
    `analysis_${Date.now()}_${Math.floor(Math.random() * 1e6)}`,
    faceConfidence,
    concernModelUsed,
  );
}

/**
 * Heuristic fallback used when the on-device model/GL backend is unavailable
 * (e.g. the Expo Go sandbox). Derives stable signals from the capture seed.
 */
export function runAnalysis(tone: SkinToneProfile, captureSeed: number): AnalysisResult {
  const signals = extractSignals(captureSeed, tone);
  const rng = mulberry32(captureSeed ^ 0x9e3779b9);

  const zones: ZoneResult[] = (Object.keys(ZONE_CONCERNS) as FacialZoneId[]).map((zoneId) => {
    const concerns = ZONE_CONCERNS[zoneId].map((c) =>
      makeConcernResult(c, scoreConcern(c, signals, tone, (rng() - 0.5) * 26)),
    );
    return {
      id: zoneId,
      label: ZONE_LABELS[zoneId],
      concerns,
      summary: zoneSummary(zoneId, concerns),
    };
  });

  return assemble(tone, zones, signals, 'heuristic', `analysis_${captureSeed}`);
}

export { CONCERN_LABELS, ZONE_LABELS };
