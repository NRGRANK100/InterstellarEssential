import { PRODUCTS } from '../data/products';
import {
  AnalysisResult,
  EthnicBackground,
  Product,
  RecommendedProduct,
} from '../types';

/**
 * Build a personalized, ethnicity-aware routine from an analysis result.
 *
 * Scoring blends three things:
 *  1. Concern match — how strongly the product targets the user's top concerns,
 *     weighted by the severity of each concern.
 *  2. Skin-type fit — whether the formula suits the derived skin type.
 *  3. Ethnicity fit — boosts products specifically indicated for the user's
 *     background, and penalizes (with a caution flag) those that commonly cause
 *     problems for it (e.g. strong acids/retinoids on PIH-prone deep skin).
 */
export function buildRecommendations(analysis: AnalysisResult): {
  routine: RecommendedProduct[];
  am: RecommendedProduct[];
  pm: RecommendedProduct[];
  weekly: RecommendedProduct[];
} {
  const eth = analysis.toneProfile.ethnicBackground;
  const concernWeight = new Map<string, number>();
  analysis.overallConcerns.forEach((c) => concernWeight.set(c.id, c.score));

  const scored: RecommendedProduct[] = PRODUCTS.map((p) =>
    scoreProduct(p, analysis, eth, concernWeight),
  )
    .filter((p) => p.matchScore > 0)
    .sort((a, b) => b.matchScore - a.matchScore);

  // De-duplicate by category, keeping the strongest match per slot, but allow
  // multiple serums/treatments since routines layer them.
  const multiSlot = new Set(['serum', 'treatment', 'mask']);
  const seen = new Set<string>();
  const routine: RecommendedProduct[] = [];
  for (const p of scored) {
    if (multiSlot.has(p.category)) {
      // cap treatments/serums so the routine stays realistic
      const countInCat = routine.filter((r) => r.category === p.category).length;
      const cap = p.category === 'mask' ? 1 : 2;
      if (countInCat >= cap) continue;
      routine.push(p);
    } else {
      if (seen.has(p.category)) continue;
      seen.add(p.category);
      routine.push(p);
    }
  }

  routine.sort((a, b) => a.applicationStep - b.applicationStep);

  const am = routine
    .filter((p) => p.usage !== 'PM' && p.category !== 'mask' && p.category !== 'exfoliant')
    .sort((a, b) => a.applicationStep - b.applicationStep);
  const pm = routine
    .filter((p) => p.usage !== 'AM' && p.category !== 'mask' && p.category !== 'exfoliant')
    .sort((a, b) => a.applicationStep - b.applicationStep);
  const weekly = routine.filter((p) => p.category === 'mask' || p.category === 'exfoliant');

  return { routine, am, pm, weekly };
}

function scoreProduct(
  p: Product,
  analysis: AnalysisResult,
  eth: EthnicBackground,
  concernWeight: Map<string, number>,
): RecommendedProduct {
  let score = 0;
  const reasons: string[] = [];

  // 1. Concern match weighted by severity.
  let topTarget: { concern: string; weight: number } | null = null;
  for (const t of p.targets) {
    const w = concernWeight.get(t) ?? 0;
    if (w > 0) {
      score += w * 0.8;
      if (!topTarget || w > topTarget.weight) topTarget = { concern: t, weight: w };
    }
  }
  if (topTarget && topTarget.weight >= 30) {
    const label = analysis.overallConcerns.find((c) => c.id === topTarget!.concern)?.label;
    reasons.push(`targets your ${label?.toLowerCase()} (${Math.round(topTarget.weight)}/100)`);
  }

  // 2. Skin-type fit.
  if (p.suitableSkinTypes.includes(analysis.skinType)) {
    score += 25;
    reasons.push(`suited to ${analysis.skinType} skin`);
  } else {
    score -= 15;
  }

  // Essentials (cleanser, moisturizer, sunscreen) get a baseline so a routine
  // is always complete even when concerns are low.
  if (['cleanser', 'moisturizer', 'sunscreen'].includes(p.category)) {
    score += 30;
  }

  // 3. Ethnicity fit.
  if (p.recommendedFor?.includes(eth)) {
    score += 35;
    reasons.push('specifically indicated for your skin background');
  }
  let cautioned = false;
  if (p.cautionFor?.includes(eth)) {
    score -= 25;
    cautioned = true;
    reasons.push('use with care for your skin background — introduce slowly');
  }

  // Undertone nudge for sunscreens (tinted mineral flatters deeper tones).
  if (p.id === 'mineral-spf' && analysis.toneProfile.monk >= 6) {
    score += 15;
  }

  const rationale = reasons.length
    ? `Recommended because it ${reasons.join('; ')}.`
    : 'A solid all-rounder for your routine.';

  return {
    ...p,
    matchScore: Math.round(score),
    rationale: (cautioned ? '⚠️ ' : '') + rationale,
  };
}
