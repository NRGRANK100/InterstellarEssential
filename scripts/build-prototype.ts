/**
 * Builds a static HTML prototype of the app's screens using the REAL design
 * tokens (theme) and REAL engine output (runAnalysis + buildRecommendations),
 * so the prototype reflects what the RN app actually renders. Output: an HTML
 * file that scripts/shoot-prototype.cjs screenshots per screen.
 */
import { writeFileSync } from 'fs';

import { FITZPATRICK_TYPES, MONK_SCALE, ETHNIC_BACKGROUNDS } from '../src/data/skinTones';
import { buildRecommendations } from '../src/services/recommendations';
import { runAnalysis } from '../src/services/skinAnalysis';
import { colors, severityColor } from '../src/theme';
import { FacialZoneId, SkinToneProfile } from '../src/types';

const profile: SkinToneProfile = {
  fitzpatrick: 'V',
  monk: 8,
  undertone: 'warm',
  ethnicBackground: 'south_asian',
  source: 'self_reported',
  createdAt: Date.now(),
};
const analysis = runAnalysis(profile, 1234567);
const recs = buildRecommendations(analysis);

const topSeverity = (id: FacialZoneId) => {
  const z = analysis.zones.find((x) => x.id === id)!;
  return [...z.concerns].sort((a, b) => b.score - a.score)[0].severity;
};
const zoneFill = (id: FacialZoneId) => `${severityColor[topSeverity(id)]}cc`;

const scoreColor =
  analysis.overallSkinScore >= 75 ? colors.success : analysis.overallSkinScore >= 50 ? colors.warning : colors.danger;

function bar(label: string, score: number, sev: string) {
  const c = severityColor[sev] ?? colors.primary;
  return `<div class="barrow">
    <div class="barhead"><span>${label}</span><b style="color:${c}">${score}</b></div>
    <div class="track"><div class="fill" style="width:${Math.max(3, score)}%;background:${c}"></div></div>
  </div>`;
}

const fitzRows = FITZPATRICK_TYPES.map(
  (f) => `<div class="fitz ${f.type === 'V' ? 'active' : ''}">
    <span class="dot" style="background:${f.swatch}"></span>
    <div class="grow"><div class="t">${f.label}</div><div class="s">${f.sunResponse}</div></div>
    <span class="radio ${f.type === 'V' ? 'on' : ''}"></span>
  </div>`,
).join('');

const monkRow = MONK_SCALE.map(
  (m) => `<span class="msw ${m.value === 8 ? 'on' : ''}" style="background:${m.hex}"></span>`,
).join('');

const ethChips = ETHNIC_BACKGROUNDS.map(
  (e) => `<span class="chip ${e.value === 'south_asian' ? 'on' : ''}">${e.label}</span>`,
).join('');

const topConcerns = analysis.overallConcerns
  .slice(0, 3)
  .map(
    (c) => `<div class="card">
      <div class="cardhead"><span class="cname">${c.label}</span>
      <span class="pill" style="color:${severityColor[c.severity]};border-color:${severityColor[c.severity]};background:${severityColor[c.severity]}22">${c.severity}</span></div>
      ${bar('Severity', c.score, c.severity)}
      <div class="desc">${c.description}</div>
    </div>`,
  )
  .join('');

const fullBreak = analysis.overallConcerns.map((c) => bar(c.label, c.score, c.severity)).join('');

const amCards = recs.am
  .slice(0, 5)
  .map(
    (p, i) => `<div class="pcard">
      <div class="prow"><span class="step">${i + 1}</span>
        <div class="grow"><div class="pname">${p.name}</div><div class="pmeta">${p.category.replace('_', ' ')} · ${p.usage}</div></div>
      </div>
      <div class="rationale">${p.rationale}</div>
      ${i < 2 ? `<div class="detail"><div class="dl">For your skin</div><div class="dv">${p.ethnicityNote}</div></div>` : ''}
    </div>`,
  )
  .join('');

const ethLabel = ETHNIC_BACKGROUNDS.find((e) => e.value === profile.ethnicBackground)?.label;

