import type { ClauseView } from "./types";
import { riskBadge, riskRow, riskRowSelected } from "./riskStyles";

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
  return (
    <div className="flex flex-col h-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
      {/* Panel Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/5">
        <h2 className="text-base font-semibold text-slate-100 tracking-wide">
          Original Contract
        </h2>
      </div>

      {/* Clause list */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {clauses.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-2 px-6">
            {hasReport ? (
              <>
                <p className="text-slate-400 text-sm font-medium">
                  No clauses could be extracted
                </p>
                <p className="text-slate-600 text-xs max-w-xs leading-relaxed">
                  The file was read but produced no text to review — usually a scanned
                  PDF with no text layer.
                </p>
              </>
            ) : (
              <p className="text-slate-400 text-sm font-medium">No contract loaded</p>
            )}
          </div>
        ) : (
          clauses.map((clause, index) => {
            const isSelected = selectedClauseId === clause.id;
            return (
              <button
                key={clause.id}
                type="button"
                onClick={() => onClauseSelect(clause.id)}
                aria-current={isSelected}
                className={`
                  block w-full text-left relative rounded-r-xl p-4 cursor-pointer
                  transition-all duration-200 ease-in-out
                  ${isSelected ? riskRowSelected[clause.riskLevel] : riskRow[clause.riskLevel]}
                  hover:brightness-110 hover:shadow-lg
                `}
              >
                {/* Title sits on its own line: the clause text usually repeats
                    its own numbering/heading, so inlining the two duplicates it. */}
                <div className="flex items-baseline justify-between gap-3 mb-1.5">
                  <span className="font-bold text-slate-100 text-sm">
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
                  <span
                    className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest ${
                      riskBadge[clause.riskLevel]
                    }`}
                  >
                    {clause.riskLevel}
                  </span>
                </div>
                <p className="text-sm text-slate-300 leading-relaxed line-clamp-4">
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