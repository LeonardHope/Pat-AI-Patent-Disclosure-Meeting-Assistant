import { useCallback, useEffect, useState } from "react";
import { useMeetingStore } from "../stores/meetingStore";
import { VuMeter } from "./VuMeter";
import {
  Monitor,
  Mic,
  MicOff,
  Upload,
  FileText,
  Play,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Download,
  Brain,
  X,
} from "lucide-react";

interface PreCallSetupProps {
  onStartMeeting: () => void;
  send: (msg: Record<string, unknown>) => void;
}

export function PreCallSetup({ onStartMeeting, send }: PreCallSetupProps) {
  const connected = useMeetingStore((s) => s.connected);
  const apps = useMeetingStore((s) => s.apps);
  const setApps = useMeetingStore((s) => s.setApps);
  const microphones = useMeetingStore((s) => s.microphones);
  const setMicrophones = useMeetingStore((s) => s.setMicrophones);
  const selectedApp = useMeetingStore((s) => s.selectedApp);
  const setSelectedApp = useMeetingStore((s) => s.setSelectedApp);
  const selectedMic = useMeetingStore((s) => s.selectedMic);
  const setSelectedMic = useMeetingStore((s) => s.setSelectedMic);
  const micEnabled = useMeetingStore((s) => s.micEnabled);
  const setMicEnabled = useMeetingStore((s) => s.setMicEnabled);
  const documentNames = useMeetingStore((s) => s.documentNames);
  const documentPreviews = useMeetingStore((s) => s.documentPreviews);
  const addDocument = useMeetingStore((s) => s.addDocument);
  const clearDocuments = useMeetingStore((s) => s.clearDocuments);

  const [loadingDevices, setLoadingDevices] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [docCapacity, setDocCapacity] = useState<{ total: number; max: number } | null>(null);
  const [analysis, setAnalysis] = useState<{
    summary?: string;
    technology_area?: string;
    key_elements?: string[];
    top_questions?: { question: string; reason: string }[];
  } | null>(null);

  const remoteLevel = useMeetingStore((s) => s.remoteLevel);
  const localLevel = useMeetingStore((s) => s.localLevel);
  const setPreCallQuestions = useMeetingStore((s) => s.setPreCallQuestions);
  const [provider, setProvider] = useState("lmstudio");

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((data) => setProvider(data.llm?.provider ?? "lmstudio"))
      .catch(() => {});
  }, [connected]);


  const loadDevices = useCallback(async () => {
    setLoadingDevices(true);
    try {
      const r = await fetch("/api/devices");
      const data = await r.json();
      setMicrophones(data.microphones ?? []);
      setApps(data.apps ?? []);
    } finally {
      setLoadingDevices(false);
    }
  }, [setMicrophones, setApps]);

  useEffect(() => {
    if (connected) loadDevices();
  }, [connected, loadDevices]);

  // Start/stop audio monitoring for VU meters
  useEffect(() => {
    if (!connected) return;
    send({
      type: "start_audio_monitor",
      app_bundle_id: selectedApp,
      mic_device: selectedMic,
      mic_enabled: micEnabled,
    });
    return () => {
      send({ type: "stop_audio_monitor" });
    };
  }, [connected, selectedApp, selectedMic, micEnabled, send]);

  const uploadFile = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch("/api/documents/upload", {
          method: "POST",
          body: formData,
        });
        if (response.ok) {
          const data = await response.json();
          if (data.error) {
            setUploadError(data.error);
            return;
          }
          setUploadError(null);
          if (data.total_chars && data.max_chars) {
            setDocCapacity({ total: data.total_chars, max: data.max_chars });
          }
          addDocument(data.filename);
          // Auto-analyze after upload
          if (!analyzing) {
            setAnalyzing(true);
            setAnalyzeProgress(0);
            // Progress slows down as it approaches 95% (asymptotic)
            // This naturally handles variable LLM response times
            const startTime = Date.now();
            const progressInterval = setInterval(() => {
              const elapsed = (Date.now() - startTime) / 1000;
              // Asymptotic curve: fast at start, slows near 95%
              // At 10s → ~60%, at 20s → ~80%, at 30s → ~88%, at 60s → ~95%
              const pct = Math.min(95, Math.round(95 * (1 - Math.exp(-elapsed / 15))));
              setAnalyzeProgress(pct);
            }, 300);
            fetch("/api/documents/analyze", { method: "POST" })
              .then((r) => r.json())
              .then((result) => {
                clearInterval(progressInterval);
                if (result.error) {
                  console.error("Analysis failed:", result.error);
                  setAnalyzeProgress(0);
                  // Retry once
                  setTimeout(() => {
                    fetch("/api/documents/analyze", { method: "POST" })
                      .then((r) => r.json())
                      .then((r2) => {
                        if (!r2.error) {
                          setAnalysis(r2);
                          if (r2.top_questions) setPreCallQuestions(r2.top_questions);
                        }
                      })
                      .finally(() => setAnalyzing(false));
                  }, 1000);
                } else {
                  setAnalyzeProgress(100);
                  setAnalysis(result);
                  if (result.top_questions) setPreCallQuestions(result.top_questions);
                  setAnalyzing(false);
                }
              })
              .catch(() => {
                clearInterval(progressInterval);
                setAnalyzing(false);
              });
          }
        }
      } finally {
        setUploading(false);
      }
    },
    [addDocument]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      Array.from(e.dataTransfer.files).forEach(uploadFile);
    },
    [uploadFile]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      Array.from(e.target.files ?? []).forEach(uploadFile);
    },
    [uploadFile]
  );

  // Only show apps a user would actually use for meetings or audio playback
  const relevantApps = apps.filter((a) => {
    // Exclude system helpers, background processes, autofill, etc.
    if (/AutoFill|Helper|Agent|Daemon|Service|Extension|WebView|SandboxBroker/i.test(a.name)) return false;
    if (/com\.apple\.Safari.*Helper|com\.apple\.Safari.*Broker/i.test(a.bundle_id)) return false;
    if (/\.helper$/i.test(a.bundle_id)) return false;

    const id = (a.name + " " + a.bundle_id).toLowerCase();
    // Meeting/call apps
    if (/zoom|teams|meet|webex|slack|facetime|discord|skype|ringcentral|gotomeeting|whereby|around/i.test(id)) return true;
    // Browsers (for web-based meetings)
    if (/chrome|safari|firefox|edge|brave|arc|opera/i.test(id)) return true;
    // Media players (for testing/playback)
    if (/vlc|quicktime|music|spotify|podcast/i.test(id)) return true;
    return false;
  });

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto py-8 px-6 space-y-8">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-gray-100">
            Meeting Setup
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            Configure audio sources and upload disclosure documents before
            starting.
          </p>
        </div>

        {/* Audio Sources */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
              Audio Sources
            </h3>
            <button
              onClick={loadDevices}
              disabled={loadingDevices}
              className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1"
            >
              <RefreshCw
                className={`w-3 h-3 ${loadingDevices ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
          </div>

          {/* System Audio (Remote) */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                <Monitor className="w-5 h-5 text-blue-400" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-200">
                  System Audio
                  <span className="text-xs text-gray-500 ml-2">
                    Remote speakers
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  Captures audio output from your meeting app
                </div>
              </div>
              <VuMeter level={remoteLevel} />
            </div>

            <div className="relative">
              <select
                value={selectedApp ?? "__all__"}
                onChange={(e) =>
                  setSelectedApp(
                    e.target.value === "__all__" ? null : e.target.value
                  )
                }
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-3 pr-8 py-2.5 text-sm text-gray-200 appearance-none focus:outline-none focus:border-blue-500 transition-colors"
              >
                <option value="__all__">All System Audio</option>
                {relevantApps.map((a) => (
                  <option key={a.bundle_id} value={a.bundle_id}>
                    {a.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-gray-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          </div>

          {/* Microphone (Local) */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                  micEnabled ? "bg-green-500/10" : "bg-gray-700/50"
                }`}
              >
                {micEnabled ? (
                  <Mic className="w-5 h-5 text-green-400" />
                ) : (
                  <MicOff className="w-5 h-5 text-gray-500" />
                )}
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-200">
                  Microphone
                  <span className="text-xs text-gray-500 ml-2">
                    Your voice
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  {micEnabled
                    ? "Your speech will be transcribed"
                    : "Disabled — enable when in a live call"}
                </div>
              </div>
              <button
                onClick={() => setMicEnabled(!micEnabled)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  micEnabled ? "bg-green-600" : "bg-gray-600"
                }`}
              >
                <div
                  className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-sm ${
                    micEnabled ? "translate-x-[22px]" : "translate-x-0.5"
                  }`}
                />
              </button>
              {micEnabled && <VuMeter level={localLevel} />}
            </div>

            {micEnabled && (
              <div className="relative">
                <select
                  value={selectedMic ?? ""}
                  onChange={(e) =>
                    setSelectedMic(
                      e.target.value ? Number(e.target.value) : null
                    )
                  }
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-3 pr-8 py-2.5 text-sm text-gray-200 appearance-none focus:outline-none focus:border-green-500 transition-colors"
                >
                  <option value="">Default Microphone</option>
                  {microphones.map((m) => (
                    <option key={m.index} value={m.index}>
                      {m.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 text-gray-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
            )}
          </div>
        </section>

        {/* Documents */}
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
            Disclosure Documents
            <span className="text-xs font-normal text-gray-500 ml-2">
              Optional
            </span>
          </h3>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
              dragging
                ? "border-blue-400 bg-blue-400/5"
                : "border-gray-800 hover:border-gray-700"
            }`}
          >
            <Upload
              className={`w-10 h-10 mx-auto mb-3 ${
                dragging ? "text-blue-400" : "text-gray-600"
              }`}
            />
            <p className="text-sm text-gray-400 mb-1">
              {uploading
                ? "Uploading..."
                : "Drag & drop disclosure documents"}
            </p>
            <p className="text-xs text-gray-600 mb-4">
              PDF, DOCX, PPTX, or plain text — gives the AI context
            </p>
            <label className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 cursor-pointer transition-colors border border-gray-700">
              <input
                type="file"
                multiple
                accept=".pdf,.docx,.pptx,.txt,.md"
                onChange={handleFileInput}
                className="hidden"
              />
              Browse Files
            </label>
          </div>

          {documentNames.length > 0 && (
            <div className="space-y-2">
              {documentNames.map((name, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 text-sm text-gray-300 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2"
                >
                  <FileText className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <span className="truncate font-medium">{name}</span>
                  <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0 ml-auto" />
                </div>
              ))}
              {/* Capacity indicator */}
              {docCapacity && (
                <div>
                  <div className="flex justify-between text-[11px] text-gray-500 mb-1">
                    <span>Context usage</span>
                    <span>{Math.round((docCapacity.total / docCapacity.max) * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-1">
                    <div
                      className={`h-1 rounded-full transition-all ${
                        docCapacity.total / docCapacity.max > 0.8
                          ? "bg-red-400"
                          : docCapacity.total / docCapacity.max > 0.5
                            ? "bg-amber-400"
                            : "bg-green-400"
                      }`}
                      style={{
                        width: `${Math.min(100, (docCapacity.total / docCapacity.max) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Upload error */}
              {uploadError && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                  <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-300">{uploadError}</p>
                </div>
              )}

              <button
                onClick={() => {
                  fetch("/api/documents", { method: "DELETE" });
                  clearDocuments();
                  setAnalysis(null);
                  setUploadError(null);
                  setDocCapacity(null);
                }}
                className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-red-400 bg-gray-900 hover:bg-red-500/10 border border-gray-800 hover:border-red-500/20 rounded-lg px-3 py-1.5 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
                Clear documents
              </button>
            </div>
          )}
        </section>

        {/* Pre-Meeting Analysis */}
        {(analyzing || analysis) && (
          <section className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
              Pre-Meeting Analysis
            </h3>

            {analyzing ? (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <div className="flex items-center gap-3 mb-3">
                  <Brain className="w-5 h-5 text-purple-400 animate-pulse flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-300">
                      AI is reviewing your documents...
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {analyzeProgress < 50
                        ? "Reading and understanding the disclosure..."
                        : analyzeProgress < 80
                          ? "Identifying key elements and gaps..."
                          : "Generating questions — almost done..."}
                    </p>
                  </div>
                  <span className="text-xs text-purple-400 font-mono tabular-nums">
                    {analyzeProgress}%
                  </span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-1.5">
                  <div
                    className="bg-purple-500 h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${analyzeProgress}%` }}
                  />
                </div>
              </div>
            ) : analysis ? (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4">
                {analysis.summary && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 uppercase mb-1">
                      Invention Summary
                    </p>
                    <p className="text-sm text-gray-300">{analysis.summary}</p>
                    {analysis.technology_area && (
                      <span className="inline-block mt-1.5 text-xs bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded px-2 py-0.5">
                        {analysis.technology_area}
                      </span>
                    )}
                  </div>
                )}

                {analysis.top_questions && analysis.top_questions.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 uppercase mb-2">
                      Top Questions to Ask
                    </p>
                    <div className="space-y-2">
                      {analysis.top_questions.map((q, i) => (
                        <div
                          key={i}
                          className="flex gap-3 bg-gray-800/50 rounded-lg p-3"
                        >
                          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center">
                            {i + 1}
                          </span>
                          <div>
                            <p className="text-sm text-gray-200">
                              {q.question}
                            </p>
                            <p className="text-xs text-gray-500 mt-0.5">
                              {q.reason}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </section>
        )}

        {/* AI Model */}
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
            AI Suggestion Model
          </h3>

          {provider === "claude" ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-purple-400" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-200">
                    Claude API
                  </div>
                  <div className="text-xs text-gray-500">
                    Using Claude API for AI suggestions
                  </div>
                </div>
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-purple-400" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-200">
                    LM Studio
                  </div>
                  <div className="text-xs text-gray-500">
                    Local AI for suggestions — configure in Settings
                  </div>
                </div>
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              </div>
            </div>
          )}
        </section>

        {/* Start Button */}
        <div className="pt-2">
          <button
            onClick={onStartMeeting}
            disabled={!connected}
            className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-green-600 hover:bg-green-500 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-xl text-base font-semibold transition-colors shadow-lg shadow-green-600/20 disabled:shadow-none"
          >
            <Play className="w-5 h-5" />
            Start Meeting
          </button>
          {!connected && (
            <p className="text-xs text-red-400 text-center mt-2">
              Connecting to backend...
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
