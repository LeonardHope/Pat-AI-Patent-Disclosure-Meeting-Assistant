export interface TranscriptSegment {
  id: string;
  text: string;
  speaker: "LOCAL" | "REMOTE" | string;
  timestamp: number;
  duration: number;
  is_final: boolean;
}

export interface Suggestion {
  id: string;
  category: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  suggestion: string;
  context: string;
  timestamp: number;
}

export type MeetingState = "idle" | "pre_call" | "active" | "ended";

export type WSMessage =
  | { type: "transcript_segment"; data: TranscriptSegment }
  | { type: "suggestions_update"; data: Suggestion[] }
  | { type: "meeting_status"; data: { state: MeetingState } }
  | { type: "summary_status"; data: { status: string } }
  | { type: "summary"; data: { markdown: string } }
  | { type: "audio_level"; data: { source: "remote" | "local"; level: number } }
  | { type: "model_downloaded"; data: { model: string } }
  | { type: "model_download_progress"; data: { model: string; downloaded: number; total: number } }
  | { type: "model_download_error"; data: { model: string; error: string } }
  | { type: "error"; data: { message: string } };

export interface ModelInfo {
  name: string;
  filename: string;
  size_gb: number;
  min_ram_gb: number;
  downloaded: boolean;
  recommended: boolean;
  can_run: boolean;
  fit_reason: string;
}

export interface AudioDevice {
  index: number;
  name: string;
  channels: number;
  sample_rate: number;
}

export interface AudioApp {
  bundle_id: string;
  name: string;
}
