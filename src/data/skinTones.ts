import { EthnicBackground, FitzpatrickType, Undertone } from '../types';

export interface FitzpatrickInfo {
  type: FitzpatrickType;
  label: string;
  monkRange: [number, number];
  description: string;
  sunResponse: string;
  /** Swatch color approximating the mid of this phototype. */
  swatch: string;
  /** Concerns this phototype is statistically more prone to. */
  predisposition: string[];
}

export const FITZPATRICK_TYPES: FitzpatrickInfo[] = [
  {
    type: 'I',
    label: 'Type I — Very Fair',
    monkRange: [1, 2],
    description: 'Pale/ivory skin, often with freckles, light eyes and hair.',
    sunResponse: 'Always burns, never tans.',
    swatch: '#F6E0D2',
    predisposition: ['redness', 'fine_lines', 'sensitivity', 'dark_spots'],
  },
  {
    type: 'II',
    label: 'Type II — Fair',
    monkRange: [2, 3],
    description: 'Fair skin that burns easily and tans minimally.',
    sunResponse: 'Burns easily, tans poorly.',
    swatch: '#EBC8AE',
    predisposition: ['redness', 'fine_lines', 'sensitivity'],
  },
  {
    type: 'III',
    label: 'Type III — Medium',
    monkRange: [3, 5],
    description: 'Light-to-medium skin, the most common European tone.',
    sunResponse: 'Sometimes burns, tans gradually.',
    swatch: '#D7A77F',
    predisposition: ['hyperpigmentation', 'tone_evenness', 'oiliness'],
  },
  {
    type: 'IV',
    label: 'Type IV — Olive / Tan',
    monkRange: [5, 7],
    description: 'Olive or moderate brown skin, common in Mediterranean, Latino, and parts of Asia.',
    sunResponse: 'Rarely burns, tans easily.',
    swatch: '#B07C4F',
    predisposition: ['hyperpigmentation', 'tone_evenness', 'acne', 'oiliness'],
  },
  {
    type: 'V',
    label: 'Type V — Brown',
    monkRange: [7, 9],
    description: 'Brown skin, common in South Asian, Middle Eastern, and African heritage.',
    sunResponse: 'Very rarely burns, tans deeply.',
    swatch: '#8A5A36',
    predisposition: ['hyperpigmentation', 'dark_spots', 'scarring', 'tone_evenness'],
  },
  {
    type: 'VI',
    label: 'Type VI — Deep',
    monkRange: [9, 10],
    description: 'Deeply pigmented brown to black skin, common in African heritage.',
    sunResponse: 'Never burns, deeply pigmented.',
    swatch: '#5A3622',
    predisposition: ['hyperpigmentation', 'dark_spots', 'scarring', 'dryness'],
  },
];

export interface MonkSwatch {
  value: number;
  hex: string;
}

// Approximate Monk Skin Tone scale swatches (1 lightest → 10 deepest).
export const MONK_SCALE: MonkSwatch[] = [
  { value: 1, hex: '#F6EDE4' },
  { value: 2, hex: '#F3E7DB' },
  { value: 3, hex: '#F7EAD0' },
  { value: 4, hex: '#EADABA' },
  { value: 5, hex: '#D7BD96' },
  { value: 6, hex: '#A07E56' },
  { value: 7, hex: '#825C43' },
  { value: 8, hex: '#604134' },
  { value: 9, hex: '#3A312A' },
  { value: 10, hex: '#292420' },
];

export const UNDERTONES: { value: Undertone; label: string; hint: string }[] = [
  { value: 'cool', label: 'Cool', hint: 'Veins look blue/purple; silver jewelry flatters.' },
  { value: 'neutral', label: 'Neutral', hint: 'A mix; both gold and silver suit you.' },
  { value: 'warm', label: 'Warm', hint: 'Veins look green; gold jewelry flatters.' },
];

export const ETHNIC_BACKGROUNDS: { value: EthnicBackground; label: string }[] = [
  { value: 'african', label: 'African / Black' },
  { value: 'east_asian', label: 'East Asian' },
  { value: 'south_asian', label: 'South Asian' },
  { value: 'southeast_asian', label: 'Southeast Asian' },
  { value: 'middle_eastern', label: 'Middle Eastern' },
  { value: 'hispanic_latino', label: 'Hispanic / Latino' },
  { value: 'caucasian', label: 'Caucasian / European' },
  { value: 'mixed', label: 'Mixed / Multiple' },
  { value: 'other', label: 'Other' },
  { value: 'prefer_not_to_say', label: 'Prefer not to say' },
];

/**
 * Map an average RGB sample from a reference photo to the closest Monk swatch
 * and a derived Fitzpatrick type + undertone. This is a heuristic baseline; a
 * production build would calibrate against a white-balance reference.
 */
export function classifyRgb(r: number, g: number, b: number): {
  monk: number;
  fitzpatrick: FitzpatrickType;
  undertone: Undertone;
} {
  let bestMonk = MONK_SCALE[0];
  let bestDist = Infinity;
  for (const swatch of MONK_SCALE) {
    const sr = parseInt(swatch.hex.slice(1, 3), 16);
    const sg = parseInt(swatch.hex.slice(3, 5), 16);
    const sb = parseInt(swatch.hex.slice(5, 7), 16);
    const dist = (sr - r) ** 2 + (sg - g) ** 2 + (sb - b) ** 2;
    if (dist < bestDist) {
      bestDist = dist;
      bestMonk = swatch;
    }
  }

  const fitz = FITZPATRICK_TYPES.find(
    (f) => bestMonk.value >= f.monkRange[0] && bestMonk.value <= f.monkRange[1],
  );

  // Undertone heuristic: compare red vs blue channels relative to green.
  let undertone: Undertone = 'neutral';
  const warmth = r - b;
  if (warmth > 22) undertone = 'warm';
  else if (warmth < 8) undertone = 'cool';

  return {
    monk: bestMonk.value,
    fitzpatrick: fitz ? fitz.type : 'III',
    undertone,
  };
}

export function fitzInfo(type: FitzpatrickType): FitzpatrickInfo {
  return FITZPATRICK_TYPES.find((f) => f.type === type) ?? FITZPATRICK_TYPES[2];
}
