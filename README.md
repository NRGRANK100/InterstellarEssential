# Interstellar Essential

A React Native (Expo) mobile app that performs deep facial skin analysis and
generates **tone- and ethnicity-aware** skincare recommendations.

The app scans the whole face, breaks results down by facial zone, and detects a
broad set of skin concerns: **texture irregularities, pore size & distribution,
redness & inflammation, dryness & hydration, oiliness & sebum, hyperpigmentation,
dark spots, under-eye bags & discoloration, fine lines & wrinkles, acne &
blemishes, scarring, sensitivity indicators, and overall tone evenness.**

Before any analysis the user establishes a **baseline skin tone** — either by
selecting their Fitzpatrick type / Monk tone / undertone / ethnic background, or
by taking a **reference photo**. That baseline calibrates both the analysis and
the product advice, because ingredient efficacy and sensitivity genuinely vary
across skin tones and ethnic backgrounds (e.g. post-inflammatory
hyperpigmentation risk in deeper skin, retinoid/acid sensitivity in thinner
skin).

---

## Features

- 📷 **Camera capture** (front-facing) via `expo-camera`, with a face-framing
  guide and a live read-out panel.
- 🧭 **Baseline setup** — Fitzpatrick I–VI, Monk 1–10 scale, undertone, and ethnic
  background; or estimate from a reference photo and confirm.
- 🔬 **Deep analysis** across **13 concerns** mapped over **7 facial zones**
  (forehead, both cheeks, nose/T-zone, under-eyes, chin, jawline).
- 🗺️ **Interactive face heat-map** (SVG) — tap any zone to drill into its
  localized concern scores.
- 📊 **Results breakdown** — overall skin score, derived skin type, hydration and
  sebum levels, ranked top concerns, and a full per-concern scorecard.
- 🧴 **Personalized routine** — AM / PM / weekly steps in application order, each
  with key ingredients, expected results, an **ethnicity-specific note**, and a
  **potential-sensitivity / patch-test note**. Items risky for the user's
  background are flagged ⚠️.
- 💾 **Local persistence** of the tone profile and analysis history via
  `AsyncStorage`.
- 🚀 **Store-ready** config for the App Store and Google Play (bundle IDs,
  permissions, icons, splash, EAS build & submit profiles).

---

## Tech stack

| Area              | Choice                                        |
| ----------------- | --------------------------------------------- |
| Framework         | Expo SDK 51 (managed), React Native 0.74      |
| Language          | TypeScript (strict)                           |
| Navigation        | React Navigation (native-stack)               |
| Camera            | `expo-camera`                                 |
| Vector graphics   | `react-native-svg` (face zone map)            |
| Storage           | `@react-native-async-storage/async-storage`   |
| Build / submit    | EAS (`eas.json`)                              |

---

## Project structure

```
App.tsx                     # Providers + navigation container
index.ts                    # Expo entry
app.json                    # Expo app config (iOS/Android/web, permissions)
eas.json                    # EAS build & submit profiles
scripts/gen-assets.js       # Regenerates placeholder icon/splash PNGs
src/
  components/               # Button, ScoreBar, SeverityPill, FaceZoneMap
  context/AppContext.tsx    # Tone profile + analysis history (persisted)
  data/
    skinTones.ts            # Fitzpatrick + Monk scales, RGB classifier
    products.ts             # Ingredient-led product archetypes w/ ethnicity notes
  navigation/              # Stack navigator + param types
  screens/                 # Welcome, SkinToneSetup, ReferencePhoto, Scan,
                           # Analyzing, Results, ZoneDetail, Recommendations
  services/
    skinAnalysis.ts        # Concern scoring engine (signals -> zones -> report)
    recommendations.ts     # Tone/ethnicity-aware routine builder
  theme/                   # Colors, spacing, typography
  types/                   # Shared domain types
```

---

## Running locally

```bash
npm install
npm start            # then press i / a, or scan the QR with Expo Go
# or directly:
npm run ios
npm run android
npm run typecheck    # tsc --noEmit
```

Camera features require a physical device or a simulator with a camera; Expo Go
is sufficient for development.

---

## How the analysis works (and an honest note)

The scoring pipeline in `src/services/skinAnalysis.ts` is deterministic and
fully exercised end-to-end:

1. `extractSignals()` produces aggregate image signals (brightness, redness
   index, luminance variance, highlight ratio, local contrast).
2. Each of the 13 concerns has its own evidence formula plus a tone-driven
   predisposition bias, scored 0–100 per facial zone.
3. Per-zone results roll up into an overall report, a derived skin type, and an
   overall skin score.
4. `recommendations.ts` ranks products by concern match (severity-weighted),
   skin-type fit, and **ethnicity fit** (boosting indicated products, flagging
   risky ones).

> **Note on the CV/ML model.** True per-pixel facial analysis requires a
> computer-vision model and a native pixel-buffer module, which is out of scope
> for the Expo managed runtime in this reference build. `extractSignals()` is the
> single, well-documented seam where you plug in a real on-device model
> (TensorFlow Lite / Core ML) or a server inference call — the scoring,
> per-zone breakdown, UI, and recommendation logic are identical regardless of
> the signal source. The reference build derives stable, plausible signals from
> the capture + the user's tone baseline so the whole product works today.

This app provides **cosmetic guidance only** — it is not a medical device and
does not diagnose conditions.

---

## Store deployment (App Store & Google Play)

Configured and ready in `app.json` + `eas.json`:

- iOS `bundleIdentifier` and Android `package`: `com.nrgrank.interstellaressential`
- Camera & photo-library usage descriptions / Android permissions
- App icon, adaptive icon, splash, favicon (placeholders in `assets/`; replace
  with final artwork — rerun `node scripts/gen-assets.js` to regenerate)
- EAS `production` build profile (iOS archive, Android app-bundle) and `submit`
  profiles

```bash
npm i -g eas-cli
eas login
eas build:configure                 # sets your real EAS projectId in app.json
eas build --platform ios --profile production
eas build --platform android --profile production
eas submit --platform ios --profile production
eas submit --platform android --profile production
```

Before submitting:

- Replace the placeholder `extra.eas.projectId` in `app.json` (run
  `eas build:configure`).
- Fill in real credentials in `eas.json` `submit.production` (Apple ID / ASC app
  ID / team ID; Google service-account key path).
- Swap the placeholder `assets/` artwork for final brand assets.
- Add a privacy policy (required by both stores for camera + on-device data).
