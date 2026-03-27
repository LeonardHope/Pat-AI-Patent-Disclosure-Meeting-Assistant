import type { Suggestion } from "../types";
import {
  AlertTriangle,
  FileText,
  Lightbulb,
  Search,
  Zap,
  HelpCircle,
  BookOpen,
  Cpu,
  Shield,
  Expand,
  FlaskConical,
  X,
} from "lucide-react";

const CATEGORY_CONFIG: Record<
  string,
  { label: string; color: string; bg: string; icon: typeof Zap }
> = {
  BACKGROUND: { label: "Background", color: "text-blue-400", bg: "bg-blue-400/10 border-blue-400/20", icon: BookOpen },
  PRIOR_ART: { label: "Prior Art", color: "text-cyan-400", bg: "bg-cyan-400/10 border-cyan-400/20", icon: Search },
  TECHNICAL: { label: "Technical", color: "text-purple-400", bg: "bg-purple-400/10 border-purple-400/20", icon: Cpu },
  ENABLEMENT: { label: "Enablement (112)", color: "text-red-400", bg: "bg-red-400/10 border-red-400/20", icon: AlertTriangle },
  BEST_MODE: { label: "Best Mode", color: "text-amber-400", bg: "bg-amber-400/10 border-amber-400/20", icon: Zap },
  ELIGIBILITY: { label: "Eligibility (101)", color: "text-emerald-400", bg: "bg-emerald-400/10 border-emerald-400/20", icon: Shield },
  NON_OBVIOUS: { label: "Non-Obvious (103)", color: "text-orange-400", bg: "bg-orange-400/10 border-orange-400/20", icon: FlaskConical },
  SCOPE: { label: "Scope", color: "text-indigo-400", bg: "bg-indigo-400/10 border-indigo-400/20", icon: Expand },
  EXAMPLES: { label: "Examples", color: "text-teal-400", bg: "bg-teal-400/10 border-teal-400/20", icon: FileText },
  TECHNICAL_OVERVIEW: { label: "Technical", color: "text-purple-400", bg: "bg-purple-400/10 border-purple-400/20", icon: Cpu },
  TECHNICAL_DETAIL: { label: "Technical", color: "text-purple-400", bg: "bg-purple-400/10 border-purple-400/20", icon: Cpu },
  WRITTEN_DESCRIPTION: { label: "Written Desc.", color: "text-orange-400", bg: "bg-orange-400/10 border-orange-400/20", icon: FileText },
  CLAIM_ELEMENT: { label: "Claim Element", color: "text-purple-400", bg: "bg-purple-400/10 border-purple-400/20", icon: Lightbulb },
  FOLLOW_UP: { label: "Follow-up", color: "text-gray-400", bg: "bg-gray-400/10 border-gray-400/20", icon: HelpCircle },
};

const PRIORITY_STYLES: Record<string, string> = {
  HIGH: "border-l-red-400",
  MEDIUM: "border-l-amber-400",
  LOW: "border-l-gray-500",
};

interface SuggestionCardProps {
  suggestion: Suggestion;
  onDismiss?: (id: string) => void;
}

export function SuggestionCard({ suggestion, onDismiss }: SuggestionCardProps) {
  const config = CATEGORY_CONFIG[suggestion.category] ?? CATEGORY_CONFIG.FOLLOW_UP;
  const Icon = config.icon;

  return (
    <div
      className={`group border border-gray-700/50 rounded-lg p-3 border-l-4 ${
        PRIORITY_STYLES[suggestion.priority] ?? ""
      } transition-all hover:bg-gray-800/50 relative`}
    >
      {onDismiss && (
        <button
          onClick={() => onDismiss(suggestion.id)}
          className="absolute top-2 right-2 text-gray-700 hover:text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity"
          title="Dismiss"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
      <div className="flex items-center gap-2 mb-1.5">
        <span className={`inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded ${config.bg} ${config.color} border`}>
          <Icon className="w-3 h-3" />
          {config.label}
        </span>
        {suggestion.priority === "HIGH" && (
          <span className="text-xs text-red-400 font-semibold">HIGH</span>
        )}
      </div>
      <p className="text-sm text-gray-200 leading-relaxed pr-5">
        {suggestion.suggestion}
      </p>
      {suggestion.context && (
        <p className="text-xs text-gray-500 mt-1.5 italic">
          {suggestion.context}
        </p>
      )}
    </div>
  );
}
