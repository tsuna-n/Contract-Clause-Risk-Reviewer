import { useState } from "react";
import { OriginalContract, AIRiskAnalysis } from "../component/contract";
import { MOCK_CLAUSES } from "../component/contract/OriginalContract";
import type { Clause, RiskLevel, ContractMetadata } from "../component/contract/types";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ContractData {
  contractName: string;
  overallRisk: RiskLevel;
  contractTitle: string;
  clauses: Clause[];
  metadata: ContractMetadata;
}

// ── Mock Data ──────────────────────────────────────────────────────────────────

const mockContractData: ContractData = {
  contractName: "Master_Service_Agreement_v2.pdf",
  overallRisk: "HIGH",
  contractTitle: "MASTER SERVICE AGREEMENT",
  clauses: MOCK_CLAUSES,
  metadata: {
    contractType: "Master Service Agreement (MSA)",
    contractTitle: "Master_Service_Agreement_v2.pdf",
    contractingParties: "บริษัท เทคโซลูชั่น จำกัด (Tech Solution Co., Ltd.) & บริษัท เอคอมเมิร์ซ จำกัด (aCommerce Co., Ltd.)",
    contractExecutionDate: "18 กรกฎาคม 2026",
    effectiveDate: "1 สิงหาคม 2026",
    expirationDate: "31 กรกฎาคม 2029",
    contractValue: "5,500,000 บาท (THB)",
    contractTerm: "3 ปี (3 Years)",
  }
};


// ── Risk badge styles ──────────────────────────────────────────────────────────

const overallRiskStyle: Record<RiskLevel, string> = {
  LOW: "text-emerald-400",
  MEDIUM: "text-amber-400",
  HIGH: "text-red-400",
  CRITICAL: "text-rose-500",
};

// ── Page Component ─────────────────────────────────────────────────────────────

export default function ContractPage() {
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(
    MOCK_CLAUSES[0].id
  );

  const selectedClause =
    mockContractData.clauses.find((c) => c.id === selectedClauseId) ?? null;

  return (
    <div className="flex flex-col min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* ── Warning Banner ──────────────────────────────────────────────────── */}
      

      {/* ── Page Header ─────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-8 py-5 border-b border-white/10 bg-white/5 backdrop-blur-sm">
        <div className="space-y-0.5">
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            Contract Clause Risk Reviewer
          </h1>
          <p className="text-xs text-slate-500 font-medium tracking-wide">
            {mockContractData.contractName}
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Overall Risk */}
          <div className="text-right">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Overall Risk
            </p>
            <p
              className={`text-sm font-extrabold tracking-wide ${
                overallRiskStyle[mockContractData.overallRisk]
              }`}
            >
              {mockContractData.overallRisk.charAt(0) +
                mockContractData.overallRisk.slice(1).toLowerCase()}{" "}
              Risk
            </p>
          </div>

          {/* Export Button */}
          <button
            className="
              flex items-center gap-2 px-5 py-2.5 rounded-xl
              bg-slate-100 text-slate-900 text-sm font-semibold
              hover:bg-white transition-all duration-200
              shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95
            "
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            Export Report
          </button>
        </div>
      </header>

      {/* ── Main Content — Two-panel layout ────────────────────────────────── */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-6 p-6 min-h-0">
        {/* Left: Original Contract */}
        <OriginalContract
          contractTitle={mockContractData.contractTitle}
          clauses={mockContractData.clauses}
          selectedClauseId={selectedClauseId}
          onClauseSelect={setSelectedClauseId}
        />

        {/* Right: AI Risk Analysis */}
        <AIRiskAnalysis clause={selectedClause} metadata={mockContractData.metadata} />
      </main>
    </div>
  );
}