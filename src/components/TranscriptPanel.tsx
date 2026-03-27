import { useEffect, useRef } from "react";
import { useMeetingStore } from "../stores/meetingStore";
import { Mic, Monitor } from "lucide-react";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function TranscriptPanel() {
  const transcript = useMeetingStore((s) => s.transcript);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  if (transcript.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-600 px-8">
        <Monitor className="w-10 h-10 mb-3 text-gray-700" />
        <p className="text-sm text-center">
          Listening for speech...
          <br />
          <span className="text-xs text-gray-700">
            Transcript appears here as people speak
          </span>
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="divide-y divide-gray-800/50">
        {transcript.map((seg) => (
          <div
            key={seg.id}
            className="px-4 py-2.5 hover:bg-gray-900/30 transition-colors"
          >
            <div className="flex items-start gap-3">
              {/* Timestamp */}
              <span className="text-[11px] font-mono text-gray-600 tabular-nums mt-0.5 w-10 flex-shrink-0">
                {formatTimestamp(seg.timestamp)}
              </span>

              {/* Speaker icon */}
              <div className="flex-shrink-0 mt-0.5">
                {seg.speaker === "REMOTE" ? (
                  <Monitor className="w-3.5 h-3.5 text-blue-400/70" />
                ) : (
                  <Mic className="w-3.5 h-3.5 text-green-400/70" />
                )}
              </div>

              {/* Text */}
              <p className="text-sm text-gray-300 leading-relaxed flex-1 min-w-0">
                {seg.text}
              </p>
            </div>
          </div>
        ))}
      </div>
      <div ref={bottomRef} />
    </div>
  );
}
