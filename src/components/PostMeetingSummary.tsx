import { useMeetingStore } from "../stores/meetingStore";
import { FileDown, RotateCcw, X } from "lucide-react";

export function PostMeetingSummary() {
  const summary = useMeetingStore((s) => s.summary);
  const setSummary = useMeetingStore((s) => s.setSummary);
  const reset = useMeetingStore((s) => s.reset);

  if (!summary) return null;

  const isGenerating = summary === "_generating_";

  const downloadMarkdown = () => {
    const blob = new Blob([`# Disclosure Meeting Summary\n\n${summary}`], {
      type: "text/markdown",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `meeting-summary-${new Date().toISOString().split("T")[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-8">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold">Meeting Summary</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={downloadMarkdown}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm"
            >
              <FileDown className="w-4 h-4" />
              Export Markdown
            </button>
            <button
              onClick={() => {
                reset();
                setSummary(null);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded text-sm"
            >
              <RotateCcw className="w-4 h-4" />
              New Meeting
            </button>
            <button
              onClick={() => setSummary(null)}
              className="p-1.5 text-gray-400 hover:text-gray-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {isGenerating ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-400">
              <div className="w-8 h-8 border-2 border-gray-600 border-t-purple-400 rounded-full animate-spin" />
              <p className="text-sm">Generating meeting summary...</p>
              <p className="text-xs text-gray-600">This may take a minute</p>
            </div>
          ) : summary.split("\n").map((line, i) => {
            if (line.startsWith("## ") || line.startsWith("**") && line.endsWith("**")) {
              return (
                <h2 key={i} className="text-base font-semibold text-gray-100 mt-5 mb-2">
                  {line.replace(/^##\s*/, "").replace(/\*\*/g, "")}
                </h2>
              );
            }
            if (line.startsWith("- **")) {
              const match = line.match(/^- \*\*(.+?)\*\*:?\s*(.*)/);
              if (match) {
                return (
                  <p key={i} className="text-sm ml-4 mb-1">
                    <strong className="text-gray-200">{match[1]}:</strong>{" "}
                    <span className="text-gray-400">{match[2]}</span>
                  </p>
                );
              }
            }
            if (line.startsWith("- ")) {
              return (
                <p key={i} className="text-sm text-gray-300 ml-4 mb-1">
                  {line.replace(/^- /, "• ")}
                </p>
              );
            }
            if (line.match(/^\d+\./)) {
              return (
                <p key={i} className="text-sm text-gray-300 ml-4 mb-1">
                  {line}
                </p>
              );
            }
            if (line.trim()) {
              return (
                <p key={i} className="text-sm text-gray-300 mb-2">
                  {line}
                </p>
              );
            }
            return null;
          })}
        </div>
      </div>
    </div>
  );
}
