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
| On-device model   | TensorFlow.js + `tfjs-react-native` (WebGL) + BlazeFace |
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

## How the analysis works

The pipeline runs a **real on-device model** end-to-end:

1. **Face detection (on-device model).** `src/services/faceModel.ts` loads
   Google's **BlazeFace** and runs it locally through **TensorFlow.js** with the
   `tfjs-react-native` WebGL backend. The captured JPEG is decoded into a real
   pixel tensor (`decodeJpeg`), and BlazeFace returns the face bounding box,
   landmarks (eyes/nose/mouth/ears) and a confidence score. No face → the user
   is asked to retake.
2. **Per-zone pixel statistics (real pixels).** The face box + eye landmarks are
   used to crop the 7 facial zones, and for each zone we compute genuine
   per-pixel measurements from the captured frame: mean RGB, redness index,
   luminance variance (texture), specular highlight ratio (oiliness), and
   high-frequency local contrast (pores/fine lines). These are normalized into
   the engine's signal ranges.
3. **Trained concern classifier (pluggable).** If a trained TensorFlow.js
   skin-concern model is configured (`src/services/concernModel.ts`), each zone
   crop is also run through it on-device, producing a score per concern. The
   model loads fully offline via `bundleResourceIO` (bundled weights) or from a
   cached remote URL. Until real weights are dropped in (see
   `assets/models/skin/README.md` for the contract + training/export guide), the
   classifier is disabled and step 4 uses the measured pixel signals instead.
4. **Concern scoring.** `src/services/skinAnalysis.ts` builds the per-zone
   breakdown (`runAnalysisFromZones`): a trained-model score is used when present,
   otherwise the concern is scored from the zone's real pixel signals. Results
   roll up into an overall report with derived skin type, hydration, sebum and
   overall skin score.
5. **Recommendations.** `recommendations.ts` ranks products by concern match
   (severity-weighted), skin-type fit, and **ethnicity fit** (boosting indicated
   products, flagging risky ones).

The Results screen badge reflects exactly which engine ran: **“On-device model
(face + concern AI) • NN% face match”** when a trained classifier scored the
zones, **“On-device model (face detection)”** when only BlazeFace ran with pixel
scoring, or **“Estimated”** for the heuristic fallback.

### Runtime requirements & fallback

- The on-device model needs the native GL backend, so it runs in an **EAS dev or
  production build** (and the Expo Go sandbox will use the fallback). Build a dev
  client with `eas build --profile development` or `npx expo run:ios` /
  `run:android`.
- **First run downloads the BlazeFace weights (~a few hundred KB)** and caches
  them; that initial load needs network. For fully offline weights, switch
  `loadFaceModel()` to `bundleResourceIO` (the `bin` asset extension is already
  enabled in `metro.config.js`).
- If the model or backend is unavailable, the app **gracefully falls back** to a
  deterministic heuristic engine (`runAnalysis`) so it never breaks; the
  fallback is clearly labelled in the UI.

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
