import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, ShieldAlert } from "lucide-react";
import type { ClauseView, RiskLevel } from "./types";
import { riskBadge, riskAcceptButton } from "./riskStyles";
import OverrideSidebar from "./OverrideSidebar";
import {
  setClauseDecisionState,
  useContractUiState,
} from "./contractUiStore.ts";

interface AIRiskAnalysisProps {
  clause: ClauseView | null;
  /** Absent until a contract has been reviewed; disables override. */
  reportId?: string | null;
  onOverride?: (clauseId: string, newRisk: RiskLevel, reason: string) => Promise<void>;
  /**
   * Record or withdraw the reviewer's sign-off on this clause.
   *
   * Whether the clause *is* accepted comes from the clause itself — it is
   * stored on the report — so there is no separate prop that could disagree
   * with it.
   */
  onAccept?: (clauseId: string, accepted: boolean) => Promise<void>;
}

function EmptyPanel({ message, hint }: { message: string; hint: string }) {
  return (
    <div className="flex h-full items-center justify-center rounded-2xl border border-navy-700 bg-navy-900/60 shadow-2xl backdrop-blur-sm">
      <div className="text-center space-y-3 px-8">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-navy-700 bg-navy-800 text-navy-300">
          <ShieldAlert className="h-6 w-6" />
        </div>
        <p className="text-sm font-medium text-slate-200">{message}</p>
        <p className="text-xs text-slate-400">{hint}</p>
      </div>
    </div>
  );
}

function riskIcon(level: RiskLevel) {
  switch (level) {
    case "HIGH":
      return <AlertTriangle className="h-3.5 w-3.5" />;
    case "MEDIUM":
      return <Info className="h-3.5 w-3.5" />;
    case "LOW":
      return <CheckCircle2 className="h-3.5 w-3.5" />;
    case "UNKNOWN":
    default:
      return <Info className="h-3.5 w-3.5" />;
  }
}

