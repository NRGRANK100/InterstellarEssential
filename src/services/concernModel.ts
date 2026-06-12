/**
 * ──────────────────────────────────────────────────────────────────────────
 * Trained per-zone skin-concern classifier (optional, pluggable)
 * ──────────────────────────────────────────────────────────────────────────
 * This is the seam for a REAL trained skin-concern model. It runs a TensorFlow.js
 * model on each facial-zone crop and outputs a score per concern. It supports
 * two offline/on-device loading strategies:
 *
 *   1. `bundleResourceIO` — weights shipped inside the app bundle (fully offline).
 *   2. A remote URL (`tf.loadGraphModel`) — downloaded once and cached.
 *
 * Until real weights are provided, `getModelSource()` returns `null`, the model
 * is "not available", and the analysis pipeline transparently falls back to the
 * physically-measured pixel-heuristic per-zone scoring. The moment you drop in a
 * trained model (see `assets/models/skin/README.md`) and point `getModelSource()`
 * at it, every zone is scored by the trained network instead — no other code
 * changes required.
 *
 * MODEL CONTRACT
 *   Input : float32 [1, INPUT_SIZE, INPUT_SIZE, 3], RGB, values in [0, 1].
 *   Output: float32 [1, 13], each in [0, 1] (sigmoid), ordered by CONCERN_ORDER.
 */
import * as tf from '@tensorflow/tfjs';
import { bundleResourceIO } from '@tensorflow/tfjs-react-native';

import { ConcernId } from '../types';

export const INPUT_SIZE = 96;

/** The model's output ordering. Must match the training label order exactly. */
export const CONCERN_ORDER: ConcernId[] = [
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

type ModelSource =
  | { kind: 'url'; url: string; format: 'graph' | 'layers' }
  | { kind: 'bundle'; modelJson: unknown; weights: number[]; format: 'graph' | 'layers' }
  | null;

/**
 * Configure where the trained model comes from. Returns `null` (disabled) by
 * default. To enable, do ONE of the following and return it here:
 *
 *   // (A) Remote, cached after first download:
 *   return {
 *     kind: 'url',
 *     url: 'https://your-cdn.example.com/skin-concern/model.json',
 *     format: 'graph',
 *   };
 *
 *   // (B) Fully offline, bundled weights (place files under
 *   //     assets/models/skin/ then uncomment the requires):
 *   return {
 *     kind: 'bundle',
 *     modelJson: require('../../assets/models/skin/model.json'),
 *     weights: [require('../../assets/models/skin/group1-shard1of1.bin')],
 *     format: 'graph',
 *   };
 */
function getModelSource(): ModelSource {
  return null;
}

export function isConcernModelConfigured(): boolean {
  return getModelSource() !== null;
}

type LoadedModel = tf.GraphModel | tf.LayersModel;

let modelPromise: Promise<LoadedModel | null> | null = null;

export function loadConcernModel(): Promise<LoadedModel | null> {
  if (!modelPromise) {
    modelPromise = (async () => {
      const source = getModelSource();
      if (!source) return null;
      try {
        const handler =
          source.kind === 'bundle'
            ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
              bundleResourceIO(source.modelJson as any, source.weights)
            : source.url;
        return source.format === 'layers'
          ? await tf.loadLayersModel(handler as never)
          : await tf.loadGraphModel(handler as never);
      } catch (e) {
        console.warn('Failed to load concern model; falling back to heuristic:', e);
        return null;
      }
    })();
  }
  return modelPromise;
}

/**
 * Run the trained classifier on a single zone crop of the full image tensor.
 * `rect` is in the same pixel coordinate space as the image tensor.
 * Returns a partial map of concern → 0–100 score, or `null` if no model.
 */
export async function inferZoneConcerns(
  model: LoadedModel | null,
  image: tf.Tensor3D,
  rect: { x: number; y: number; w: number; h: number },
): Promise<Partial<Record<ConcernId, number>> | null> {
  if (!model) return null;

  const batched = tf.tidy(() => {
    const crop = image.slice([rect.y, rect.x, 0], [rect.h, rect.w, 3]);
    const resized = tf.image.resizeBilinear(crop as tf.Tensor3D, [INPUT_SIZE, INPUT_SIZE]);
    return resized.toFloat().div(255).expandDims(0);
  });

  try {
    const output = model.predict(batched) as tf.Tensor;
    const values = (await output.data()) as Float32Array;
    output.dispose();

    const scores: Partial<Record<ConcernId, number>> = {};
    for (let i = 0; i < CONCERN_ORDER.length && i < values.length; i++) {
      scores[CONCERN_ORDER[i]] = Math.max(0, Math.min(100, values[i] * 100));
    }
    return scores;
  } finally {
    batched.dispose();
  }
}
