import { useState, useEffect, useRef } from "react";
import { useMeetingStore } from "../stores/meetingStore";
import { Sparkles, FileSearch, ChevronDown, ChevronRight, X } from "lucide-react";
import type { Suggestion } from "../types";

interface SuggestionPanelProps {
  preCallQuestions?: { question: string; reason: string }[];
}

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  "Pre-Meeting": { label: "Pre-Meeting Analysis", color: "text-purple-400 border-purple-400/30" },
  BACKGROUND: { label: "Background", color: "text-blue-400 border-blue-400/30" },
  PRIOR_ART: { label: "Prior Art", color: "text-cyan-400 border-cyan-400/30" },
  TECHNICAL: { label: "Technical", color: "text-purple-400 border-purple-400/30" },
  ENABLEMENT: { label: "Enablement (112)", color: "text-red-400 border-red-400/30" },
  BEST_MODE: { label: "Best Mode", color: "text-amber-400 border-amber-400/30" },
  ELIGIBILITY: { label: "Patent Eligibility (101)", color: "text-emerald-400 border-emerald-400/30" },
  NON_OBVIOUS: { label: "Non-Obviousness (103)", color: "text-orange-400 border-orange-400/30" },
  SCOPE: { label: "Scope & Alternatives", color: "text-indigo-400 border-indigo-400/30" },
  EXAMPLES: { label: "Examples & Figures", color: "text-teal-400 border-teal-400/30" },
  // Legacy
  TECHNICAL_OVERVIEW: { label: "Technical", color: "text-purple-400 border-purple-400/30" },
  TECHNICAL_DETAIL: { label: "Technical", color: "text-purple-400 border-purple-400/30" },
  CLAIM_ELEMENT: { label: "Claim Elements", color: "text-purple-400 border-purple-400/30" },
  WRITTEN_DESCRIPTION: { label: "Written Description", color: "text-orange-400 border-orange-400/30" },
  FOLLOW_UP: { label: "Follow-up", color: "text-gray-400 border-gray-400/30" },
};

interface CategoryGroup {
  category: string;
  suggestions: Suggestion[];
  isPreMeeting?: boolean;
  collapsed?: boolean;
}

export function SuggestionPanel({ preCallQuestions }: SuggestionPanelProps) {
  const suggestions = useMeetingStore((s) => s.suggestions);
  const dismissedIds = useMeetingStore((s) => s.dismissedIds);
  const dismissSuggestion = useMeetingStore((s) => s.dismissSuggestion);
  const state = useMeetingStore((s) => s.state);
  const [groups, setGroups] = useState<CategoryGroup[]>([]);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);

  // Build pre-meeting group
  const preGroup: CategoryGroup | null =
    preCallQuestions && preCallQuestions.length > 0
      ? {
          category: "Pre-Meeting",
          isPreMeeting: true,
          suggestions: preCallQuestions.map((q, i) => ({
            id: `pre-${i}`,
            category: "Pre-Meeting" as any,
            priority: "HIGH" as const,
            suggestion: q.question,
            context: q.reason,
            timestamp: 0,
          })),
        }
      : null;

  // Accumulate suggestion groups over time
  useEffect(() => {
    if (suggestions.length === 0) return;

    // Filter out dismissed suggestions, then group by category
    const activeSuggestions = suggestions.filter((s) => !dismissedIds.has(s.id));
    const newGroupMap: Record<string, Suggestion[]> = {};
    for (const s of activeSuggestions) {
      const cat = s.category || "FOLLOW_UP";
      if (!newGroupMap[cat]) newGroupMap[cat] = [];
      newGroupMap[cat].push(s);
    }

    setGroups((prev) => {
      const updated = [...prev];

      for (const [cat, catSuggestions] of Object.entries(newGroupMap)) {
        const existing = updated.find((g) => g.category === cat);
        if (existing) {
          // Update existing group with new suggestions
          existing.suggestions = catSuggestions;
        } else {
          // New category — add it
          updated.push({ category: cat, suggestions: catSuggestions });
        }
      }

      return updated;
    });

    // Scroll to bottom when new groups appear
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  }, [suggestions, dismissedIds]);

  // Reset groups when meeting resets
  useEffect(() => {
    if (state === "idle") {
      setGroups([]);
      setCollapsedGroups(new Set());
    }
  }, [state]);

  const toggleCollapse = (category: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  };

  // Active meeting with groups
  if (state === "active" && (groups.length > 0 || preGroup)) {
    const allGroups = preGroup ? [preGroup, ...groups] : groups;

    return (
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {allGroups.map((group) => {
          const config = CATEGORY_LABELS[group.category] ?? {
            label: group.category,
            color: "text-gray-400 border-gray-400/30",
          };
          const isCollapsed = collapsedGroups.has(group.category);
          const isLatest = group === allGroups[allGroups.length - 1];

          return (
            <div key={group.category}>
              {/* Category header */}
              <button
                onClick={() => toggleCollapse(group.category)}
                className={`flex items-center gap-2 w-full text-left mb-2 group`}
              >
                {isCollapsed ? (
                  <ChevronRight className="w-3.5 h-3.5 text-gray-600" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 text-gray-600" />
                )}
                <span
                  className={`text-xs font-semibold uppercase tracking-wider ${config.color.split(" ")[0]}`}
                >
                  {config.label}
                </span>
                <span className="text-[10px] text-gray-600">
                  {group.suggestions.length}
                </span>
                {!isLatest && !isCollapsed && (
                  <span className="text-[10px] text-gray-700 ml-auto">
                    earlier
                  </span>
                )}
              </button>

              {/* Suggestions */}
              {!isCollapsed && (
                <div
                  className={`space-y-2 ${!isLatest ? "opacity-50" : ""}`}
                >
                  {group.suggestions.filter((s) => !dismissedIds.has(s.id)).map((s, i) => (
                    <div
                      key={s.id}
                      className={`group/card border border-gray-700/50 rounded-lg p-3 border-l-4 ${
                        config.color.split(" ")[1] ?? "border-l-gray-500"
                      } transition-all hover:bg-gray-800/50 relative`}
                    >
                      <button
                        onClick={() => dismissSuggestion(s.id)}
                        className="absolute top-2 right-2 text-gray-700 hover:text-gray-400 opacity-0 group-hover/card:opacity-100 transition-opacity"
                        title="Dismiss"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                      <p className="text-sm text-gray-200 leading-relaxed pr-5">
                        {s.suggestion}
                      </p>
                      {s.context && (
                        <p className="text-xs text-gray-500 mt-1.5 italic">
                          {s.context}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    );
  }

  // Active meeting, waiting for suggestions
  if (state === "active") {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-500 text-sm px-6 gap-3">
        <Sparkles className="w-8 h-8 text-gray-600 animate-pulse" />
        <div className="text-center">
          Listening to the conversation...
          <br />
          Suggestions will appear as the discussion develops.
        </div>
      </div>
    );
  }

  // Not in a meeting
  return (
    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm px-6 text-center">
      AI suggestions will appear here during the meeting.
      <br />
      Suggestions are grouped by meeting phase and accumulate over time.
    </div>
  );
}
