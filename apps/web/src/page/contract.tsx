import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  OriginalContract,
  AIRiskAnalysis,
  ContractMetadataPanel,
  ExportMenu,
  PrintableReport,
  IncompleteReviewNotice,
} from "../component/contract";
import type { ContractReport, RiskLevel } from "../component/contract/types";
import { riskAccent } from "../component/contract/riskStyles";
import { ApiError } from "../lib/api";
import {
  acceptClause,
  fetchReport,
  overrideClause,
} from "../lib/contracts";

export default function ContractPage() {
  const navigate = useNavigate();
  // `?report=<id>` opens a review the history sidebar already knows about,
  // instead of forcing the reviewer to re-upload (and re-pay for) a contract
  // the backend has a report for.
  const [searchParams] = useSearchParams();
  const requestedReportId = searchParams.get("report");

  const [report, setReport] = useState<ContractReport | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  /**
   * The last `?report=` id the loader below finished with, win or lose.
   *
   * "Still loading" is derived from comparing it to the requested id rather
   * than stored as its own flag: a flag would have to be raised synchronously
   * inside the effect (a cascading render), and it would go stale the moment
   * the URL changed to a different report.
   */
  const [resolvedReportId, setResolvedReportId] = useState<string | null>(null);

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

  // Opening a stored report fills exactly the state an upload would, so the
  // rest of the page can't tell the two apart. Every write happens in a
  // settled-promise callback, never in the effect body — same shape as the
  // session probe in AuthProvider.
  useEffect(() => {
    if (!requestedReportId || requestedReportId === resolvedReportId) return;

    // The fetch outlives this component if the reviewer navigates away
    // mid-flight, and the flag also stops a slow answer for an old id from
    // overwriting a newer one.
    let cancelled = false;

    fetchReport(requestedReportId).then(
      (loaded) => {
        if (cancelled) return;
        setReport(loaded);
        setFileName(loaded.filename || loaded.contractId);
        setSelectedClauseId(loaded.clauses[0]?.id ?? null);
        setError(null);
        setResolvedReportId(requestedReportId);
      },
      (err: unknown) => {
        if (cancelled) return;
        handleApiError(err);
        // Resolved even though it failed: without this the effect would fire
        // again on the next render and retry forever.
        setResolvedReportId(requestedReportId);
      }
    );

    return () => {
      cancelled = true;
    };
  }, [requestedReportId, resolvedReportId, handleApiError]);

  const busy = requestedReportId !== null && requestedReportId !== resolvedReportId;

  /**
   * The override endpoint returns the whole updated report, so the response
   * replaces page state rather than being patched into it. (It also clears the
   * clause's acceptance server-side — the sign-off was for the old verdict.)
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
    },
    [report]
  );

  /** Sign-off is stored on the report, so the response is again the new state. */
  const handleAccept = useCallback(
    async (clauseId: string, accepted: boolean) => {
      if (!report) return;
      try {
        setReport(await acceptClause({ reportId: report.reportId, clauseId, accepted }));
      } catch (err) {
        handleApiError(err);
      }
    },
    [report, handleApiError]
  );

  const selectedClause = report?.clauses.find((c) => c.id === selectedClauseId) ?? null;

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* ── Page Header ─────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-8 py-5 border-b border-white/10 bg-white/5 backdrop-blur-sm shrink-0">
        <div className="space-y-0.5 min-w-0">
          <div className="flex items-center gap-3 min-w-0">
            <Link
              to="/manual"
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors shrink-0"
            >
              ← History
            </Link>
            <h1 className="text-xl font-bold text-slate-100 tracking-tight truncate">
              Contract Clause Risk Reviewer
            </h1>
          </div>
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

            <ExportMenu
              report={report}
              className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-600 text-sm font-semibold text-slate-300 hover:bg-slate-700/50 hover:text-white hover:border-slate-500 transition-colors"
            />
          </div>
        )}
      </header>

      {/* ── Status strip ────────────────────────────────────────────────────── */}
      {busy && (
        <div className="flex items-center gap-3 px-8 py-3 border-b border-sky-500/20 bg-sky-950/40 shrink-0">
          <span className="w-3.5 h-3.5 rounded-full border-2 border-sky-400 border-t-transparent animate-spin" />
          {/* The wait is measured, not guessed: the pipeline runs clauses
              serially at roughly four LLM calls each, and a real 8-clause
              contract took just over six minutes. "About a minute" reads as a
              hang once the third minute passes. */}
          <p className="text-sm text-sky-200">
            Loading the stored report…
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

      {/* A review that produced nothing, or clauses the pipeline failed on,
          both render as an ordinary report. Say so above the panels. */}
      {report && (
        <IncompleteReviewNotice report={report} className="mx-8 mt-3 shrink-0" />
      )}

      {/* Parties, dates, value — quoted from the document. Renders nothing
          when the contract didn't state any of it. */}
      {report && (
        <ContractMetadataPanel metadata={report.metadata} className="mx-8 mt-3 shrink-0" />
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
          hasReport={report !== null}
        />

        <AIRiskAnalysis
          clause={selectedClause}
          reportId={report?.reportId ?? null}
          onOverride={handleOverride}
          onAccept={handleAccept}
        />
      </main>

      {/* Hidden on screen; the print stylesheet swaps it in for the app. */}
      {report && <PrintableReport report={report} />}
    </div>
  );
}
