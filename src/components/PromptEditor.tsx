import { useState, useEffect } from "react";
import { X, RotateCcw, Save } from "lucide-react";

interface PromptEditorProps {
  open: boolean;
  onClose: () => void;
}

export function PromptEditor({ open, onClose }: PromptEditorProps) {
  const [prompt, setPrompt] = useState("");
  const [original, setOriginal] = useState("");
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (open) {
      fetch("/api/prompt")
        .then((r) => r.json())
        .then((data) => {
          setPrompt(data.prompt);
          setOriginal(data.prompt);
          setDirty(false);
        });
    }
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch("/api/prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      setOriginal(prompt);
      setDirty(false);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    // Reload from server (which has the original default)
    const r = await fetch("/api/prompt");
    const data = await r.json();
    setPrompt(data.prompt);
    setDirty(data.prompt !== original);
  };

  if (!open) return null;

  const lines = prompt.split("\n").length;

  return (
    <div className="fixed inset-0 bg-black/70 z-[60] flex items-center justify-center p-6">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div>
            <h2 className="text-lg font-semibold">System Prompt</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Controls how the AI generates suggestions during meetings
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden p-4">
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              setDirty(e.target.value !== original);
            }}
            className="w-full h-full min-h-[400px] bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-200 font-mono leading-relaxed resize-none focus:outline-none focus:border-blue-500 transition-colors"
            spellCheck={false}
          />
        </div>

        <div className="flex items-center justify-between p-4 border-t border-gray-800">
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-600">
              {lines} lines, {prompt.length} chars
            </span>
            {dirty && (
              <span className="text-xs text-amber-400">Unsaved changes</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!dirty || saving}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
