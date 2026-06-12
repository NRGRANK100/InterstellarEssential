# Trained skin-concern model (drop-in)

This folder is where a **trained per-zone skin-concern classifier** is placed so
the app scores concerns with a neural network instead of the pixel heuristic.

It is intentionally empty by default. Until you add a model here (or configure a
remote URL), `src/services/concernModel.ts#getModelSource()` returns `null`, the
classifier is disabled, and the app falls back to the physically-measured
pixel-heuristic per-zone scoring. Nothing breaks.

## Model contract

The pipeline crops each of the 7 facial zones, resizes, and feeds them to the
model one zone at a time.

| | |
| --- | --- |
| **Input**  | `float32` tensor `[1, 96, 96, 3]`, RGB, normalized to `[0, 1]` |
| **Output** | `float32` tensor `[1, 13]`, each value in `[0, 1]` (sigmoid) |
| **Labels** | In this exact order (see `CONCERN_ORDER` in `concernModel.ts`): |

```
0  texture
1  pores
2  redness
3  dryness
4  oiliness
5  hyperpigmentation
6  dark_spots
7  under_eye
8  fine_lines
9  acne
10 scarring
11 sensitivity
12 tone_evenness
```

`INPUT_SIZE` (96) and the label order are the single source of truth — change
them in `concernModel.ts` if your model differs.

## Training notes

- **Task:** multi-label regression/classification — each zone crop can exhibit
  several concerns at once, so use per-label sigmoid + binary cross-entropy
  (not softmax).
- **Labels:** train on dermatologist-annotated face-zone crops graded 0–1 per
  concern. Ensure the dataset is **balanced across Fitzpatrick I–VI and ethnic
  backgrounds** so the model is fair across skin tones — this is essential, as
  many public skin datasets under-represent deeper skin.
- **Backbone:** a small MobileNetV3 / EfficientNet-Lite works well on-device.
- **Augmentation:** lighting/white-balance jitter matters for selfie capture.

## Export to TensorFlow.js

From a SavedModel (GraphModel, recommended):

```bash
pip install tensorflowjs
tensorflowjs_converter \
  --input_format=tf_saved_model \
  --output_format=tfjs_graph_model \
  ./saved_model \
  ./assets/models/skin
```

From a Keras model (LayersModel):

```bash
tensorflowjs_converter --input_format=keras model.h5 ./assets/models/skin
# then set format: 'layers' in getModelSource()
```

This produces `model.json` plus one or more `group1-shard*of*.bin` files here.

## Enable it

In `src/services/concernModel.ts`, edit `getModelSource()` to return either:

```ts
// Offline / bundled (these files):
return {
  kind: 'bundle',
  modelJson: require('../../assets/models/skin/model.json'),
  weights: [require('../../assets/models/skin/group1-shard1of1.bin')],
  format: 'graph',
};

// or remote (downloaded once, cached):
return { kind: 'url', url: 'https://your-cdn/skin/model.json', format: 'graph' };
```

The `bin` asset extension is already enabled in `metro.config.js`, so bundled
weights are picked up by the packager automatically. After this, the Results
screen badge reads **“On-device model (face + concern AI)”**.
```
