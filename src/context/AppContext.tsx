import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { AnalysisResult, SkinToneProfile } from '../types';

const TONE_KEY = '@ie/tone_profile';
const HISTORY_KEY = '@ie/analysis_history';

interface AppContextValue {
  toneProfile: SkinToneProfile | null;
  setToneProfile: (p: SkinToneProfile) => Promise<void>;
  history: AnalysisResult[];
  latest: AnalysisResult | null;
  addAnalysis: (a: AnalysisResult) => Promise<void>;
  clearAll: () => Promise<void>;
  hydrated: boolean;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [toneProfile, setToneProfileState] = useState<SkinToneProfile | null>(null);
  const [history, setHistory] = useState<AnalysisResult[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [toneRaw, histRaw] = await Promise.all([
          AsyncStorage.getItem(TONE_KEY),
          AsyncStorage.getItem(HISTORY_KEY),
        ]);
        if (toneRaw) setToneProfileState(JSON.parse(toneRaw));
        if (histRaw) setHistory(JSON.parse(histRaw));
      } catch (e) {
        // Non-fatal — start fresh.
        console.warn('Failed to hydrate storage', e);
      } finally {
        setHydrated(true);
      }
    })();
  }, []);

  const setToneProfile = async (p: SkinToneProfile) => {
    setToneProfileState(p);
    await AsyncStorage.setItem(TONE_KEY, JSON.stringify(p));
  };

  const addAnalysis = async (a: AnalysisResult) => {
    const next = [a, ...history].slice(0, 30);
    setHistory(next);
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  };

  const clearAll = async () => {
    setToneProfileState(null);
    setHistory([]);
    await AsyncStorage.multiRemove([TONE_KEY, HISTORY_KEY]);
  };

  const value = useMemo<AppContextValue>(
    () => ({
      toneProfile,
      setToneProfile,
      history,
      latest: history[0] ?? null,
      addAnalysis,
      clearAll,
      hydrated,
    }),
    [toneProfile, history, hydrated],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
