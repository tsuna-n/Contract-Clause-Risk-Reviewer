import { useEffect, useRef, useState } from "react";
import type { ClauseView, RiskLevel } from "./types";
import { OVERRIDE_RISK_LEVELS } from "./types";
import { riskBadge } from "./riskStyles";

interface OverrideSidebarProps {
  isOpen: boolean;
  clause: ClauseView;
  onClose: () => void;
  /** Resolves once the backend has accepted the override. */
  onSubmit: (newRisk: RiskLevel, reason: string) => Promise<void>;
}

/**
 * OverrideSidebar — human-in-the-loop risk override.
 *
 * The backend records the actor from the bearer token, so this form only
 * collects what `POST /contracts/{id}/override` actually accepts: the new
 * risk level and a reason.
 *
 * Parents mount this with `key={clause.id}` so switching clauses resets the
 * form by remounting rather than by writing state from an effect.
 */
export default function OverrideSidebar({
  isOpen,
  clause,
  onClose,
  onSubmit,
}: OverrideSidebarProps) {
  const [newRisk, setNewRisk] = useState<RiskLevel>(clause.riskLevel);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const sidebarRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (isOpen) sidebarRef.current?.focus();
  }, [isOpen]);

  // Escape closes the panel, as expected of a modal dialog.
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onClose]);

  const trimmedReason = reason.trim();
  const unchanged = newRisk === clause.riskLevel;
  const canSubmit = trimmedReason.length > 0 && !unchanged && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(newRisk, trimmedReason);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Override failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* ── Backdrop ────────────────────────────────────────────────────────── */}
      <div
        onClick={onClose}
        className={`
          fixed inset-0 z-40 bg-black/50 backdrop-blur-sm
          transition-opacity duration-300
          ${isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}
        `}
        aria-hidden="true"
      />

      {/* ── Sidebar panel ───────────────────────────────────────────────────── */}
      <div
        ref={sidebarRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Override Risk"
        className={`
          fixed top-0 right-0 z-50 h-full w-full max-w-md
          flex flex-col
          bg-slate-900 border-l border-white/10 shadow-2xl
          transition-transform duration-300 ease-in-out outline-none
          ${isOpen ? "translate-x-0" : "translate-x-full"}
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/10 bg-white/5 shrink-0">
          <div className="space-y-0.5 min-w-0">
            <h2 className="text-base font-bold text-slate-100 tracking-tight">
              Override Risk
            </h2>
            <p className="text-xs text-slate-500 font-medium truncate max-w-[260px]">
              {clause.title} · {clause.id}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-all duration-150 active:scale-95"
            aria-label="Close sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {submitted ? (
          /* Success state */
          <div className="flex flex-col flex-1 items-center justify-center gap-4 px-8 text-center">
            <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div className="space-y-1">
              <p className="text-slate-100 font-semibold text-lg">Override Recorded</p>
              <p className="text-slate-500 text-sm">
                {clause.title} is now{" "}
                <span className="font-semibold text-slate-300">{newRisk}</span> risk.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="mt-4 px-6 py-2.5 rounded-xl bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium transition-all duration-200"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            {/* Scrollable form body */}
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
              {/* Current clause info */}
              <div className="rounded-xl bg-slate-800/60 border border-slate-700/40 p-4 space-y-2">
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  Current Clause
                </p>
                <p className="text-sm text-slate-300 leading-relaxed line-clamp-3">
                  {clause.excerpt}
                </p>
                <span
                  className={`inline-block mt-1 text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-widest ${
                    riskBadge[clause.riskLevel]
                  }`}
                >
                  {clause.riskLevel} RISK
                </span>
              </div>

              {/* New Risk Level */}
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  Override to Risk Level <span className="text-rose-400">*</span>
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {OVERRIDE_RISK_LEVELS.map((level) => (
                    <button
                      key={level}
                      type="button"
                      onClick={() => setNewRisk(level)}
                      className={`
                        py-2 rounded-xl text-xs font-bold uppercase tracking-wide border
                        transition-all duration-150 active:scale-95
                        ${
                          newRisk === level
                            ? `${riskBadge[level]} scale-105 shadow-lg`
                            : "border-slate-700 text-slate-500 hover:border-slate-500 hover:text-slate-300"
                        }
                      `}
                    >
                      {level}
                    </button>
                  ))}
                </div>
                {unchanged && (
                  <p className="text-xs text-slate-600">
                    Pick a level different from the current one to record an override.
                  </p>
                )}
              </div>

              {/* Override Reason */}
              <div className="space-y-2">
                <label
                  htmlFor="override-reason"
                  className="text-[10px] font-bold uppercase tracking-widest text-slate-500"
                >
                  Override Reason <span className="text-rose-400">*</span>
                </label>
                <textarea
                  id="override-reason"
                  rows={5}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain why this risk level is being overridden…"
                  className="
                    w-full bg-slate-800/60 border border-slate-700/50 rounded-xl
                    px-4 py-3 text-sm text-slate-200 placeholder-slate-600
                    focus:outline-none focus:border-sky-500/60 focus:ring-2 focus:ring-sky-500/20
                    resize-none transition-all duration-200 leading-relaxed
                  "
                />
                <p className="text-xs text-slate-600">
                  Recorded in the audit trail against your account.
                </p>
              </div>

              {error && (
                <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3">
                  <p className="text-sm text-rose-300">{error}</p>
                </div>
              )}
            </div>

            {/* Footer actions */}
            <div className="px-6 py-4 border-t border-white/10 bg-white/5 grid grid-cols-2 gap-3 shrink-0">
              <button
                type="button"
                onClick={onClose}
                className="
                  py-3 rounded-xl text-sm font-semibold
                  border border-slate-600 text-slate-300
                  hover:bg-slate-700/50 hover:text-white hover:border-slate-500
                  transition-all duration-200 active:scale-95
                "
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="
                  py-3 rounded-xl text-sm font-semibold
                  bg-sky-600 hover:bg-sky-500 text-white
                  transition-all duration-200 active:scale-95
                  disabled:opacity-40 disabled:cursor-not-allowed
                "
              >
                {submitting ? "Submitting…" : "Submit Override"}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