export default function AIRiskAnalysis({
  clause,
  reportId,
  onOverride,
  onAccept,
}: AIRiskAnalysisProps) {
  const [overrideSidebarOpen, setOverrideSidebarOpen] = useState(false);
  const [overrideConfirmOpen, setOverrideConfirmOpen] = useState(false);
  /** Accepting is a round trip now, so the button has to say it's mid-flight. */
  const [accepting, setAccepting] = useState(false);
  const [expandedRationale, setExpandedRationale] = useState(false);
  const [canExpandRationale, setCanExpandRationale] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const rationaleMeasureRef = useRef<HTMLDivElement>(null);
  const { clauses, decisionStates } = useContractUiState();

  const progress = useMemo(() => {
    const total = clauses.length;
    const reviewed = clauses.filter((item) => item.accepted || decisionStates[item.id]).length;
    return { total, reviewed };
  }, [clauses, decisionStates]);

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    setExpandedRationale(false);
  }, [clause?.id]);

  useEffect(() => {
    const element = rationaleMeasureRef.current;
    if (!element) {
      setCanExpandRationale(false);
      return;
    }

    const update = () => {
      setCanExpandRationale(element.scrollHeight > element.clientHeight + 2);
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [clause?.rationale]);

  const acceptLabel = clause && (clause.accepted ? "✓ Accepted — Undo" : "Accept Risk");

  const handleAccept = async () => {
    if (!clause || !onAccept) return;
    const nextAccepted = !clause.accepted;
    setAccepting(true);
    try {
      await onAccept(clause.id, nextAccepted);
      setClauseDecisionState(clause.id, nextAccepted ? "accepted" : null);
    } finally {
      setAccepting(false);
    }
  };

  const confirmOverride = () => {
    setOverrideConfirmOpen(false);
    setOverrideSidebarOpen(true);
  };

  const renderRiskBadge = (level: RiskLevel) => (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full tracking-widest uppercase ${
        riskBadge[level]
      }`}
      aria-label={`${level} risk`}
    >
      {riskIcon(level)}
      <span>{level} RISK</span>
    </span>
  );

  if (!clause) {
    return (
      <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-navy-700 bg-navy-900/60 shadow-2xl backdrop-blur-sm">
        <div className="flex items-center justify-between border-b border-navy-800 bg-navy-900/60 px-6 py-4">
          <div className="space-y-1">
            <h2 className="text-base font-semibold tracking-wide text-slate-100">
              AI Risk Analysis
            </h2>
            <p className="text-xs text-slate-400">
              Reviewed {progress.reviewed}/{progress.total || 0} clauses
            </p>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
            Select a clause
          </span>
        </div>

        <div className="flex-1 p-6">
          <EmptyPanel
            message="Select a clause from the contract"
            hint="Click any clause on the left to see the AI risk analysis"
          />
        </div>
      </div>
    );
  }

  const canOverride = Boolean(reportId && onOverride);

  const decisionLabel = decisionStates[clause.id] ?? (clause.accepted ? "accepted" : null);

  const rationaleText = clause.rationale || "No rationale returned.";

  return (
    <>
      <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-navy-700 bg-navy-900/60 shadow-2xl backdrop-blur-sm">
        {/* Panel Header */}
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-navy-800 bg-navy-900/60 px-6 py-4">
          <div className="space-y-1 min-w-0">
            <h2 className="text-base font-semibold tracking-wide text-slate-100">
              AI Risk Analysis
            </h2>
            <p className="text-xs text-slate-400">
              Reviewed {progress.reviewed}/{progress.total || 0} clauses
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            {renderRiskBadge(clause.riskLevel)}
            <div className="h-1.5 w-28 overflow-hidden rounded-full bg-navy-800">
              <div
                className="h-full rounded-full bg-navy-400 transition-all duration-300"
                style={{
                  width: progress.total ? `${Math.max((progress.reviewed / progress.total) * 100, 6)}%` : "0%",
                }}
              />
            </div>
          </div>
        </div>

        {/* Analysis Content */}
        <div ref={contentRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
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
              {decisionLabel && (
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest ${
                    decisionLabel === "accepted"
                      ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                      : "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                  }`}
                >
                  {decisionLabel === "accepted" ? "Accepted" : "Overridden"}
                </span>
              )}
              {/* The judge's grounding verdict — an ungrounded rationale is the
                  one thing a reviewer must not take at face value. */}
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest ${
                  clause.verified
                    ? "bg-navy-500/20 text-navy-300 border border-navy-500/40"
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
            <div className="bg-navy-800/60 border border-navy-700/50 rounded-xl p-4">
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
            <div className="space-y-2">
              <div
                ref={rationaleMeasureRef}
                className={`overflow-hidden text-sm text-slate-300 leading-relaxed transition-all duration-200 ${
                  expandedRationale ? "max-h-none" : "max-h-24"
                }`}
              >
                <p>{rationaleText}</p>
              </div>
              {canExpandRationale && (
                <button
                  type="button"
                  onClick={() => setExpandedRationale((current) => !current)}
                  className="text-xs font-medium text-navy-200 hover:text-navy-100 transition-colors"
                >
                  {expandedRationale ? "ย่อ" : "อ่านเพิ่มเติม"}
                </button>
              )}
            </div>
          </div>

          {/* Suggested Fallback */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 bg-navy-500 rounded-full" />
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Suggested Fallback{" "}
                <span className="text-slate-500 normal-case font-normal">
                  (Retrieved from Playbook)
                </span>
              </p>
            </div>
            <div className="bg-navy-800/40 border border-navy-700/40 rounded-xl p-4">
              <p className="text-sm text-slate-300 leading-relaxed">
                {clause.suggestedFallback ?? (
                  <span className="text-slate-500 italic">
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
              <p className="text-xs text-slate-500 italic">
                No playbook positions were cited for this clause.
              </p>
            ) : (
              <ul className="space-y-2">
                {clause.citations.map((citation) => (
                  <li
                    key={citation.id}
                    className="bg-navy-800/40 border border-navy-700/40 rounded-xl px-4 py-3 space-y-1.5"
                  >
                    <span className="text-xs bg-navy-700/60 border border-navy-600/40 text-slate-300 px-2.5 py-0.5 rounded-lg font-mono inline-block">
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

        {/* Who signed off, once someone has. A ✓ with no name is a claim
            nobody is attached to, which is the opposite of an audit trail. */}
        {clause.accepted && clause.acceptedBy && (
          <div className="px-6 py-2 border-t border-navy-800 bg-emerald-950/20">
            <p className="text-xs text-emerald-300/80">
              ✓ Accepted by {clause.acceptedBy}
              {clause.acceptedAt && ` · ${new Date(clause.acceptedAt).toLocaleString()}`}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="px-6 py-4 border-t border-navy-800 bg-navy-900/60 grid grid-cols-2 gap-3">
          {/* Sign-off is persisted (POST /contracts/{id}/accept) and reversible
              — clicking again withdraws it, which is also audited. */}
          <button
            type="button"
            onClick={handleAccept}
            disabled={accepting || !onAccept}
            title={clause.accepted ? "Withdraw your sign-off on this clause" : undefined}
            className={`
              py-3 rounded-xl text-sm font-semibold
              transition-all duration-200 ease-in-out
              shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95
              disabled:cursor-default disabled:hover:scale-100 disabled:shadow-none
              ${
                clause.accepted
                  ? "bg-navy-700/60 text-slate-400 border border-navy-600"
                  : riskAcceptButton[clause.riskLevel]
              }
            `}
          >
            {accepting ? "Saving…" : acceptLabel}
          </button>
          <button
            type="button"
            onClick={() => setOverrideConfirmOpen(true)}
            disabled={!canOverride}
            className="
              py-3 rounded-xl text-sm font-semibold
              border border-navy-600 text-slate-300
              hover:bg-navy-700/50 hover:text-white hover:border-navy-500
              transition-all duration-200 ease-in-out
              hover:shadow-lg hover:scale-[1.02] active:scale-95
              disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100
            "
          >
            Override Risk
          </button>
        </div>
      </div>

      {overrideConfirmOpen && (
        <div className="fixed inset-0 z-40 bg-navy-950/70 backdrop-blur-sm flex items-center justify-center px-4">
          <div className="w-full max-w-md rounded-2xl border border-navy-700 bg-navy-900/95 shadow-2xl shadow-navy-950/70">
            <div className="border-b border-navy-800 px-6 py-5">
              <p className="text-xs uppercase tracking-[0.2em] text-navy-300 mb-1">
                Confirm action
              </p>
              <h3 className="text-lg font-semibold text-white">Override risk?</h3>
            </div>
            <div className="px-6 py-5 space-y-3">
              <p className="text-sm leading-relaxed text-slate-300">
                This will open the override form and record a new risk assessment for{" "}
                <span className="text-slate-100 font-medium">{clause.title}</span>.
              </p>
              <p className="text-xs text-slate-400 leading-relaxed">
                Use this only if you have a clear reviewer reason. The original assessment will
                remain available in the audit trail.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 border-t border-navy-800 px-6 py-4">
              <button
                type="button"
                onClick={() => setOverrideConfirmOpen(false)}
                className="rounded-xl border border-navy-600 px-4 py-3 text-sm font-semibold text-slate-300 transition-all hover:bg-navy-700/50 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmOverride}
                className="rounded-xl bg-amber-600 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-amber-500"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Override Sidebar — rendered outside the panel so it overlays the full page.
          Keyed by clause so switching clauses resets the form by remounting. */}
      {reportId && onOverride && (
        <OverrideSidebar
          key={clause.id}
          isOpen={overrideSidebarOpen}
          clause={clause}
          onClose={() => setOverrideSidebarOpen(false)}
          onSubmit={async (newRisk, reason) => {
            await onOverride(clause.id, newRisk, reason);
            setClauseDecisionState(clause.id, "overridden");
          }}
        />
      )}
    </>
  );
}