const faceSvg = `<svg viewBox="0 0 200 240" width="220" height="264">
  <path d="M100 8 C150 8 168 50 168 100 C168 165 138 224 100 224 C62 224 32 165 32 100 C32 50 50 8 100 8 Z" fill="${colors.surface}" stroke="${colors.border}" stroke-width="2"/>
  <path d="M55 40 C70 24 130 24 145 40 C140 64 60 64 55 40 Z" fill="${zoneFill('forehead')}"/>
  <ellipse cx="73" cy="92" rx="18" ry="9" fill="${zoneFill('under_eyes')}"/>
  <ellipse cx="127" cy="92" rx="18" ry="9" fill="${zoneFill('under_eyes')}"/>
  <path d="M48 100 C52 140 70 150 86 138 C84 118 74 104 60 102 Z" fill="${zoneFill('left_cheek')}"/>
  <path d="M152 100 C148 140 130 150 114 138 C116 118 126 104 140 102 Z" fill="${zoneFill('right_cheek')}"/>
  <path d="M92 96 C92 120 88 134 100 140 C112 134 108 120 108 96 Z" fill="${zoneFill('nose')}"/>
  <ellipse cx="100" cy="186" rx="26" ry="16" fill="${zoneFill('chin')}"/>
  <path d="M52 150 C60 196 80 214 100 216 C120 214 140 196 148 150 C140 178 120 196 100 196 C80 196 60 178 52 150 Z" fill="${zoneFill('jawline')}"/>
</svg>`;

const css = `
*{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
body{background:#05060d;padding:40px;display:flex;flex-wrap:wrap;gap:40px;align-items:flex-start}
.phone{width:390px;height:844px;background:${colors.background};border-radius:42px;overflow:hidden;position:relative;
  box-shadow:0 30px 80px rgba(0,0,0,.6);border:10px solid #1b1f33}
.scroll{height:100%;overflow:hidden;padding:54px 22px 24px}
.label{position:absolute;top:-30px;left:6px;color:#7780a6;font-size:14px;font-weight:700}
.kicker{color:${colors.primary};letter-spacing:2px;font-size:11px;font-weight:800}
h1{color:${colors.text};font-size:26px;margin-top:8px;line-height:1.15}
.sub{color:${colors.textMuted};font-size:14px;margin-top:12px;line-height:1.5}
.mark{width:60px;height:60px;border-radius:18px;background:${colors.surfaceAlt};display:flex;align-items:center;justify-content:center;font-size:28px;color:${colors.primary};margin-bottom:14px}
.feature{display:flex;gap:12px;background:${colors.surface};border:1px solid ${colors.border};border-radius:14px;padding:14px;margin-top:12px}
.feature .ic{font-size:22px}.feature .t{color:${colors.text};font-weight:700;font-size:14px}.feature .b{color:${colors.textMuted};font-size:12px;margin-top:2px}
.btn{height:50px;border-radius:999px;background:${colors.primary};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;margin-top:18px}
.btn.sec{background:${colors.surfaceAlt};color:${colors.text};border:1px solid ${colors.border}}
.btn.ghost{background:transparent;color:${colors.primary}}
.disc{color:${colors.textFaint};font-size:10.5px;text-align:center;margin-top:16px;line-height:1.5}
.sect{color:${colors.text};font-size:18px;font-weight:800;margin-top:22px}
.hint{color:${colors.textFaint};font-size:12px;margin-top:3px}
.fitz{display:flex;align-items:center;gap:12px;padding:8px;border-radius:14px;border:1px solid transparent;margin-top:4px}
.fitz.active{background:${colors.surface};border-color:${colors.primary}}
.fitz .dot{width:30px;height:30px;border-radius:50%;border:1px solid ${colors.border}}
.fitz .t{color:${colors.text};font-size:13px;font-weight:700}.fitz .s{color:${colors.textFaint};font-size:11px}
.radio{width:18px;height:18px;border-radius:50%;border:2px solid ${colors.border}}.radio.on{border-color:${colors.primary};background:${colors.primary}}
.grow{flex:1}
.monk{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}
.msw{width:38px;height:38px;border-radius:8px;border:2px solid transparent}.msw.on{border-color:${colors.text};transform:scale(1.08)}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}
.chip{padding:8px 13px;border-radius:999px;background:${colors.surface};border:1px solid ${colors.border};color:${colors.textMuted};font-size:12px;font-weight:700}
.chip.on{background:${colors.primary};border-color:${colors.primary};color:#fff}
.badge{display:inline-block;padding:5px 12px;border-radius:999px;border:1px solid ${colors.success};color:${colors.success};background:${colors.surface};font-size:11px;font-weight:800;margin-bottom:10px}
.scoreCard{display:flex;align-items:center;gap:14px;background:${colors.surface};border:1px solid ${colors.border};border-radius:22px;padding:16px}
.ring{width:92px;height:92px;border-radius:50%;border:5px solid ${scoreColor};display:flex;flex-direction:column;align-items:center;justify-content:center}
.ring b{color:${scoreColor};font-size:30px}.ring s{color:${colors.textFaint};font-size:10px;text-decoration:none}
.scoreCard .t{color:${colors.text};font-weight:700;font-size:15px}.scoreCard .s{color:${colors.textMuted};font-size:11.5px;margin-top:3px;line-height:1.4}
.metrics{display:flex;gap:8px;margin-top:14px}
.metric{flex:1;background:${colors.surface};border:1px solid ${colors.border};border-radius:14px;padding:14px;text-align:center}
.metric b{color:${colors.text};font-size:20px}.metric.good b{color:${colors.success}}.metric span{color:${colors.textFaint};font-size:10px;display:block;margin-top:3px}
.facewrap{display:flex;justify-content:center;margin-top:12px}
.legend{display:flex;gap:14px;justify-content:center;margin-top:8px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px}
.legend span{color:${colors.textMuted};font-size:11px}
.barrow{margin-bottom:11px}.barhead{display:flex;justify-content:space-between;font-size:13px;color:${colors.text};font-weight:600;margin-bottom:5px}
.track{height:8px;border-radius:999px;background:${colors.surfaceAlt};overflow:hidden}.fill{height:100%;border-radius:999px}
.card{background:${colors.surface};border:1px solid ${colors.border};border-radius:14px;padding:14px;margin-top:9px}
.cardhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.cname{color:${colors.text};font-weight:700;font-size:14px}
.pill{font-size:11px;font-weight:800;padding:3px 10px;border-radius:999px;border:1px solid;text-transform:capitalize}
.desc{color:${colors.textMuted};font-size:12px;line-height:1.45}
.fullcard{background:${colors.surface};border:1px solid ${colors.border};border-radius:14px;padding:14px;margin-top:9px}
.tabs{display:flex;background:${colors.surface};border:1px solid ${colors.border};border-radius:999px;padding:4px;margin-top:16px}
.tab{flex:1;text-align:center;padding:9px;border-radius:999px;color:${colors.textMuted};font-weight:800;font-size:14px}
.tab.on{background:${colors.primary};color:#fff}
.pcard{background:${colors.surface};border:1px solid ${colors.border};border-radius:14px;padding:14px;margin-top:9px}
.prow{display:flex;align-items:center;gap:10px}
.step{width:30px;height:30px;border-radius:50%;background:${colors.surfaceAlt};border:1px solid ${colors.primaryDark};color:${colors.primary};font-weight:800;display:flex;align-items:center;justify-content:center}
.pname{color:${colors.text};font-weight:700;font-size:14px}.pmeta{color:${colors.textFaint};font-size:11px;text-transform:capitalize}
.rationale{color:${colors.textMuted};font-size:12px;margin-top:9px;line-height:1.45}
.detail{margin-top:10px;background:${colors.surfaceAlt};border-radius:8px;padding:10px}
.dl{color:${colors.primary};font-size:11px;font-weight:800;margin-bottom:3px}.dv{color:${colors.text};font-size:12px;line-height:1.45}
.guide{position:absolute;top:200px;left:70px;width:250px;height:320px}
.corner{position:absolute;width:34px;height:34px;border-color:${colors.primary}}
.live{position:absolute;top:60px;right:18px;width:130px;background:rgba(11,14,26,.7);border-radius:14px;padding:10px}
.live .lr{margin-bottom:9px}.live .ll{color:${colors.textMuted};font-size:11px;margin-bottom:4px}
.live .lt{height:6px;border-radius:999px;background:rgba(255,255,255,.15);overflow:hidden}.live .lf{height:100%;background:${colors.primary}}
.cambottom{position:absolute;left:0;right:0;bottom:0;padding:22px;background:rgba(11,14,26,.85)}
.camhint{color:${colors.text};text-align:center;font-size:13px;margin-bottom:14px;line-height:1.4}
.scanlabel{position:absolute;top:150px;width:100%;text-align:center}
.scanlabel span{background:rgba(11,14,26,.7);color:${colors.text};font-size:13px;font-weight:700;padding:8px 14px;border-radius:999px}
`;

