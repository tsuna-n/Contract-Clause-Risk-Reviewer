import { useState } from "react";
import type { Clause } from "./types";
import AIRiskAnalysis from "./AIRiskAnalysis";

// ── Mock test data (1 full dataset for system testing) ─────────────────────────
export const MOCK_CLAUSES: Clause[] = [
  {
    id: "mock-1",
    title: "Confidentiality",
    text: "Each party shall hold the other's Confidential Information in strict confidence for a period of three (3) years from the date of disclosure.",
    riskLevel: "LOW",
    excerpt:
      "Each party shall hold the other's Confidential Information in strict confidence for a period of three (3) years.",
    playbookMatch: "Playbook §2.1: Standard NDA",
    aiRationale:
      "ระยะเวลาการรักษาความลับ 3 ปี เป็นไปตามมาตรฐานของบริษัท ถือว่าอยู่ในเกณฑ์มาตรฐานและยอมรับได้",
    suggestedFallback: "No standard fallback available. Clause is acceptable as is.",
    citations: ["KB-REF-021"],
  },
  {
    id: "mock-2",
    title: "Liability",
    text: "Supplier shall have unlimited liability for any breach of this Agreement, including all direct, indirect, and consequential damages.",
    riskLevel: "HIGH",
    excerpt:
      "Supplier shall have unlimited liability for any breach of this Agreement, including all direct, indirect, and consequential damages.",
    playbookMatch: "Playbook §4.3: Liability Cap",
    aiRationale:
      "ข้อกำหนดความรับผิดไม่จำกัดนี้เป็นความเสี่ยงสูง ควรกำหนดเพดานไม่เกิน 2 เท่าของค่าบริการในช่วง 12 เดือนที่ผ่านมา",
    suggestedFallback:
      "Supplier's total liability shall not exceed two (2) times the fees paid in the twelve (12) months preceding the claim.",
    citations: ["KB-REF-044", "KB-REF-078"],
  },
  {
    id: "mock-3",
    title: "Intellectual Property",
    text: "All inventions developed under this Agreement shall be solely owned by the Customer, including pre-existing IP of the Supplier.",
    riskLevel: "CRITICAL",
    excerpt:
      "All inventions developed under this Agreement shall be solely owned by the Customer, including pre-existing IP of the Supplier.",
    playbookMatch: "Playbook §5.1: IP Ownership",
    aiRationale:
      "การโอนกรรมสิทธิ์รวมถึง IP ที่มีอยู่ก่อนของ Supplier ถือเป็นความเสี่ยงร้ายแรง ควรจำกัดเฉพาะงานที่สร้างภายใต้สัญญานี้เท่านั้น",
    suggestedFallback:
      "All work product created specifically under this Agreement shall be owned by Customer. Supplier retains all pre-existing intellectual property.",
    citations: ["KB-REF-012", "KB-REF-019", "KB-REF-055"],
  },
  {
    id: "mock-4",
    title: "Termination",
    text: "Either party may terminate this Agreement with thirty (30) days written notice. Upon termination, Customer shall pay all outstanding fees within five (5) business days.",
    riskLevel: "MEDIUM",
    excerpt: "Either party may terminate this Agreement with thirty (30) days written notice.",
    playbookMatch: "Playbook §6.2: Termination for Convenience",
    aiRationale:
      "ระยะเวลาบอกเลิกสัญญา 30 วันอาจสั้นเกินไปสำหรับการถ่ายโอนงาน ควรเจรจาขยายเป็น 90 วัน",
    suggestedFallback:
      "Either party may terminate this Agreement with ninety (90) days written notice to allow adequate transition time.",
    citations: ["KB-REF-033"],
  },
];

// ── Props ──────────────────────────────────────────────────────────────────────
interface OriginalContractProps {
  contractTitle?: string;
  clauses?: Clause[];
  /** Pass from parent to control externally; omit to use internal state (standalone/test mode) */
  selectedClauseId?: string | null;
  onClauseSelect?: (id: string) => void;
}

const riskBorderColor: Record<string, string> = {
  LOW: "border-l-4 border-emerald-400 bg-emerald-950/30",
  MEDIUM: "border-l-4 border-amber-400 bg-amber-950/30",
  HIGH: "border-l-4 border-red-400 bg-red-950/30",
  CRITICAL: "border-l-4 border-rose-600 bg-rose-950/40",
};

const riskBorderSelected: Record<string, string> = {
  LOW: "border-l-4 border-emerald-400 bg-emerald-900/50 ring-2 ring-emerald-400/40",
  MEDIUM: "border-l-4 border-amber-400 bg-amber-900/50 ring-2 ring-amber-400/40",
  HIGH: "border-l-4 border-red-400 bg-red-900/50 ring-2 ring-red-400/40",
  CRITICAL: "border-l-4 border-rose-600 bg-rose-900/50 ring-2 ring-rose-600/40",
};

