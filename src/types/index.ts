// Core domain types for Interstellar Essential skin analysis.

/**
 * Fitzpatrick skin phototype (I–VI) — classic dermatological scale describing
 * how skin responds to UV. We pair it with the Monk scale for richer tone
 * representation and with a self-reported ethnic background, because ingredient
 * suitability and reaction patterns vary across ethnic groups even within the
 * same Fitzpatrick type.
 */
export type FitzpatrickType = 'I' | 'II' | 'III' | 'IV' | 'V' | 'VI';

export type Undertone = 'cool' | 'neutral' | 'warm';

export type EthnicBackground =
  | 'african'
  | 'east_asian'
  | 'south_asian'
  | 'southeast_asian'
  | 'middle_eastern'
  | 'hispanic_latino'
  | 'caucasian'
  | 'mixed'
  | 'other'
  | 'prefer_not_to_say';

export interface SkinToneProfile {
  /** Fitzpatrick phototype I–VI. */
  fitzpatrick: FitzpatrickType;
  /** Monk Skin Tone scale 1–10 (1 = lightest, 10 = deepest). */
  monk: number;
  undertone: Undertone;
  ethnicBackground: EthnicBackground;
  /** How the baseline was established. */
  source: 'self_reported' | 'reference_photo';
  /** Average RGB sampled from a reference photo, if one was used. */
  referenceRgb?: { r: number; g: number; b: number };
  createdAt: number;
}

/** A measurable skin concern. Scores are 0–100 where higher = more concern. */
export type ConcernId =
  | 'texture'
  | 'pores'
  | 'redness'
  | 'dryness'
  | 'oiliness'
  | 'hyperpigmentation'
  | 'dark_spots'
  | 'under_eye'
  | 'fine_lines'
  | 'acne'
  | 'scarring'
  | 'sensitivity'
  | 'tone_evenness';

export interface ConcernResult {
  id: ConcernId;
  label: string;
  /** 0–100, higher = more pronounced concern. */
  score: number;
  /** Bucketed severity derived from score. */
  severity: 'minimal' | 'mild' | 'moderate' | 'significant';
  description: string;
}

export type FacialZoneId =
  | 'forehead'
  | 'left_cheek'
  | 'right_cheek'
  | 'nose'
  | 'under_eyes'
  | 'chin'
  | 'jawline';

export interface ZoneResult {
  id: FacialZoneId;
  label: string;
  /** Concern scores localized to this zone. */
  concerns: ConcernResult[];
  /** Short human summary of the zone. */
  summary: string;
}

export type SkinType = 'dry' | 'oily' | 'combination' | 'normal' | 'sensitive';

export interface AnalysisResult {
  id: string;
  createdAt: number;
  toneProfile: SkinToneProfile;
  /** Overall (whole-face) concern scores. */
  overallConcerns: ConcernResult[];
  zones: ZoneResult[];
  /** Derived dominant skin type. */
  skinType: SkinType;
  hydrationLevel: number; // 0–100, higher = more hydrated
  sebumLevel: number; // 0–100, higher = more oily
  overallSkinScore: number; // 0–100, higher = healthier
  /** Raw sampled image signals, kept for transparency / future ML. */
  signals: ImageSignals;
}

/** Aggregate signals extracted from the captured frame. */
export interface ImageSignals {
  meanR: number;
  meanG: number;
  meanB: number;
  /** Standard deviation of luminance — proxy for texture/unevenness. */
  lumaStdDev: number;
  /** Redness index (r relative to g/b). */
  rednessIndex: number;
  /** Highlight ratio — proportion of very bright (specular/oily) pixels. */
  highlightRatio: number;
  /** Brightness mean (0–255). */
  brightness: number;
  /** Local contrast — proxy for pores/fine lines. */
  localContrast: number;
}

export type ProductCategory =
  | 'cleanser'
  | 'exfoliant'
  | 'toner'
  | 'serum'
  | 'treatment'
  | 'eye_cream'
  | 'moisturizer'
  | 'sunscreen'
  | 'mask';

export interface Product {
  id: string;
  name: string;
  brandStyle: string;
  category: ProductCategory;
  /** Order in an AM/PM routine (lower = applied earlier). */
  applicationStep: number;
  keyIngredients: string[];
  /** Concerns this product targets. */
  targets: ConcernId[];
  /** Skin types this suits. */
  suitableSkinTypes: SkinType[];
  /** Ethnic backgrounds for which this is especially indicated, if any. */
  recommendedFor?: EthnicBackground[];
  /** Backgrounds/types that should approach with caution. */
  cautionFor?: EthnicBackground[];
  expectedResults: string;
  /** Notes about how the product interacts with tone/ethnicity. */
  ethnicityNote: string;
  /** Potential sensitivity / patch-test guidance. */
  sensitivityNote: string;
  usage: 'AM' | 'PM' | 'AM/PM';
}

export interface RecommendedProduct extends Product {
  /** Why this product was selected for the user. */
  rationale: string;
  /** Relevance score used for ranking. */
  matchScore: number;
}
