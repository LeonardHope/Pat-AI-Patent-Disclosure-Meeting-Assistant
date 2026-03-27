/**
 * Demo mode — populates the UI with realistic mock data for screenshots.
 * Uses a fictional "adaptive thermal management system" invention.
 *
 * Trigger via browser console: window.__loadDemo()
 */

import { useMeetingStore } from "./stores/meetingStore";
import type { TranscriptSegment, Suggestion } from "./types";

const DEMO_TRANSCRIPT: TranscriptSegment[] = [
  {
    id: "d1", speaker: "REMOTE", timestamp: 5, duration: 8, is_final: true,
    text: "So what we've built is a system that listens to a patent disclosure meeting in real time, transcribes the audio on-device, and uses AI to suggest questions that the patent attorney should be asking.",
  },
  {
    id: "d2", speaker: "LOCAL", timestamp: 16, duration: 4, is_final: true,
    text: "Interesting. Walk me through the problem this solves — what's the current process like without the tool?",
  },
  {
    id: "d3", speaker: "REMOTE", timestamp: 23, duration: 9, is_final: true,
    text: "Today, the attorney goes into a meeting, takes notes, and hopes they covered everything. But they often miss critical details — enablement gaps, alternative embodiments, prior art distinctions. They only realize what they missed when they start drafting, and then they need a follow-up meeting.",
  },
  {
    id: "d4", speaker: "LOCAL", timestamp: 36, duration: 4, is_final: true,
    text: "How does the real-time transcription work? Is it cloud-based or on-device?",
  },
  {
    id: "d5", speaker: "REMOTE", timestamp: 43, duration: 10, is_final: true,
    text: "Entirely on-device. We capture the system audio using the operating system's native screen capture API, run it through a voice activity detector to isolate speech segments, then feed those segments to a local speech-to-text model running on the GPU. The transcript stays in memory and is never stored to disk or sent to a server.",
  },
  {
    id: "d6", speaker: "LOCAL", timestamp: 57, duration: 3, is_final: true,
    text: "And how does the AI know what questions to suggest?",
  },
  {
    id: "d7", speaker: "REMOTE", timestamp: 63, duration: 9, is_final: true,
    text: "The system feeds the rolling transcript plus any uploaded disclosure documents to a language model with a patent-specific system prompt. The prompt encodes knowledge about enablement requirements, claim strategy, prior art, and 101 eligibility. The model returns structured suggestions categorized by patent topic and ranked by urgency.",
  },
  {
    id: "d8", speaker: "LOCAL", timestamp: 76, duration: 4, is_final: true,
    text: "How does it handle the timing? You don't want to suggest prior art questions while they're discussing the background.",
  },
  {
    id: "d9", speaker: "REMOTE", timestamp: 83, duration: 7, is_final: true,
    text: "Right, the suggestions are phase-aware. The model detects where the conversation is — background, prior art discussion, technical deep dive, wrap-up — and only surfaces questions relevant to that phase. Earlier suggestions stay visible but fade so the attorney can scroll back.",
  },
];

const DEMO_SUGGESTIONS: Suggestion[] = [
  {
    id: "s1", category: "ENABLEMENT", priority: "HIGH", timestamp: 50,
    suggestion: "What specific speech-to-text model is used for on-device transcription? What are the accuracy benchmarks, especially for accented speakers?",
    context: "The transcription pipeline is a core component — a PHOSITA needs the model architecture and performance characteristics.",
  },
  {
    id: "s2", category: "ELIGIBILITY", priority: "HIGH", timestamp: 55,
    suggestion: "What is the specific technical improvement over an attorney simply recording and reviewing a meeting later? Can you quantify how many follow-up meetings are eliminated?",
    context: "The real-time suggestion timing is the technical effect — needs to be more than just automating note-taking.",
  },
  {
    id: "s3", category: "NON_OBVIOUS", priority: "MEDIUM", timestamp: 65,
    suggestion: "Why wouldn't a skilled engineer simply combine an existing transcription API with a chatbot? What makes the phase-aware suggestion timing non-obvious?",
    context: "Anticipating the obviousness argument — the phase detection and suggestion ranking may be the inventive step.",
  },
  {
    id: "s4", category: "SCOPE", priority: "MEDIUM", timestamp: 75,
    suggestion: "Could this system work for other professional meetings beyond patent disclosures — for example medical consultations, regulatory audits, or due diligence calls?",
    context: "Broader applicability across meeting types strengthens claim scope significantly.",
  },
  {
    id: "s5", category: "TECHNICAL", priority: "MEDIUM", timestamp: 80,
    suggestion: "How does the system handle the debouncing and rate limiting of LLM calls? What triggers a new suggestion update versus waiting for more transcript context?",
    context: "The real-time orchestration between transcription, VAD, and LLM inference is a key technical detail.",
  },
];

export function loadDemo() {
  const store = useMeetingStore.getState();

  store.setState("active");
  store.clearTranscript();

  // Add transcript segments
  for (const seg of DEMO_TRANSCRIPT) {
    store.addSegment(seg);
  }

  // Set suggestions
  store.setSuggestions(DEMO_SUGGESTIONS);
}

// Expose globally for console access
(window as any).__loadDemo = loadDemo;
