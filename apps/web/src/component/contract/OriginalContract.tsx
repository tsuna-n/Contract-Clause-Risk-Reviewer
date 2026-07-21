import { useRef } from "react";
import type { ClauseView } from "./types";
import { riskBadge, riskRow, riskRowSelected } from "./riskStyles";
import { ACCEPT_ATTRIBUTE, ACCEPTED_EXTENSIONS } from "../../lib/contracts";

interface OriginalContractProps {
  clauses: ClauseView[];
  selectedClauseId: string | null;
  onClauseSelect: (id: string) => void;
  /** Called with a user-picked file; the page owns the upload itself. */
  onFileSelect: (file: File) => void;
  /** Disables the picker while a review is in flight. */
  busy?: boolean;
  /** Clause ids the reviewer has accepted, for at-a-glance progress. */
  acceptedIds?: ReadonlySet<string>;
}

export default function OriginalContract({
  clauses,
  selectedClauseId,
  onClauseSelect,
  onFileSelect,
  busy = false,
  acceptedIds,
}: OriginalContractProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const openFilePicker = () => fileInputRef.current?.click();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset first: picking the same file twice in a row otherwise fires no
    // change event, and re-uploading after a failure is exactly that case.
    e.target.value = "";
    if (file) onFileSelect(file);
  };

  return (
    <div className="flex flex-col h-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
      {/* Panel Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/5">
        <h2 className="text-base font-semibold text-slate-100 tracking-wide">
          Original Contract
        </h2>
        <button
          type="button"
          onClick={openFilePicker}
          disabled={busy}
          className="
            flex items-center gap-2 px-4 py-2 rounded-xl
            bg-slate-100 text-slate-900 text-sm font-semibold
            hover:bg-white transition-all duration-200
            shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95
            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100
          "
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
            />
          </svg>
          Upload
        </button>
      </div>

      {/* Clause list */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {clauses.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-2 px-6">
            <p className="text-slate-400 text-sm font-medium">No contract loaded</p>
            <p className="text-slate-600 text-xs">
              Upload a {ACCEPTED_EXTENSIONS.join(" or ")} file to run a review
            </p>
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
                    {acceptedIds?.has(clause.id) && (
                      <span className="text-emerald-400 mr-1" title="Accepted">
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

      {/* Import Footer */}
      <div className="px-6 py-4 border-t border-white/10 bg-white/5">
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          type="button"
          onClick={openFilePicker}
          disabled={busy}
          className="
            w-full flex items-center justify-center gap-2.5
            py-3 rounded-xl text-sm font-semibold
            border border-dashed border-slate-600
            text-slate-300 hover:text-white
            hover:border-slate-400 hover:bg-slate-700/40
            transition-all duration-200 ease-in-out
            hover:shadow-lg active:scale-95
            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent
          "
        >
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
            />
          </svg>
          {busy ? "Reviewing…" : "Import Contract"}
          <span className="text-xs text-slate-500 font-normal">
            {ACCEPTED_EXTENSIONS.join(" · ")}
          </span>
        </button>
      </div>
    </div>
  );
}
