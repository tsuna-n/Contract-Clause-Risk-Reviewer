import { useEffect, useMemo } from "react";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import type { ClauseView } from "./types";
import { riskBadge, riskRow, riskRowSelected } from "./riskStyles";
import {
  setContractContext,
  setSelectedClauseId,
  useContractUiState,
} from "./contractUiStore.ts";

interface OriginalContractProps {
  clauses: ClauseView[];
  selectedClauseId: string | null;
  onClauseSelect: (id: string) => void;
  /**
   * A report is loaded, even if it yielded no clauses.
   *
   * Without this the panel can't tell "nothing uploaded yet" from "a file was
   * reviewed and no text came out of it" — and it told the second case to
   * upload a contract, while the page header named the file it had just
   * reviewed.
   */
  hasReport?: boolean;
}

export default function OriginalContract({
  clauses,
  selectedClauseId,
  onClauseSelect,
  hasReport = false,
}: OriginalContractProps) {
  const { decisionStates } = useContractUiState();

  useEffect(() => {
    setContractContext(clauses, selectedClauseId);
  }, [clauses, selectedClauseId]);

  const selectedClauseIds = useMemo(
    () => new Set(clauses.filter((clause) => clause.accepted).map((clause) => clause.id)),
    [clauses]
  );

  function getDecisionLabel(clause: ClauseView) {
    return decisionStates[clause.id] ?? (selectedClauseIds.has(clause.id) ? "accepted" : null);
  }

  function badgeIcon(level: ClauseView["riskLevel"]) {
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

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-3xl border border-navy-800 bg-navy-900/60 shadow-2xl shadow-navy-950/40 backdrop-blur-sm">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-navy-800 bg-navy-900/80 px-6 py-4">
        <h2 className="text-base font-semibold tracking-wide text-white">
          Original Contract
        </h2>
      </div>

      {/* Clause list */}
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
        {clauses.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-2 px-6">
            {hasReport ? (
              <>
                <p className="text-sm font-medium text-slate-300">
                  No clauses could be extracted
                </p>
                <p className="max-w-xs text-xs leading-relaxed text-slate-400">
                  The file was read but produced no text to review — usually a scanned
                  PDF with no text layer.
                </p>
              </>
            ) : (
              <p className="text-sm font-medium text-slate-300">No contract loaded</p>
            )}
          </div>
        ) : (
          clauses.map((clause, index) => {
            const isSelected = selectedClauseId === clause.id;
            const decisionLabel = getDecisionLabel(clause);
            return (
              <button
                key={clause.id}
                type="button"
                onClick={() => {
                  setSelectedClauseId(clause.id);
                  onClauseSelect(clause.id);
                }}
                aria-current={isSelected}
                className={`
                  group block w-full text-left relative rounded-r-2xl p-4 cursor-pointer
                  transition-all duration-200 ease-in-out
                  ${isSelected ? riskRowSelected[clause.riskLevel] : riskRow[clause.riskLevel]}
                  hover:brightness-110 hover:shadow-lg
                `}
              >
                {/* Title sits on its own line: the clause text usually repeats
                    its own numbering/heading, so inlining the two duplicates it. */}
                <div className="mb-1.5 flex items-start justify-between gap-3">
                  <span className="min-w-0 text-sm font-bold text-white">
                    {/* Sign-off comes with the report, so the checklist is
                        still filled in after a refresh. */}
                    {clause.accepted && (
                      <span
                        className="text-emerald-400 mr-1"
                        title={
                          clause.acceptedBy
                            ? `Accepted by ${clause.acceptedBy}`
                            : "Accepted"
                        }
                      >
                        ✓
                      </span>
                    )}
                    {index + 1}. {clause.title}
                  </span>
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${
                        riskBadge[clause.riskLevel]
                      }`}
                      aria-label={`${clause.riskLevel} risk`}
                    >
                      {badgeIcon(clause.riskLevel)}
                      <span>{clause.riskLevel}</span>
                    </span>

                    {decisionLabel && (
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${
                          decisionLabel === "accepted"
                            ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                            : "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                        }`}
                      >
                        {decisionLabel === "accepted" ? "Accepted" : "Overridden"}
                      </span>
                    )}
                  </div>
                </div>
                <p className="line-clamp-4 text-sm leading-relaxed text-slate-300">
                  {clause.text}
                </p>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}