const html = `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>

<div class="phone" id="welcome"><div class="label">1 · Welcome</div><div class="scroll">
  <div class="mark">✦</div>
  <div class="kicker">INTERSTELLAR ESSENTIAL</div>
  <h1>Deep skin analysis, tailored to your tone</h1>
  <div class="sub">Scan your whole face for texture, pores, redness, hydration, pigmentation, fine lines, breakouts and more — then get a routine built for your skin tone and ethnic background.</div>
  <div class="feature"><span class="ic">🔬</span><div><div class="t">Deep facial analysis</div><div class="b">13 skin concerns mapped across 7 facial zones.</div></div></div>
  <div class="feature"><span class="ic">🎯</span><div><div class="t">Tone &amp; ethnicity aware</div><div class="b">Baseline your skin tone so results and advice fit you.</div></div></div>
  <div class="feature"><span class="ic">🧴</span><div><div class="t">Personalized routine</div><div class="b">AM/PM product steps with expected results &amp; cautions.</div></div></div>
  <div class="btn">Get started</div>
  <div class="disc">Interstellar Essential offers cosmetic guidance only and is not a medical device. It does not diagnose skin conditions.</div>
</div></div>

<div class="phone" id="tone"><div class="label">2 · Skin profile</div><div class="scroll">
  <div class="sub" style="margin-top:0">Establishing your baseline lets us read concerns accurately and recommend products that actually suit your skin.</div>
  <div class="sect">Fitzpatrick skin type</div>
  ${fitzRows}
  <div class="sect">Skin tone (Monk scale)</div>
  <div class="monk">${monkRow}</div>
  <div class="sect">Ethnic background</div>
  <div class="chips">${ethChips}</div>
  <div class="btn">Save &amp; start scan</div>
</div></div>

<div class="phone" id="scan"><div class="label">3 · Face scan</div>
  <div style="position:absolute;inset:0;background:radial-gradient(120% 80% at 50% 35%, #46506f 0%, #232a45 45%, #0b0e1a 100%)"></div>
  <div class="scanlabel"><span>Analyzing: Cheeks</span></div>
  <div class="guide">
    <div class="corner" style="top:0;left:0;border-top:3px solid;border-left:3px solid;border-top-left-radius:12px"></div>
    <div class="corner" style="top:0;right:0;border-top:3px solid;border-right:3px solid;border-top-right-radius:12px"></div>
    <div class="corner" style="bottom:0;left:0;border-bottom:3px solid;border-left:3px solid;border-bottom-left-radius:12px"></div>
    <div class="corner" style="bottom:0;right:0;border-bottom:3px solid;border-right:3px solid;border-bottom-right-radius:12px"></div>
  </div>
  <div class="live">
    <div class="lr"><div class="ll">Luminance</div><div class="lt"><div class="lf" style="width:72%"></div></div></div>
    <div class="lr"><div class="ll">Redness</div><div class="lt"><div class="lf" style="width:28%"></div></div></div>
    <div class="lr"><div class="ll">Texture</div><div class="lt"><div class="lf" style="width:44%"></div></div></div>
  </div>
  <div class="cambottom">
    <div class="camhint">Hold steady in even light, no glasses, hair off your face. We'll scan all 7 facial zones.</div>
    <div class="btn" style="margin-top:0">Analyze my face</div>
  </div>
</div>

<div class="phone" id="results"><div class="label">4 · Results</div><div class="scroll">
  <span class="badge">On-device model (face + concern AI) · 96% face match</span>
  <div class="scoreCard">
    <div class="ring"><b>${analysis.overallSkinScore}</b><s>/ 100</s></div>
    <div><div class="t">Overall skin score</div>
      <div class="s">${analysis.skinType[0].toUpperCase() + analysis.skinType.slice(1)} skin · Type V · ${ethLabel}</div>
      <div class="s">Calibrated to your self-reported tone baseline.</div></div>
  </div>
  <div class="metrics">
    <div class="metric good"><b>${analysis.hydrationLevel}%</b><span>Hydration</span></div>
    <div class="metric"><b>${analysis.sebumLevel}%</b><span>Sebum / oil</span></div>
    <div class="metric"><b>${analysis.overallConcerns.filter((c) => c.severity !== 'minimal').length}</b><span>Concerns</span></div>
  </div>
  <div class="sect">Facial zone map</div><div class="hint">Color shows the leading concern severity per zone.</div>
  <div class="facewrap">${faceSvg}</div>
  <div class="legend">
    <span><i style="background:${colors.good}"></i>Minimal</span><span><i style="background:${colors.mild}"></i>Mild</span>
    <span><i style="background:${colors.moderate}"></i>Moderate</span><span><i style="background:${colors.significant}"></i>High</span>
  </div>
  <div class="sect">Top concerns</div>
  ${topConcerns}
  <div class="sect">Full breakdown</div>
  <div class="fullcard">${fullBreak}</div>
</div></div>

<div class="phone" id="recs"><div class="label">5 · Your routine</div><div class="scroll">
  <h1 style="font-size:24px">Your personalized routine</h1>
  <div class="sub">Built for ${analysis.skinType} skin and tailored to your ${ethLabel} background. Products interact differently with each skin tone, so suitability, results and cautions are adjusted for you.</div>
  <div class="tabs"><div class="tab on">AM</div><div class="tab">PM</div><div class="tab">Weekly</div></div>
  <div class="hint" style="margin-top:12px">Apply in this order, morning. Lower steps go first.</div>
  ${amCards}
</div></div>

</body></html>`;

writeFileSync('/tmp/prototype.html', html);
console.log('wrote /tmp/prototype.html');
console.log('score', analysis.overallSkinScore, 'skinType', analysis.skinType);
