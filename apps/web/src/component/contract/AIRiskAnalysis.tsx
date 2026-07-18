import { useState } from "react";
import type { Clause, ContractMetadata } from "./types";
import OverrideSidebar from "./OverrideSidebar";

// ── Styles ─────────────────────────────────────────────────────────────────────
interface AIRiskAnalysisProps {
  clause: Clause | null;
  metadata?: ContractMetadata;
}


const riskBadgeStyle: Record<string, string> = {
  LOW:      "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
  MEDIUM:   "bg-amber-500/20  text-amber-300  border border-amber-500/40",
  HIGH:     "bg-red-500/20    text-red-300    border border-red-500/40",
  CRITICAL: "bg-rose-600/20   text-rose-300   border border-rose-600/40",
};

const riskAcceptStyle: Record<string, string> = {
  LOW:      "bg-emerald-600 hover:bg-emerald-500 text-white",
  MEDIUM:   "bg-amber-600   hover:bg-amber-500   text-white",
  HIGH:     "bg-red-600     hover:bg-red-500     text-white",
  CRITICAL: "bg-rose-700    hover:bg-rose-600    text-white",
};

// ── Component ──────────────────────────────────────────────────────────────────
export default function AIRiskAnalysis({ clause, metadata }: AIRiskAnalysisProps) {
  const [overrideSidebarOpen, setOverrideSidebarOpen] = useState(false);

  if (!clause) {
    return (
      <div className="flex flex-col h-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl overflow-hidden shadow-2xl items-center justify-center">
        <div className="text-center space-y-3 px-8 animate-fade-in-up">
          <div className="text-5xl mb-4">🔍</div>
          <p className="text-slate-400 text-sm font-medium">
            Select a clause from the contract
          </p>
          <p className="text-slate-600 text-xs">
            Click any highlighted clause to see the AI risk analysis
          </p>
        </div>
      </div>
    );
  }

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
              riskBadgeStyle[clause.riskLevel]
            }`}
          >
            {clause.riskLevel} RISK
          </span>
        </div>

        {/* Analysis Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {/* ── Contract Metadata Section ─────────────────────────────────── */}
          {metadata && (
            <div className="bg-slate-800/20 border border-white/10 rounded-xl p-5 space-y-4">
              <div className="flex items-center gap-2 border-b border-white/10 pb-2">
                <svg className="w-4 h-4 text-sky-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest">
                  ข้อมูลสัญญา (Contract Metadata)
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="space-y-1">
                  <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Contract Type</p>
                  <div className="bg-slate-950/40 border border-white/5 rounded-lg p-2.5 text-slate-200 min-h-[38px] flex items-center">
                    {metadata.contractType || <span className="text-slate-600 italic">{clause.title}</span>}
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Contract Title</p>
                  <div className="bg-slate-950/40 border border-white/5 rounded-lg p-2.5 text-slate-200 min-h-[38px] flex items-center">
                    {metadata.contractTitle || <span className="text-slate-600 italic">No Data</span>}
                  </div>
                </div>
                <div className="space-y-1 md:col-span-2">
                  <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Contracting Parties</p>
                  <div className="bg-slate-950/40 border border-white/5 rounded-lg p-2.5 text-slate-200 min-h-[38px] flex items-center">
                    {metadata.contractingParties || <span className="text-slate-600 italic">No Data</span>}
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Contract Execution Date</p>
                  <div className="bg-slate-950/40 border border-white/5 rounded-lg p-2.5 text-slate-200 min-h-[38px] flex items-center">
                    {metadata.contractExecutionDate || <span className="text-slate-600 italic">No Data</span>}
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Effective Date</p>
                  <div className="bg-slate-950/40 border border-white/5 rounded-lg p-2.5 text-slate-200 min-h-[38px] flex items-center">
                    {metadata.effectiveDate || <span className="text-slate-600 italic">No Data</span>}
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Expiration Date</p>
                  <div className="bg-slate-950/40 border border-white/5 rounded-lg p-2.5 text-slate-200 min-h-[38px] flex items-center">
                    {metadata.expirationDate || <span className="text-slate-600 italic">No Data</span>}
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Contract Value</p>
                  <div className="bg-slate-950/40 border border-white/5 rounded-lg p-2.5 text-slate-200 min-h-[38px] flex items-center">
                    {metadata.contractValue || <span className="text-slate-500 italic">Not Specified</span>}
                  </div>
                </div>
                <div className="space-y-1 md:col-span-2">
                  <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Contract Term</p>
                  <div className="bg-slate-950/40 border border-white/5 rounded-lg p-2.5 text-slate-200 min-h-[38px] flex items-center">
                    {metadata.contractTerm || <span className="text-slate-600 italic">No Data</span>}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Clause Type */}
          <div className="space-y-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Clause Type
            </p>
            <p className="text-xl font-bold text-slate-100">{clause.title}</p>
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

          {/* Playbook Match */}
          <div className="space-y-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Playbook Match
            </p>
            <a
              href="#"
              className="text-sm text-sky-400 hover:text-sky-300 hover:underline transition-colors font-medium"
            >
              {clause.playbookMatch}
            </a>
          </div>

          {/* AI Rationale */}
          <div className="space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              AI Rationale
            </p>
            <p className="text-sm text-slate-300 leading-relaxed">
              {clause.aiRationale}
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
                {clause.suggestedFallback}
              </p>
            </div>
          </div>

          {/* Citations */}
          <div className="space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Citations
            </p>
            <div className="flex flex-wrap gap-2">
              {clause.citations.map((c) => (
                <span
                  key={c}
                  className="text-xs bg-slate-700/60 border border-slate-600/40 text-slate-300 px-3 py-1 rounded-lg font-mono"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="px-6 py-4 border-t border-white/10 bg-white/5 grid grid-cols-2 gap-3">
          <button
            className={`
              py-3 rounded-xl text-sm font-semibold
              transition-all duration-200 ease-in-out
              shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95
              ${riskAcceptStyle[clause.riskLevel]}
            `}
          >
            Accept Risk
          </button>
          <button
            onClick={() => setOverrideSidebarOpen(true)}
            className="
              py-3 rounded-xl text-sm font-semibold
              border border-slate-600 text-slate-300
              hover:bg-slate-700/50 hover:text-white hover:border-slate-500
              transition-all duration-200 ease-in-out
              hover:shadow-lg hover:scale-[1.02] active:scale-95
            "
          >
            Override Risk
          </button>
        </div>
      </div>

      {/* Override Sidebar — rendered outside the panel so it overlays the full page */}
      <OverrideSidebar
        isOpen={overrideSidebarOpen}
        clause={clause}
        onClose={() => setOverrideSidebarOpen(false)}
      />
    </>
  );
}
