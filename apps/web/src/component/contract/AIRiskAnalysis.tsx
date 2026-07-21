import { useState } from "react";
import type { ClauseView, RiskLevel } from "./types";
import { riskBadge, riskAcceptButton } from "./riskStyles";
import OverrideSidebar from "./OverrideSidebar";

interface AIRiskAnalysisProps {
  clause: ClauseView | null;
  /** Absent until a contract has been reviewed; disables override. */
  reportId?: string | null;
  onOverride?: (clauseId: string, newRisk: RiskLevel, reason: string) => Promise<void>;
  /** Reviewer has accepted this clause's assessment (local review progress). */
  accepted?: boolean;
  onAccept?: (clauseId: string) => void;
}

function EmptyPanel({ message, hint }: { message: string; hint: string }) {
  return (
    <div className="flex flex-col h-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl overflow-hidden shadow-2xl items-center justify-center">
      <div className="text-center space-y-3 px-8">
        <div className="text-5xl mb-4">🔍</div>
        <p className="text-slate-400 text-sm font-medium">{message}</p>
        <p className="text-slate-600 text-xs">{hint}</p>
      </div>
    </div>
  );
}

export default function AIRiskAnalysis({
  clause,
  reportId,
  onOverride,
  accepted = false,
  onAccept,
}: AIRiskAnalysisProps) {
  const [overrideSidebarOpen, setOverrideSidebarOpen] = useState(false);

  if (!clause) {
    return (
      <EmptyPanel
        message="Select a clause from the contract"
        hint="Click any clause to see the AI risk analysis"
      />
    );
  }

  const canOverride = Boolean(reportId && onOverride);

  return (
    <>
      <div className="flex flex-col h-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
        {/* Panel Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/5">
          <h2 className="text-base font-semibold text-slate-100 tracking-wide">
            AI Risk Analysis
          </h2>
          <span
            className={`text-xs font-bold px-3 py-1 rounded-full tracking-widest uppercase ${
              riskBadge[clause.riskLevel]
            }`}
          >
            {clause.riskLevel} RISK
          </span>
        </div>

        {/* Analysis Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {/* Clause Type */}
          <div className="space-y-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Clause Type
            </p>
            <div className="flex items-center gap-3 flex-wrap">
              <p className="text-xl font-bold text-slate-100">{clause.title}</p>
              {clause.page !== null && (
                <span className="text-xs text-slate-500">page {clause.page}</span>
              )}
              {/* The judge's grounding verdict — an ungrounded rationale is the
                  one thing a reviewer must not take at face value. */}
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest ${
                  clause.verified
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                    : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                }`}
                title={
                  clause.verified
                    ? "The rationale is grounded in the cited playbook text"
                    : "Not grounded against the playbook — verify manually"
                }
              >
                {clause.verified ? "Grounded" : "Unverified"}
              </span>
            </div>
          </div>

          {/* Excerpt */}
          <div className="space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Excerpt
            </p>
            <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
              <p className="text-sm text-slate-300 italic leading-relaxed">
                "{clause.excerpt}"
              </p>
            </div>
          </div>

          {/* AI Rationale */}
          <div className="space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              AI Rationale
            </p>
            <p className="text-sm text-slate-300 leading-relaxed">
              {clause.rationale || (
                <span className="text-slate-600 italic">No rationale returned.</span>
              )}
            </p>
          </div>

          {/* Suggested Fallback */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 bg-sky-500 rounded-full" />
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Suggested Fallback{" "}
                <span className="text-slate-600 normal-case font-normal">
                  (Retrieved from Playbook)
                </span>
              </p>
            </div>
            <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl p-4">
              <p className="text-sm text-slate-300 leading-relaxed">
                {clause.suggestedFallback ?? (
                  <span className="text-slate-600 italic">
                    No fallback language available for this clause.
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Citations */}
          <div className="space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Citations
            </p>
            {clause.citations.length === 0 ? (
              <p className="text-xs text-slate-600 italic">
                No playbook positions were cited for this clause.
              </p>
            ) : (
              <ul className="space-y-2">
                {clause.citations.map((citation) => (
                  <li
                    key={citation.id}
                    className="bg-slate-800/40 border border-slate-700/40 rounded-xl px-4 py-3 space-y-1.5"
                  >
                    <span className="text-xs bg-slate-700/60 border border-slate-600/40 text-slate-300 px-2.5 py-0.5 rounded-lg font-mono inline-block">
                      {citation.playbookPositionId}
                    </span>
                    <p className="text-xs text-slate-400 leading-relaxed italic">
                      "{citation.excerpt}"
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="px-6 py-4 border-t border-white/10 bg-white/5 grid grid-cols-2 gap-3">
          {/* Acceptance is local review progress — the backend has no accept
              endpoint, only override, so this deliberately claims nothing more. */}
          <button
            type="button"
            onClick={() => onAccept?.(clause.id)}
            disabled={accepted || !onAccept}
            className={`
              py-3 rounded-xl text-sm font-semibold
              transition-all duration-200 ease-in-out
              shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95
              disabled:cursor-default disabled:hover:scale-100 disabled:shadow-none
              ${
                accepted
                  ? "bg-slate-700/60 text-slate-400 border border-slate-600"
                  : riskAcceptButton[clause.riskLevel]
              }
            `}
          >
            {accepted ? "✓ Accepted" : "Accept Risk"}
          </button>
          <button
            type="button"
            onClick={() => setOverrideSidebarOpen(true)}
            disabled={!canOverride}
            className="
              py-3 rounded-xl text-sm font-semibold
              border border-slate-600 text-slate-300
              hover:bg-slate-700/50 hover:text-white hover:border-slate-500
              transition-all duration-200 ease-in-out
              hover:shadow-lg hover:scale-[1.02] active:scale-95
              disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100
            "
          >
            Override Risk
          </button>
        </div>
      </div>

      {/* Override Sidebar — rendered outside the panel so it overlays the full page.
          Keyed by clause so switching clauses resets the form by remounting. */}
      {reportId && onOverride && (
        <OverrideSidebar
          key={clause.id}
          isOpen={overrideSidebarOpen}
          clause={clause}
          onClose={() => setOverrideSidebarOpen(false)}
          onSubmit={(newRisk, reason) => onOverride(clause.id, newRisk, reason)}
        />
      )}
    </>
  );
}
