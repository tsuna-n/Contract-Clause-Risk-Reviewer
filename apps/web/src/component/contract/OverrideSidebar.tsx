import { useEffect, useRef, useState } from "react";
import type { Clause, RiskLevel } from "./types";

// ── Mock override data ─────────────────────────────────────────────────────────
const MOCK_OVERRIDE = {
  reason: "Legal team has reviewed and approved this clause under the current\nbusiness context. The confidentiality period aligns with our standard NDA template.",
  newRiskLevel: "LOW" as RiskLevel,
  reviewerName: "Natthaphon Sitha",
  reviewerRole: "Senior Legal Counsel",
  overrideDate: "2026-07-18",
  notes: "Override approved after cross-referencing with client contract playbook §2.1 and internal risk matrix v4.",
  approvalRef: "OVR-2026-0718-001",
};

// ── Styles ─────────────────────────────────────────────────────────────────────
const riskBadge: Record<RiskLevel, string> = {
  LOW:      "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
  MEDIUM:   "bg-amber-500/20  text-amber-300  border border-amber-500/40",
  HIGH:     "bg-red-500/20    text-red-300    border border-red-500/40",
  CRITICAL: "bg-rose-600/20   text-rose-300   border border-rose-600/40",
};

const riskOption: Record<RiskLevel, string> = {
  LOW:      "text-emerald-300",
  MEDIUM:   "text-amber-300",
  HIGH:     "text-red-300",
  CRITICAL: "text-rose-400",
};

// ── Props ──────────────────────────────────────────────────────────────────────
interface OverrideSidebarProps {
  isOpen: boolean;
  clause: Clause | null;
  onClose: () => void;
  onSubmit?: (data: typeof MOCK_OVERRIDE) => void;
}

const RISK_LEVELS: RiskLevel[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

// ── Component ──────────────────────────────────────────────────────────────────
export default function OverrideSidebar({
  isOpen,
  clause,
  onClose,
  onSubmit,
}: OverrideSidebarProps) {
  // Form state — pre-filled with mock data
  const [reason, setReason]           = useState(MOCK_OVERRIDE.reason);
  const [newRisk, setNewRisk]         = useState<RiskLevel>(MOCK_OVERRIDE.newRiskLevel);
  const [notes, setNotes]             = useState(MOCK_OVERRIDE.notes);
  const [reviewer, setReviewer]       = useState(MOCK_OVERRIDE.reviewerName);
  const [submitted, setSubmitted]     = useState(false);

  // Reset form when a new clause is loaded
  useEffect(() => {
    if (clause) {
      setReason(MOCK_OVERRIDE.reason);
      setNewRisk(MOCK_OVERRIDE.newRiskLevel);
      setNotes(MOCK_OVERRIDE.notes);
      setReviewer(MOCK_OVERRIDE.reviewerName);
      setSubmitted(false);
    }
  }, [clause?.id]);

  // Trap focus inside sidebar when open
  const sidebarRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (isOpen) sidebarRef.current?.focus();
  }, [isOpen]);

  const handleSubmit = () => {
    setSubmitted(true);
    onSubmit?.({
      ...MOCK_OVERRIDE,
      reason,
      newRiskLevel: newRisk,
      notes,
      reviewerName: reviewer,
    });
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
          <div className="space-y-0.5">
            <h2 className="text-base font-bold text-slate-100 tracking-tight">
              Override Risk
            </h2>
            {clause && (
              <p className="text-xs text-slate-500 font-medium truncate max-w-[260px]">
                {clause.title} · {clause.id}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-all duration-150 active:scale-95"
            aria-label="Close sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Success state */}
        {submitted ? (
          <div className="flex flex-col flex-1 items-center justify-center gap-4 px-8 text-center">
            <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div className="space-y-1">
              <p className="text-slate-100 font-semibold text-lg">Override Submitted</p>
              <p className="text-slate-500 text-sm">
                Ref: <span className="font-mono text-slate-400">{MOCK_OVERRIDE.approvalRef}</span>
              </p>
            </div>
            <button
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
              {clause && (
                <div className="rounded-xl bg-slate-800/60 border border-slate-700/40 p-4 space-y-2">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                    Current Clause
                  </p>
                  <p className="text-sm text-slate-300 leading-relaxed line-clamp-3">
                    {clause.excerpt}
                  </p>
                  <span className={`inline-block mt-1 text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-widest ${riskBadge[clause.riskLevel]}`}>
                    {clause.riskLevel} RISK
                  </span>
                </div>
              )}

              {/* New Risk Level */}
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  Override to Risk Level <span className="text-rose-400">*</span>
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {RISK_LEVELS.map((level) => (
                    <button
                      key={level}
                      onClick={() => setNewRisk(level)}
                      className={`
                        py-2 rounded-xl text-xs font-bold uppercase tracking-wide border
                        transition-all duration-150 active:scale-95
                        ${newRisk === level
                          ? `${riskBadge[level]} scale-105 shadow-lg`
                          : "border-slate-700 text-slate-500 hover:border-slate-500 hover:text-slate-300"
                        }
                      `}
                    >
                      <span className={newRisk === level ? riskOption[level] : ""}>{level}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Override Reason */}
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  Override Reason <span className="text-rose-400">*</span>
                </label>
                <textarea
                  rows={4}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain why this risk level is being overridden..."
                  className="
                    w-full bg-slate-800/60 border border-slate-700/50 rounded-xl
                    px-4 py-3 text-sm text-slate-200 placeholder-slate-600
                    focus:outline-none focus:border-sky-500/60 focus:ring-2 focus:ring-sky-500/20
                    resize-none transition-all duration-200 leading-relaxed
                  "
                />
              </div>

              {/* Additional Notes */}
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  Additional Notes
                </label>
                <textarea
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Any supporting context or references..."
                  className="
                    w-full bg-slate-800/60 border border-slate-700/50 rounded-xl
                    px-4 py-3 text-sm text-slate-200 placeholder-slate-600
                    focus:outline-none focus:border-sky-500/60 focus:ring-2 focus:ring-sky-500/20
                    resize-none transition-all duration-200 leading-relaxed
                  "
                />
              </div>

              {/* Reviewer Name */}
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  Reviewed by
                </label>
                <input
                  type="text"
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                  placeholder="Full name"
                  className="
                    w-full bg-slate-800/60 border border-slate-700/50 rounded-xl
                    px-4 py-3 text-sm text-slate-200 placeholder-slate-600
                    focus:outline-none focus:border-sky-500/60 focus:ring-2 focus:ring-sky-500/20
                    transition-all duration-200
                  "
                />
                <p className="text-xs text-slate-600">{MOCK_OVERRIDE.reviewerRole} · {MOCK_OVERRIDE.overrideDate}</p>
              </div>

              {/* Approval Ref */}
              <div className="rounded-xl bg-slate-800/40 border border-slate-700/30 px-4 py-3 flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Approval Ref</span>
                <span className="font-mono text-xs text-slate-400">{MOCK_OVERRIDE.approvalRef}</span>
              </div>
            </div>

            {/* Footer actions */}
            <div className="px-6 py-4 border-t border-white/10 bg-white/5 grid grid-cols-2 gap-3 shrink-0">
              <button
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
                onClick={handleSubmit}
                disabled={!reason.trim()}
                className="
                  py-3 rounded-xl text-sm font-semibold
                  bg-sky-600 hover:bg-sky-500 text-white
                  disabled:opacity-40 disabled:cursor-not-allowed
                  transition-all duration-200 shadow-lg hover:shadow-sky-500/25
                  hover:scale-[1.02] active:scale-95
                "
              >
                Submit Override
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
