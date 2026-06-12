import { AnalysisResult, FacialZoneId, SkinToneProfile } from '../types';

export type RootStackParamList = {
  Welcome: undefined;
  SkinToneSetup: { prefill?: Partial<SkinToneProfile> } | undefined;
  ReferencePhoto: undefined;
  Scan: undefined;
  Analyzing: { toneProfile: SkinToneProfile; photoUri: string; captureSeed: number };
  Results: { analysisId: string };
  ZoneDetail: { analysisId: string; zoneId: FacialZoneId };
  Recommendations: { analysisId: string };
};

// Helper for passing the freshly computed profile from the photo flow.
export type ReferencePhotoResult = Partial<SkinToneProfile>;
export type { AnalysisResult };
