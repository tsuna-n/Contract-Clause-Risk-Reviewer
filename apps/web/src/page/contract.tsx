import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  OriginalContract,
  AIRiskAnalysis,
  ContractMetadataPanel,
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

/**
 * Small colored count row used in the sidebar's risk breakdown.
 * Pulled out so the breakdown reads as a list a reviewer can scan top to
 * bottom, rather than a row of pills competing for attention.
 */
function StatRow({
  dotClassName,
  valueClassName,
  label,
  value,
}: {
  dotClassName: string;
  valueClassName: string;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span className={`h-2 w-2 shrink-0 rounded-full ${dotClassName}`} aria-hidden />
      <span className={`text-sm font-semibold tabular-nums ${valueClassName}`}>{value}</span>
      <span className="text-xs font-medium text-slate-400">{label}</span>
    </div>
  );
}

const RISK_COLORS = {
  high: { dot: "bg-red-400", text: "text-red-400", hex: "#f87171" },
  medium: { dot: "bg-amber-400", text: "text-amber-400", hex: "#fbbf24" },
  low: { dot: "bg-emerald-400", text: "text-emerald-400", hex: "#34d399" },
  unknown: { dot: "bg-slate-400", text: "text-slate-300", hex: "#94a3b8" },
};

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

  /**
   * Whether the AI analysis panel is open. It's separate from
   * `selectedClauseId` on purpose: closing the panel shouldn't forget which
   * clause a reviewer was looking at, so re-opening it (or clicking the same
   * clause again) can snap right back to it.
   */
  const [analysisOpen, setAnalysisOpen] = useState(false);

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

  // Escape closes the analysis panel — the same expectation as any slide-in
  // panel or dialog, and the fastest way back to just reading the contract.
  useEffect(() => {
    if (!analysisOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAnalysisOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [analysisOpen]);

  /**
   * Selecting a clause opens its analysis; clearing the selection closes it.
   * The panel itself can still be dismissed independently (Escape, backdrop,
   * close button) without losing track of which clause was selected.
   */
  const handleClauseSelect = useCallback((clauseId: string | null) => {
    setSelectedClauseId(clauseId);
    setAnalysisOpen(clauseId !== null);
  }, []);

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

  // Composition of the risk gauge in the sidebar. Percentages, not raw
  // counts, because the gauge is a conic-gradient ring — it needs where each
  // color's slice starts and ends, not how many clauses are in it.
  const summary = report?.summary;
  const total = summary ? summary.high + summary.medium + summary.low + summary.unknown : 0;
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);
  const highEnd = pct(summary?.high ?? 0);
  const mediumEnd = highEnd + pct(summary?.medium ?? 0);
  const lowEnd = mediumEnd + pct(summary?.low ?? 0);
  const gaugeBackground = `conic-gradient(${RISK_COLORS.high.hex} 0% ${highEnd}%, ${RISK_COLORS.medium.hex} ${highEnd}% ${mediumEnd}%, ${RISK_COLORS.low.hex} ${mediumEnd}% ${lowEnd}%, ${RISK_COLORS.unknown.hex} ${lowEnd}% 100%)`;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-navy-950 text-white">
      {/* ── Status / error — global, thin, above everything else so neither
          the sidebar nor the reading pane has to make room for them ──────── */}
      {busy && (
        <div className="shrink-0 border-b border-navy-700/60 bg-navy-900/40">
          <div className="flex items-center gap-3 px-6 py-3">
            <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-navy-400 border-t-transparent" />
            {/* The wait is measured, not guessed: the pipeline runs clauses
                serially at roughly four LLM calls each, and a real 8-clause
                contract took just over six minutes. Say so up front so a
                third minute of waiting doesn't read as a hang. */}
            <p className="text-sm text-navy-100">
              Loading the stored report — longer contracts can take a few minutes.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="shrink-0 border-b border-rose-500/30 bg-rose-950/40">
          <div className="flex items-start justify-between gap-4 px-6 py-3">
            <div className="flex items-start gap-2.5">
              <span aria-hidden className="mt-0.5 shrink-0 text-rose-400">⚠</span>
              <p className="text-sm text-rose-200">{error}</p>
            </div>
            <button
              type="button"
              onClick={() => setError(null)}
              className="shrink-0 rounded-full p-1 text-rose-300/70 transition-colors hover:bg-rose-500/10 hover:text-rose-200"
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
        {/* ── Sidebar — everything about the report that isn't the contract
            text itself, grouped once so the reading pane starts clean:
            identity, the risk gauge, counts, metadata, and notices ──────── */}
        <aside className="flex w-full shrink-0 flex-col overflow-y-auto border-b border-navy-800 bg-navy-900/60 backdrop-blur-sm lg:h-full lg:w-[300px] lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-3 px-5 py-4">
            <Link
              to="/manual"
              className="group flex shrink-0 items-center gap-1.5 rounded-full border border-navy-800 bg-navy-900/60 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-navy-700 hover:text-navy-100"
            >
              <span aria-hidden className="transition-transform group-hover:-translate-x-0.5">←</span>
              History
            </Link>
          </div>

          <div className="px-5 pb-1">
            <h1 className="text-base font-bold leading-tight tracking-tight text-white">
              Contract Clause Risk Reviewer
            </h1>
            <p className="mt-0.5 truncate text-xs font-medium tracking-wide text-slate-400">
              {fileName ?? "No contract loaded"}
            </p>
          </div>

          {report && (
            <>
              {/* Risk gauge + counts, side by side so the headline number
                  (Overall Risk) and its breakdown are read in one glance
                  instead of scanned across a row of separate pills. */}
              <div className="flex items-center gap-4 px-5 py-5">
                <div
                  className="relative h-[88px] w-[88px] shrink-0 rounded-full"
                  style={{ background: total > 0 ? gaugeBackground : undefined }}
                >
                  <div className="absolute inset-[7px] flex flex-col items-center justify-center rounded-full bg-navy-950">
                    <span className={`text-[11px] font-extrabold leading-tight ${riskAccent[report.overallRisk]}`}>
                      {report.overallRisk}
                    </span>
                    <span className="text-[9px] font-bold uppercase tracking-widest text-slate-500">
                      risk
                    </span>
                  </div>
                </div>

                <div className="flex flex-1 flex-col gap-2">
                  <StatRow
                    dotClassName={RISK_COLORS.high.dot}
                    valueClassName={RISK_COLORS.high.text}
                    label="High"
                    value={report.summary.high}
                  />
                  <StatRow
                    dotClassName={RISK_COLORS.medium.dot}
                    valueClassName={RISK_COLORS.medium.text}
                    label="Medium"
                    value={report.summary.medium}
                  />
                  <StatRow
                    dotClassName={RISK_COLORS.low.dot}
                    valueClassName={RISK_COLORS.low.text}
                    label="Low"
                    value={report.summary.low}
                  />
                  {report.summary.unknown > 0 && (
                    <StatRow
                      dotClassName={RISK_COLORS.unknown.dot}
                      valueClassName={RISK_COLORS.unknown.text}
                      label="Unknown"
                      value={report.summary.unknown}
                    />
                  )}
                </div>
              </div>

              <div className="divide-y divide-navy-800 border-t border-navy-800">
                {/* A review that produced nothing, or clauses the pipeline
                    failed on, both render as an ordinary report. Say so
                    up front, right where the reviewer is already looking
                    for context. */}
                <IncompleteReviewNotice report={report} />

                {/* Parties, dates, value — quoted from the document.
                    Renders nothing when the contract didn't state any of it. */}
                <ContractMetadataPanel metadata={report.metadata} />

                {report.disclaimer && (
                  <div className="bg-amber-950/30 px-5 py-3">
                    <p className="text-xs leading-relaxed text-amber-200/90">
                      {report.disclaimer}
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </aside>

        {/* ── Reading pane + analysis panel ───────────────────────────────── */}
        <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden">
          <main className="min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
            {report ? (
              <div className="h-full min-h-0 overflow-hidden rounded-2xl border border-navy-800 bg-navy-900/30 shadow-lg shadow-black/10">
                <OriginalContract
                  clauses={report.clauses}
                  selectedClauseId={selectedClauseId}
                  onClauseSelect={handleClauseSelect}
                  hasReport
                />
              </div>
            ) : busy ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-navy-800 bg-navy-900/20 p-10 text-center">
                <span className="h-8 w-8 animate-spin rounded-full border-2 border-navy-400 border-t-transparent" />
                <p className="text-sm font-medium text-navy-100">Loading the stored report…</p>
                <p className="max-w-sm text-xs text-slate-500">
                  Longer contracts can take a few minutes — each clause runs through several
                  checks before the review is ready.
                </p>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-navy-800 bg-navy-900/20 p-10 text-center">
                <p className="text-base font-semibold text-slate-200">No contract loaded</p>
                <p className="max-w-sm text-sm text-slate-500">
                  Open a previous review from your history, or start a new upload to see
                  clause-by-clause risk analysis here.
                </p>
                <Link
                  to="/manual"
                  className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-navy-100 px-4 py-2 text-xs font-semibold text-navy-950 transition-colors hover:bg-white"
                >
                  Go to history
                </Link>
              </div>
            )}
          </main>

          {/* Backdrop — mobile/tablet only. On large screens the panel sits
              in-flow next to the reading pane, so nothing needs dimming. */}
          {analysisOpen && (
            <div
              className="fixed inset-0 z-20 bg-black/50 backdrop-blur-[1px] lg:hidden"
              onClick={() => setAnalysisOpen(false)}
              aria-hidden
            />
          )}

          {/* Analysis panel — a clause's AI verdict is opened on demand
              instead of permanently occupying half the screen. On phones and
              tablets it slides in over the contract; on wide screens it
              settles in as a fixed-width column so the clause stays visible
              while its analysis is read side by side. */}
          <div
            className={`fixed inset-y-0 right-0 z-30 w-full max-w-md transform border-navy-800 bg-navy-900 shadow-2xl transition-transform duration-300 ease-in-out lg:static lg:inset-auto lg:z-auto lg:max-w-none lg:translate-x-0 lg:transform-none lg:border-l lg:shadow-none lg:transition-[width] ${
              analysisOpen ? "translate-x-0 lg:w-[420px]" : "translate-x-full lg:w-0 lg:overflow-hidden"
            }`}
          >
            <div className="flex h-full w-full flex-col overflow-hidden lg:w-[420px]">
              <div className="flex shrink-0 items-center justify-between border-b border-navy-800 px-4 py-3">
                <h2 className="text-sm font-bold tracking-tight text-white">Clause analysis</h2>
                <button
                  type="button"
                  onClick={() => setAnalysisOpen(false)}
                  className="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-navy-800 hover:text-white"
                  aria-label="Close clause analysis"
                >
                  ✕
                </button>
              </div>
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <AIRiskAnalysis
                  clause={selectedClause}
                  reportId={report?.reportId ?? null}
                  onOverride={handleOverride}
                  onAccept={handleAccept}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}