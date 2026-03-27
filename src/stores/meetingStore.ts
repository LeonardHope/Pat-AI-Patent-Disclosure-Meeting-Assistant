import { create } from "zustand";
import type {
  MeetingState,
  TranscriptSegment,
  Suggestion,
  ModelInfo,
  AudioDevice,
  AudioApp,
} from "../types";

interface MeetingStore {
  state: MeetingState;
  setState: (state: MeetingState) => void;

  transcript: TranscriptSegment[];
  addSegment: (segment: TranscriptSegment) => void;
  clearTranscript: () => void;

  suggestions: Suggestion[];
  setSuggestions: (suggestions: Suggestion[]) => void;
  pastSuggestions: Suggestion[];
  dismissedIds: Set<string>;
  dismissSuggestion: (id: string) => void;

  documentNames: string[];
  documentPreviews: Record<string, string>;
  addDocument: (name: string, preview?: string) => void;
  clearDocuments: () => void;

  summary: string | null;
  setSummary: (summary: string | null) => void;

  models: ModelInfo[];
  setModels: (models: ModelInfo[]) => void;
  recommendedModel: string;
  setRecommendedModel: (name: string) => void;

  downloadProgress: Record<string, { downloaded: number; total: number }>;
  setDownloadProgress: (model: string, downloaded: number, total: number) => void;
  clearDownloadProgress: (model: string) => void;

  microphones: AudioDevice[];
  setMicrophones: (devices: AudioDevice[]) => void;
  apps: AudioApp[];
  setApps: (apps: AudioApp[]) => void;

  // Selected audio sources
  selectedApp: string | null; // bundle_id or null for all
  setSelectedApp: (app: string | null) => void;
  selectedMic: number | null;
  setSelectedMic: (mic: number | null) => void;
  micEnabled: boolean;
  setMicEnabled: (enabled: boolean) => void;

  // Pre-call analysis
  preCallQuestions: { question: string; reason: string }[];
  setPreCallQuestions: (q: { question: string; reason: string }[]) => void;

  // Audio levels (0-1 for VU meters)
  remoteLevel: number;
  localLevel: number;
  setAudioLevel: (source: "remote" | "local", level: number) => void;

  showSettings: boolean;
  setShowSettings: (show: boolean) => void;

  connected: boolean;
  setConnected: (connected: boolean) => void;

  reset: () => void;
}

export const useMeetingStore = create<MeetingStore>((set) => ({
  state: "idle",
  setState: (state) => set({ state }),

  transcript: [],
  addSegment: (segment) =>
    set((s) => ({ transcript: [...s.transcript, segment] })),
  clearTranscript: () => set({ transcript: [] }),

  suggestions: [],
  setSuggestions: (suggestions) =>
    set((s) => {
      // Move current suggestions to past before replacing
      const past = s.suggestions.length > 0
        ? [...s.pastSuggestions, ...s.suggestions.filter(
            (old) => !suggestions.some((n) => n.suggestion === old.suggestion)
          )]
        : s.pastSuggestions;
      return { suggestions, pastSuggestions: past.slice(-20) }; // Keep last 20
    }),
  pastSuggestions: [],
  dismissedIds: new Set<string>(),
  dismissSuggestion: (id) =>
    set((s) => {
      const next = new Set(s.dismissedIds);
      next.add(id);
      return { dismissedIds: next };
    }),

  documentNames: [],
  documentPreviews: {},
  addDocument: (name, preview) =>
    set((s) => ({
      documentNames: [...s.documentNames, name],
      documentPreviews: preview
        ? { ...s.documentPreviews, [name]: preview }
        : s.documentPreviews,
    })),
  clearDocuments: () => set({ documentNames: [], documentPreviews: {} }),

  summary: null,
  setSummary: (summary) => set({ summary }),

  models: [],
  setModels: (models) => set({ models }),
  recommendedModel: "",
  setRecommendedModel: (name) => set({ recommendedModel: name }),

  downloadProgress: {},
  setDownloadProgress: (model, downloaded, total) =>
    set((s) => ({
      downloadProgress: { ...s.downloadProgress, [model]: { downloaded, total } },
    })),
  clearDownloadProgress: (model) =>
    set((s) => {
      const { [model]: _, ...rest } = s.downloadProgress;
      return { downloadProgress: rest };
    }),

  microphones: [],
  setMicrophones: (devices) => set({ microphones: devices }),
  apps: [],
  setApps: (apps) => set({ apps }),

  selectedApp: null,
  setSelectedApp: (app) => set({ selectedApp: app }),
  selectedMic: null,
  setSelectedMic: (mic) => set({ selectedMic: mic }),
  micEnabled: false,
  setMicEnabled: (enabled) => set({ micEnabled: enabled }),

  preCallQuestions: [],
  setPreCallQuestions: (q) => set({ preCallQuestions: q }),

  remoteLevel: 0,
  localLevel: 0,
  setAudioLevel: (source, level) =>
    set(source === "remote" ? { remoteLevel: level } : { localLevel: level }),

  showSettings: false,
  setShowSettings: (show) => set({ showSettings: show }),

  connected: false,
  setConnected: (connected) => set({ connected }),

  reset: () =>
    set({
      state: "idle",
      transcript: [],
      suggestions: [],
      documentNames: [],
      summary: null,
    }),
}));
