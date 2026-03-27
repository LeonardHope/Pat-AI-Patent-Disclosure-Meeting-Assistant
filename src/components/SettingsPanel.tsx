import { useState, useEffect } from "react";
import { useMeetingStore } from "../stores/meetingStore";
import { X, FileCode, CheckCircle2, AlertCircle } from "lucide-react";
import { PromptEditor } from "./PromptEditor";

export function SettingsPanel() {
  const showSettings = useMeetingStore((s) => s.showSettings);
  const setShowSettings = useMeetingStore((s) => s.setShowSettings);
  const [provider, setProvider] = useState("lmstudio");
  const [lmstudioUrl, setLmstudioUrl] = useState("http://localhost:1234");
  const [lmstudioModel, setLmstudioModel] = useState("");
  const [claudeKey, setClaudeKey] = useState("");
  const [claudeModel, setClaudeModel] = useState("claude-haiku-4-5-20251001");
  const [maxSuggestions, setMaxSuggestions] = useState(5);
  const [captureMic, setCaptureMic] = useState(false);
  const [promptEditorOpen, setPromptEditorOpen] = useState(false);
  const [llmAvailable, setLlmAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    if (showSettings) {
      fetch("/api/settings")
        .then((r) => r.json())
        .then((data) => {
          setProvider(data.llm.provider);
          setLmstudioUrl(data.llm.lmstudio_base_url || "http://localhost:1234");
          setLmstudioModel(data.llm.lmstudio_model || "");
          setClaudeKey(data.llm.claude_api_key);
          setClaudeModel(data.llm.claude_model || "claude-haiku-4-5-20251001");
          setMaxSuggestions(data.suggestions.max_suggestions);
          setCaptureMic(data.audio?.capture_microphone ?? false);
        });
      fetch("/api/llm/status")
        .then((r) => r.json())
        .then((data) => setLlmAvailable(data.available))
        .catch(() => setLlmAvailable(false));
    }
  }, [showSettings]);

  const saveSettings = async () => {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        llm: {
          provider,
          lmstudio_base_url: lmstudioUrl,
          lmstudio_model: lmstudioModel,
          claude_api_key: claudeKey,
          claude_model: claudeModel,
        },
        suggestions: { max_suggestions: maxSuggestions },
        audio: { capture_microphone: captureMic },
      }),
    });
    setShowSettings(false);
  };

  if (!showSettings) return null;

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold">Settings</h2>
          <button
            onClick={() => setShowSettings(false)}
            className="text-gray-400 hover:text-gray-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-6">
          {/* LLM Provider */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              AI Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            >
              <option value="lmstudio">LM Studio (Local, Private)</option>
              <option value="claude">Claude API (Cloud)</option>
            </select>
          </div>

          {/* LM Studio settings */}
          {provider === "lmstudio" && (
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  LM Studio URL
                </label>
                <input
                  type="text"
                  value={lmstudioUrl}
                  onChange={(e) => setLmstudioUrl(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
                  placeholder="http://localhost:1234"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Model
                  <span className="text-xs text-gray-500 ml-2">
                    Leave blank to use whatever is loaded
                  </span>
                </label>
                <input
                  type="text"
                  value={lmstudioModel}
                  onChange={(e) => setLmstudioModel(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
                  placeholder="(uses loaded model)"
                />
              </div>

              {llmAvailable !== null && (
                <div className={`flex items-center gap-2 text-xs ${llmAvailable ? "text-green-400" : "text-amber-400"}`}>
                  {llmAvailable ? (
                    <><CheckCircle2 className="w-3.5 h-3.5" /> Connected to LM Studio</>
                  ) : (
                    <><AlertCircle className="w-3.5 h-3.5" /> LM Studio not detected — make sure it's running with a model loaded</>
                  )}
                </div>
              )}

              <p className="text-xs text-gray-600">
                Load a model in LM Studio, then start the local server.
                Uses the Anthropic-compatible endpoint.
              </p>
            </div>
          )}

          {/* Claude settings */}
          {provider === "claude" && (
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Anthropic API Key
                </label>
                <input
                  type="password"
                  value={claudeKey}
                  onChange={(e) => setClaudeKey(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
                  placeholder="sk-ant-..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Model
                </label>
                <select
                  value={claudeModel}
                  onChange={(e) => setClaudeModel(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
                >
                  <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5 (fastest, ~$0.70/hr)</option>
                  <option value="claude-sonnet-4-6-20260407">Claude Sonnet 4.6 (balanced)</option>
                  <option value="claude-opus-4-6-20260407">Claude Opus 4.6 (best quality)</option>
                </select>
              </div>

              <p className="text-xs text-amber-400/60">
                Transcript data will be sent to Anthropic's API.
              </p>
            </div>
          )}

          {/* Suggestion settings */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Max Suggestions ({maxSuggestions})
            </label>
            <input
              type="range"
              min={3}
              max={10}
              value={maxSuggestions}
              onChange={(e) => setMaxSuggestions(Number(e.target.value))}
              className="w-full"
            />
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              AI System Prompt
            </label>
            <button
              onClick={() => setPromptEditorOpen(true)}
              className="w-full flex items-center gap-2 px-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 hover:bg-gray-700 transition-colors text-left"
            >
              <FileCode className="w-4 h-4 text-gray-500 flex-shrink-0" />
              <span className="flex-1">
                View & edit the prompt that controls AI suggestions
              </span>
            </button>
          </div>

          {/* Disclaimer */}
          <div className="text-xs text-gray-500 border-t border-gray-800 pt-4">
            Recording meetings may require consent from all parties depending
            on your jurisdiction. Ensure you comply with applicable laws.
          </div>
        </div>

        <div className="p-4 border-t border-gray-800 flex justify-end gap-2">
          <button
            onClick={() => setShowSettings(false)}
            className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200"
          >
            Cancel
          </button>
          <button
            onClick={saveSettings}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm"
          >
            Save
          </button>
        </div>
      </div>
      <PromptEditor
        open={promptEditorOpen}
        onClose={() => setPromptEditorOpen(false)}
      />
    </div>
  );
}
