import { useState, useEffect } from "react";
import { useMeetingStore } from "../stores/meetingStore";
import {
  Square,
  Wifi,
  WifiOff,
  Settings,
  FileText,
  Clock,
  MessageSquare,
  Sparkles,
  Download,
} from "lucide-react";

interface MeetingControlsProps {
  onStopMeeting: () => void;
  onGenerateSummary: () => void;
  onReset: () => void;
}

export function MeetingControls({
  onStopMeeting,
  onGenerateSummary,
  onReset,
}: MeetingControlsProps) {
  const state = useMeetingStore((s) => s.state);
  const connected = useMeetingStore((s) => s.connected);
  const transcript = useMeetingStore((s) => s.transcript);
  const suggestions = useMeetingStore((s) => s.suggestions);
  const setShowSettings = useMeetingStore((s) => s.setShowSettings);
  const downloadProgress = useMeetingStore((s) => s.downloadProgress);
  const [elapsed, setElapsed] = useState(0);

  const activeDownload = Object.entries(downloadProgress)[0];

  useEffect(() => {
    if (state !== "active") {
      setElapsed(0);
      return;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [state]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm">
      <div className="px-5 py-3 flex items-center justify-between">
        {/* Left: Title + status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-blue-400" />
            <h1 className="text-base font-semibold text-gray-100">
              Pat
            </h1>
          </div>

          <div className="flex items-center gap-1.5 text-xs">
            {connected ? (
              <Wifi className="w-3.5 h-3.5 text-green-400" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-red-400" />
            )}
            <span className={connected ? "text-gray-500" : "text-red-400"}>
              {connected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>

        {/* Center: Meeting status */}
        {state === "active" && (
          <div className="flex items-center gap-5 text-sm">
            <div className="flex items-center gap-2 text-gray-300">
              <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              <Clock className="w-3.5 h-3.5 text-gray-500" />
              <span className="font-mono tabular-nums text-gray-200">
                {formatTime(elapsed)}
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-gray-500">
              <MessageSquare className="w-3.5 h-3.5" />
              <span>{transcript.length}</span>
            </div>
            <div className="flex items-center gap-1.5 text-gray-500">
              <Sparkles className="w-3.5 h-3.5" />
              <span>{suggestions.length}</span>
            </div>
          </div>
        )}

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {state === "active" && (
            <button
              onClick={onStopMeeting}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Square className="w-3.5 h-3.5" />
              End Meeting
            </button>
          )}

          {state === "ended" && (
            <>
              <button
                onClick={onGenerateSummary}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <FileText className="w-3.5 h-3.5" />
                Generate Summary
              </button>
              <button
                onClick={onReset}
                className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg text-sm font-medium transition-colors"
              >
                New Meeting
              </button>
            </>
          )}

          {activeDownload && (
            <div className="flex items-center gap-2 text-xs text-blue-400 bg-blue-500/10 border border-blue-500/20 rounded-lg px-3 py-1.5">
              <Download className="w-3.5 h-3.5 animate-bounce" />
              <span>
                Downloading model...{" "}
                {activeDownload[1].total > 0
                  ? `${Math.round((activeDownload[1].downloaded / activeDownload[1].total) * 100)}%`
                  : ""}
              </span>
              <div className="w-16 bg-blue-900/50 rounded-full h-1.5">
                <div
                  className="bg-blue-400 h-1.5 rounded-full transition-all duration-300"
                  style={{
                    width: `${activeDownload[1].total > 0 ? (activeDownload[1].downloaded / activeDownload[1].total) * 100 : 0}%`,
                  }}
                />
              </div>
            </div>
          )}

          <button
            onClick={() => setShowSettings(true)}
            className="p-2 text-gray-300 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