export default function OriginalContract({

  clauses = MOCK_CLAUSES,
  selectedClauseId: externalSelectedId,
  onClauseSelect: externalOnSelect,
}: OriginalContractProps) {
  // Internal state for standalone / test mode — used when parent doesn't control selection
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(
    MOCK_CLAUSES[0].id
  );

  const isControlled = externalSelectedId !== undefined;
  const selectedClauseId = isControlled ? externalSelectedId : internalSelectedId;
  const handleSelect = (id: string) => {
    if (!isControlled) setInternalSelectedId(id);
    externalOnSelect?.(id);
  };

  const selectedClause = clauses.find((c) => c.id === selectedClauseId) ?? null;
  const [file, setFile] = useState<File | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file) {
      alert("Please select a contract file");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/contract/api/v1", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      console.log("Upload Success:", result);
    } catch (error) {
      console.error("Upload Error:", error);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
      {/* Panel Header */}
      <div className="px-6 py-4 border-b border-white/10 bg-white/5">
        <h2 className="text-base font-semibold flex justify-between text-slate-100 tracking-wide">
          Original Contract
          <form onSubmit={handleSubmit} >
            <button
              className="
              flex items-center gap-2 px-5 py-2.5 rounded-xl
              bg-slate-100 text-slate-900 text-sm font-semibold
              hover:bg-white transition-all duration-200
              shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95
              cursor-pointer
            "
              onClick={() => document.getElementById("contract-file-input")?.click()}
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
            </button>
          </form>

        </h2>
      </div>

      {/* ── Two-column test layout when standalone (no external control) ─────── */}
      {!isControlled ? (
        <div className="flex flex-1 min-h-0 gap-0">
          {/* Left: clause list */}
          <div className="flex flex-col flex-1 min-w-0">
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
              {clauses.map((clause, index) => {
                const isSelected = selectedClauseId === clause.id;
                const baseClass = isSelected
                  ? riskBorderSelected[clause.riskLevel]
                  : riskBorderColor[clause.riskLevel];
                return (
                  <div
                    key={clause.id}
                    onClick={() => handleSelect(clause.id)}
                    className={`
                      relative rounded-r-xl p-4 cursor-pointer
                      transition-all duration-200 ease-in-out
                      ${baseClass}
                      hover:brightness-110 hover:shadow-lg
                    `}
                  >
                    <p className="text-sm text-slate-200 leading-relaxed">
                      <span className="font-bold text-slate-100">
                        {index + 1}. {clause.title}.
                      </span>{" "}
                      {clause.text}
                    </p>
                  </div>
                );
              })}
            </div>

            {/* Import Footer */}
            <div className="px-6 py-4 border-t border-white/10 bg-white/5">
              <input
                id="contract-file-input"
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) console.log("Importing contract:", file.name, file.type);


                }}
              />
              <button
                onClick={() => document.getElementById("contract-file-input")?.click()}
                className="
                  w-full flex items-center justify-center gap-2.5
                  py-3 rounded-xl text-sm font-semibold
                  border border-dashed border-slate-600
                  text-slate-300 hover:text-white
                  hover:border-slate-400 hover:bg-slate-700/40
                  transition-all duration-200 ease-in-out
                  hover:shadow-lg active:scale-95
                "
              >
                <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Import Contract
                <span className="text-xs text-slate-500 font-normal">.pdf · .docx · .txt</span>
              </button>
            </div>
          </div>

          {/* Right: AI Risk Analysis panel (standalone test mode) */}
          <div className="flex-1 border-l border-white/10 min-w-0">
            <AIRiskAnalysis clause={selectedClause} />
          </div>
        </div>
      ) : (
        /* Controlled mode — just the clause list */
        <>
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
            {clauses.map((clause, index) => {
              const isSelected = selectedClauseId === clause.id;
              const baseClass = isSelected
                ? riskBorderSelected[clause.riskLevel]
                : riskBorderColor[clause.riskLevel];
              return (
                <div
                  key={clause.id}
                  onClick={() => handleSelect(clause.id)}
                  className={`
                    relative rounded-r-xl p-4 cursor-pointer
                    transition-all duration-200 ease-in-out
                    ${baseClass}
                    hover:brightness-110 hover:shadow-lg
                  `}
                >
                  <p className="text-sm text-slate-200 leading-relaxed">
                    <span className="font-bold text-slate-100">
                      {index + 1}. {clause.title}.
                    </span>{" "}
                    {clause.text}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Import Footer */}
          <div className="px-6 py-4 border-t border-white/10 bg-white/5">
            <input
              id="contract-file-input"
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              className="hidden"
              onChange={(e) => {
                const selectedFile = e.target.files?.[0];

                if (selectedFile) {
                  setFile(selectedFile);
                  console.log(
                    "Importing contract:",
                    selectedFile.name,
                    selectedFile.type
                  );
                }
              }}
            />

          </div>
        </>
      )}
    </div>
  );
}

