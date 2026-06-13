/**
 * Headless demo: runs the real analysis + recommendation engines (the same
 * code the app calls) for a few skin-tone/ethnicity profiles and prints the
 * output. This exercises everything except the camera/TF-GL layer (which needs
 * a device). Run: npx tsx scripts/demo-analysis.ts
 */
import { buildRecommendations } from '../src/services/recommendations';
import { runAnalysis } from '../src/services/skinAnalysis';
import { SkinToneProfile } from '../src/types';

const profiles: { name: string; profile: SkinToneProfile; seed: number }[] = [
  {
    name: 'Fitzpatrick V • South Asian • warm',
    seed: 1234567,
    profile: {
      fitzpatrick: 'V',
      monk: 8,
      undertone: 'warm',
      ethnicBackground: 'south_asian',
      source: 'self_reported',
      createdAt: Date.now(),
    },
  },
  {
    name: 'Fitzpatrick II • Caucasian • cool',
    seed: 9988776,
    profile: {
      fitzpatrick: 'II',
      monk: 2,
      undertone: 'cool',
      ethnicBackground: 'caucasian',
      source: 'self_reported',
      createdAt: Date.now(),
    },
  },
  {
    name: 'Fitzpatrick VI • African • neutral',
    seed: 4455667,
    profile: {
      fitzpatrick: 'VI',
      monk: 10,
      undertone: 'neutral',
      ethnicBackground: 'african',
      source: 'reference_photo',
      createdAt: Date.now(),
    },
  },
];

function bar(score: number): string {
  const filled = Math.round(score / 5);
  return '█'.repeat(filled) + '░'.repeat(20 - filled);
}

for (const { name, profile, seed } of profiles) {
  const a = runAnalysis(profile, seed);
  console.log('\n' + '='.repeat(64));
  console.log(`PROFILE: ${name}`);
  console.log('='.repeat(64));
  console.log(
    `Engine: ${a.engine}   Skin type: ${a.skinType}   ` +
      `Overall score: ${a.overallSkinScore}/100`,
  );
  console.log(`Hydration: ${a.hydrationLevel}%   Sebum: ${a.sebumLevel}%`);

  console.log('\nTop concerns:');
  for (const c of a.overallConcerns.slice(0, 5)) {
    console.log(`  ${c.label.padEnd(28)} ${bar(c.score)} ${c.score} (${c.severity})`);
  }

  console.log('\nLeading concern per zone:');
  for (const z of a.zones) {
    const top = [...z.concerns].sort((x, y) => y.score - x.score)[0];
    console.log(`  ${z.label.padEnd(14)} → ${top.label} (${top.score})`);
  }

  const recs = buildRecommendations(a);
  console.log('\nAM routine:');
  recs.am.forEach((p, i) => {
    console.log(`  ${i + 1}. ${p.name}  [${p.usage}]`);
    console.log(`     ${p.rationale}`);
  });
  console.log('\nPM routine:');
  recs.pm.forEach((p, i) => console.log(`  ${i + 1}. ${p.name}`));
  if (recs.weekly.length) {
    console.log('Weekly:');
    recs.weekly.forEach((p) => console.log(`  • ${p.name}`));
  }
}

console.log('\nDone. (Camera + on-device TF/BlazeFace layer requires a device build.)');
