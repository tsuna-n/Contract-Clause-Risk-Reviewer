import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { OriginalContract, AIRiskAnalysis } from "../component/contract";
import type { ContractReport, RiskLevel } from "../component/contract/types";
import { riskAccent } from "../component/contract/riskStyles";
import { ApiError } from "../lib/api";
import {
  ACCEPTED_EXTENSIONS,
  isSupportedFile,
  overrideClause,
  reviewContract,
} from "../lib/contracts";

export default function ContractPage() {
  const navigate = useNavigate();

  const [report, setReport] = useState<ContractReport | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Local review progress — the backend records overrides, not acceptances. */
  const [acceptedIds, setAcceptedIds] = useState<ReadonlySet<string>>(new Set());

  /** A dead session can't be recovered in-page — send the user back to login. */
  const handleApiError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.isUnauthorized) {
        navigate("/login", { replace: true });
        return;
      }
      setError(err instanceof Error ? err.message : "Something went wrong");
    },
    [navigate]
  );

  const handleFileSelect = useCallback(
    async (file: File) => {
      if (!isSupportedFile(file)) {
        setError(
          `${file.name} is not a supported format. Upload ${ACCEPTED_EXTENSIONS.join(" or ")}.`
        );
        return;
      }

      setReviewing(true);
      setError(null);
      setFileName(file.name);
      setAcceptedIds(new Set());
      try {
        const result = await reviewContract(file);
        setReport(result);
        setSelectedClauseId(result.clauses[0]?.id ?? null);
      } catch (err) {
        setReport(null);
        setSelectedClauseId(null);
        handleApiError(err);
      } finally {
        setReviewing(false);
      }
    },
    [handleApiError]
  );

  /**
   * The override endpoint returns the whole updated report, so the response
   * replaces page state rather than being patched into it.
   */
  const handleOverride = useCallback(
    async (clauseId: string, newRisk: RiskLevel, reason: string) => {
      if (!report) return;
      const updated = await overrideClause({
        reportId: report.reportId,
        clauseId,
        newRisk,
        reason,
      });
      setReport(updated);
      // An overridden clause is no longer "accepted as assessed".
      setAcceptedIds((prev) => {
        if (!prev.has(clauseId)) return prev;
        const next = new Set(prev);
        next.delete(clauseId);
        return next;
      });
    },
    [report]
  );

  const handleAccept = useCallback((clauseId: string) => {
    setAcceptedIds((prev) => new Set(prev).add(clauseId));
  }, []);

  const selectedClause = report?.clauses.find((c) => c.id === selectedClauseId) ?? null;

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* ── Page Header ─────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-8 py-5 border-b border-white/10 bg-white/5 backdrop-blur-sm shrink-0">
        <div className="space-y-0.5 min-w-0">
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            Contract Clause Risk Reviewer
          </h1>
          <p className="text-xs text-slate-500 font-medium tracking-wide truncate">
            {fileName ?? "No contract loaded"}
          </p>
        </div>

        {report && (
          <div className="flex items-center gap-6 shrink-0">
            {/* Risk counts straight from the report summary */}
            <div className="hidden md:flex items-center gap-4 text-xs">
              <span className="text-red-400 font-semibold">{report.summary.high} High</span>
              <span className="text-amber-400 font-semibold">
                {report.summary.medium} Medium
              </span>
              <span className="text-emerald-400 font-semibold">
                {report.summary.low} Low
              </span>
              {report.summary.unknown > 0 && (
                <span className="text-slate-400 font-semibold">
                  {report.summary.unknown} Unknown
                </span>
              )}
            </div>

            <div className="text-right">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Overall Risk
              </p>
              <p
                className={`text-sm font-extrabold tracking-wide ${
                  riskAccent[report.overallRisk]
                }`}
              >
                {report.overallRisk} RISK
              </p>
            </div>
          </div>
        )}
      </header>

      {/* ── Status strip ────────────────────────────────────────────────────── */}
      {reviewing && (
        <div className="flex items-center gap-3 px-8 py-3 border-b border-sky-500/20 bg-sky-950/40 shrink-0">
          <span className="w-3.5 h-3.5 rounded-full border-2 border-sky-400 border-t-transparent animate-spin" />
          <p className="text-sm text-sky-200">
            Reviewing {fileName}… this runs the full pipeline and can take a minute.
          </p>
        </div>
      )}

      {error && (
        <div className="flex items-start justify-between gap-4 px-8 py-3 border-b border-rose-500/30 bg-rose-950/40 shrink-0">
          <p className="text-sm text-rose-200">{error}</p>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-rose-300/70 hover:text-rose-200 text-sm shrink-0"
            aria-label="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {report?.disclaimer && (
        <div className="px-8 py-2.5 border-b border-amber-500/20 bg-amber-950/30 shrink-0">
          <p className="text-xs text-amber-200/90 leading-relaxed">{report.disclaimer}</p>
        </div>
      )}

      {/* ── Main Content — Two-panel layout ────────────────────────────────── */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6 p-6 min-h-0">
        <OriginalContract
          clauses={report?.clauses ?? []}
          selectedClauseId={selectedClauseId}
          onClauseSelect={setSelectedClauseId}
          onFileSelect={handleFileSelect}
          busy={reviewing}
          acceptedIds={acceptedIds}
        />

        <AIRiskAnalysis
          clause={selectedClause}
          reportId={report?.reportId ?? null}
          onOverride={handleOverride}
          accepted={selectedClause ? acceptedIds.has(selectedClause.id) : false}
          onAccept={handleAccept}
        />
      </main>
    </div>
  );
}
