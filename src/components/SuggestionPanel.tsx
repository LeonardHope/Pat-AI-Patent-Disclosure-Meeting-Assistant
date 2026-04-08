import { useState, useEffect, useRef } from "react";
import { useMeetingStore } from "../stores/meetingStore";
import { Sparkles, FileSearch, ChevronDown, ChevronRight, X } from "lucide-react";
import type { Suggestion } from "../types";

const CATEGORY_COLORS: Record<string, string> = {
  BACKGROUND: "text-blue-400",
  PRIOR_ART: "text-cyan-400",
  TECHNICAL: "text-purple-400",
  ENABLEMENT: "text-red-400",
  BEST_MODE: "text-amber-400",
  ELIGIBILITY: "text-emerald-400",
  NON_OBVIOUS: "text-orange-400",
  SCOPE: "text-indigo-400",
  EXAMPLES: "text-teal-400",
};

const CATEGORY_LABELS: Record<string, string> = {
  BACKGROUND: "Background",
  PRIOR_ART: "Prior Art",
  TECHNICAL: "Technical",
  ENABLEMENT: "112",
  BEST_MODE: "Best Mode",
  ELIGIBILITY: "101",
  NON_OBVIOUS: "103",
  SCOPE: "Scope",
  EXAMPLES: "Examples",
};

interface SuggestionPanelProps {
  preCallQuestions?: { question: string; reason: string }[];
}

const TOP_COUNT = 3;

export function SuggestionPanel({ preCallQuestions }: SuggestionPanelProps) {
  const suggestions = useMeetingStore((s) => s.suggestions);
  const dismissedIds = useMeetingStore((s) => s.dismissedIds);
  const dismissSuggestion = useMeetingStore((s) => s.dismissSuggestion);
  const state = useMeetingStore((s) => s.state);

  // Stable top 3: only changes on dismiss or when a suggestion is no longer
  // in the LLM's output (topic was addressed)
  const [pinnedIds, setPinnedIds] = useState<string[]>([]);
  const [showMore, setShowMore] = useState(false);

  const activeSuggestions = suggestions.filter((s) => !dismissedIds.has(s.id));

  useEffect(() => {
    if (activeSuggestions.length === 0) return;

    setPinnedIds((prev) => {
      // Keep currently pinned IDs that are still active
      const stillActive = prev.filter(
        (id) => activeSuggestions.some((s) => s.id === id) && !dismissedIds.has(id)
      );

      // Fill empty slots from new suggestions (in priority order)
      const pinned = [...stillActive];
      for (const s of activeSuggestions) {
        if (pinned.length >= TOP_COUNT) break;
        if (!pinned.includes(s.id)) {
          pinned.push(s.id);
        }
      }

      return pinned;
    });
  }, [activeSuggestions.map((s) => s.id).join(","), dismissedIds]);

  // Reset on new meeting
  useEffect(() => {
    if (state === "idle") {
      setPinnedIds([]);
      setShowMore(false);
    }
  }, [state]);

  const pinnedSuggestions = pinnedIds
    .map((id) => activeSuggestions.find((s) => s.id === id))
    .filter(Boolean) as Suggestion[];

  const queuedSuggestions = activeSuggestions.filter(
    (s) => !pinnedIds.includes(s.id)
  );

  // Show pre-meeting questions before live suggestions arrive
  if (state === "active" && pinnedSuggestions.length === 0 && preCallQuestions && preCallQuestions.length > 0) {
    return (
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
          From document analysis
        </div>
        {preCallQuestions.map((q, i) => (
          <div key={i} className="border-l-4 border-purple-400/30 pl-4 py-2">
            <p className="text-base text-gray-200 leading-relaxed">{q.question}</p>
          </div>
        ))}
        <div className="flex items-center justify-center gap-2 text-xs text-gray-600 pt-4">
          <Sparkles className="w-3 h-3 animate-pulse" />
          Live suggestions will appear as the conversation develops
        </div>
      </div>
    );
  }

  // Active meeting with suggestions
  if (state === "active" && pinnedSuggestions.length > 0) {
    return (
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {/* Top 3 — large, stable */}
        <div className="space-y-5">
          {pinnedSuggestions.map((s, i) => {
            const catColor = CATEGORY_COLORS[s.category] ?? "text-gray-400";
            const catLabel = CATEGORY_LABELS[s.category] ?? s.category;

            return (
              <div key={s.id} className="group/card relative">
                <button
                  onClick={() => dismissSuggestion(s.id)}
                  className="absolute top-0 right-0 text-gray-700 hover:text-gray-400 opacity-0 group-hover/card:opacity-100 transition-opacity"
                  title="Dismiss"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`text-xs font-semibold uppercase tracking-wider ${catColor}`}>
                    {catLabel}
                  </span>
                </div>
                <p className="text-base text-gray-100 leading-relaxed pr-6">
                  {s.suggestion}
                </p>
              </div>
            );
          })}
        </div>

        {/* Queue — collapsed, smaller */}
        {queuedSuggestions.length > 0 && (
          <div className="mt-6 pt-4 border-t border-gray-800/50">
            <button
              onClick={() => setShowMore(!showMore)}
              className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-400 transition-colors w-full"
            >
              {showMore ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
              More suggestions ({queuedSuggestions.length})
            </button>

            {showMore && (
              <div className="mt-3 space-y-3">
                {queuedSuggestions.map((s) => {
                  const catColor = CATEGORY_COLORS[s.category] ?? "text-gray-400";
                  const catLabel = CATEGORY_LABELS[s.category] ?? s.category;

                  return (
                    <div key={s.id} className="group/card relative opacity-60">
                      <button
                        onClick={() => dismissSuggestion(s.id)}
                        className="absolute top-0 right-0 text-gray-700 hover:text-gray-400 opacity-0 group-hover/card:opacity-100 transition-opacity"
                        title="Dismiss"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                      <span className={`text-[10px] font-semibold uppercase tracking-wider ${catColor}`}>
                        {catLabel}
                      </span>
                      <p className="text-sm text-gray-300 leading-relaxed pr-5">
                        {s.suggestion}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Active meeting, waiting
  if (state === "active") {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-500 px-6 gap-3">
        <Sparkles className="w-8 h-8 text-gray-600 animate-pulse" />
        <p className="text-sm text-center">
          Listening to the conversation...
        </p>
      </div>
    );
  }

  // Idle
  return (
    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm px-6 text-center">
      AI suggestions will appear here during the meeting.
    </div>
  );
}
