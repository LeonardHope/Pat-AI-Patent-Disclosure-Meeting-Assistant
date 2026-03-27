import { useState } from "react";
import { TranscriptPanel } from "./TranscriptPanel";
import { SuggestionPanel } from "./SuggestionPanel";
import { PreCallSetup } from "./PreCallSetup";
import { useMeetingStore } from "../stores/meetingStore";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

interface LayoutProps {
  onStartMeeting: () => void;
  send: (msg: Record<string, unknown>) => void;
}

export function Layout({ onStartMeeting, send }: LayoutProps) {
  const state = useMeetingStore((s) => s.state);
  const preCallQuestions = useMeetingStore((s) => s.preCallQuestions);
  const [showTranscript, setShowTranscript] = useState(true);

  if (state === "idle") {
    return <PreCallSetup onStartMeeting={onStartMeeting} send={send} />;
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left: Transcript (collapsible) */}
      {showTranscript && (
        <div className="flex-1 flex flex-col border-r border-gray-800 min-w-0">
          <div className="px-4 py-2.5 border-b border-gray-800 bg-gray-900/50 flex items-center justify-between">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Live Transcript
            </h2>
            <button
              onClick={() => setShowTranscript(false)}
              className="text-gray-600 hover:text-gray-400 transition-colors"
              title="Hide transcript"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>
          <TranscriptPanel />
        </div>
      )}

      {/* Right: Suggestions (expands to full width when transcript hidden) */}
      <div className={`flex flex-col min-w-0 ${showTranscript ? "w-[440px] flex-shrink-0" : "flex-1"}`}>
        <div className="px-4 py-2.5 border-b border-gray-800 bg-gray-900/50 flex items-center gap-2">
          {!showTranscript && (
            <button
              onClick={() => setShowTranscript(true)}
              className="text-gray-600 hover:text-gray-400 transition-colors"
              title="Show transcript"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          )}
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            AI Suggestions
          </h2>
        </div>
        <SuggestionPanel preCallQuestions={preCallQuestions} />
      </div>
    </div>
  );
}
