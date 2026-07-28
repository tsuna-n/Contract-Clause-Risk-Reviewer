import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { ContractReport } from '../component/contract/types';
import { riskAccent, riskBadge, riskRow, riskRowSelected } from '../component/contract/riskStyles';
import {
  ExportMenu,
  PrintableReport,
  IncompleteReviewNotice,
} from '../component/contract';
import SideDetail from '../component/sidebar/SideDetail';

interface DetailProps {
  /** รายงานฉบับเต็มจาก GET /contracts/{id}; null ระหว่างโหลด */
  report: ContractReport | null;
  loading?: boolean;
  error?: string | null;
  onBack?: () => void;
  onRetry?: () => void;
}

const riskLabel: Record<string, string> = {
  HIGH: 'เสี่ยงสูง',
  MEDIUM: 'เสี่ยงปานกลาง',
  LOW: 'เสี่ยงต่ำ',
  UNKNOWN: 'ยังไม่ประเมิน',
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('th-TH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

// Detail.tsx — มุมมองอ่านอย่างเดียวของรายงานหนึ่งฉบับ: ข้อสัญญาทั้งหมดพร้อมระดับ
// ความเสี่ยง เหตุผล และ citation ที่อ้างถึง playbook
//
// การแก้ระดับความเสี่ยง (override) ไม่ได้อยู่ที่นี่ — มันต้องใช้คู่กับตัวสัญญาต้นฉบับ
// จึงอยู่ที่ /contract ซึ่งเป็นหน้า workspace เต็มจอ ปุ่มด้านล่างพาไปที่นั่นพร้อม
// report id เดิม
function Detail({ report, loading = false, error = null, onBack, onRetry }: DetailProps) {
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(null);
  const [showOverview, setShowOverview] = useState(false);

  if (loading) {
    return (
      <div className="h-full bg-neutral-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-sm text-neutral-400">
          <span className="w-3.5 h-3.5 rounded-full border-2 border-amber-400 border-t-transparent animate-spin" />
          กำลังโหลดรายงาน...
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="h-full bg-neutral-950 flex items-center justify-center px-6">
        <div className="text-center max-w-sm">
          <p className="text-sm text-rose-300 mb-4">{error ?? 'ไม่พบรายงานฉบับนี้'}</p>
          <div className="flex items-center justify-center gap-2">
            {onRetry && (
              <button
                onClick={onRetry}
                className="text-xs px-3 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-colors"
              >
                ลองใหม่
              </button>
            )}
            {onBack && (
              <button
                onClick={onBack}
                className="text-xs px-3 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-colors"
              >
                กลับไปหน้าอัปโหลด
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full bg-neutral-950 overflow-hidden">
      {/* ส่วนเนื้อหา — scroll ได้อิสระ ไม่กระทบตำแหน่งปุ่มด้านล่าง */}
      <div className="h-full overflow-y-auto flex justify-center py-10 px-4">
        <div className="w-full max-w-2xl pb-28">
          {/* หัวข้อ + ปุ่มย้อนกลับ */}
          <div className="mb-8 border-b border-neutral-800 pb-5">
            {onBack && (
              <button
                onClick={onBack}
                className="mb-4 text-xs text-neutral-500 hover:text-amber-400 transition-colors flex items-center gap-1"
              >
                ← กลับไปหน้าอัปโหลด
              </button>
            )}
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-xs uppercase tracking-[0.2em] text-amber-500/70 mb-1">
                  {formatDate(report.createdAt)}
                </p>
                <h1
                  className="text-2xl font-semibold text-neutral-100 leading-snug break-words"
                  style={{ fontFamily: 'Georgia, "Noto Serif Thai", serif' }}
                >
                  {report.filename || report.contractId}
                </h1>
              </div>
              <ExportMenu
                report={report}
                className="shrink-0 flex items-center gap-1.5 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-neutral-300 transition-colors hover:border-amber-500/40 hover:text-amber-300"
              />
            </div>
          </div>

          {/* ความเสี่ยงรวม + จำนวนแต่ละระดับ */}
          <div className="flex flex-wrap items-center gap-2 mb-6">
            <span
              className={`px-3 py-1 rounded-full text-[11px] font-medium ${
                riskBadge[report.overallRisk]
              }`}
            >
              รวม: {riskLabel[report.overallRisk] ?? report.overallRisk}
            </span>
            <span className="px-3 py-1 rounded-full text-[11px] font-medium bg-neutral-800 text-neutral-300 ring-1 ring-neutral-700">
              {report.clauses.length} ข้อสัญญา
            </span>
          </div>

          {/* ข้อสัญญาที่ประเมินไม่สำเร็จก็ยังมี badge กับถูกนับใน summary เหมือนข้อที่
              ตรวจผ่าน — ต้องบอกให้ชัดตรงนี้ว่ามันคนละเรื่องกับ "ไม่มีความเสี่ยง" */}
          <IncompleteReviewNotice report={report} locale="th" className="mb-6" />

          {/* คำเตือนจาก backend — ติดมากับทุกรายงาน ไม่ใช่ข้อความที่ frontend แต่งเอง */}
          {report.disclaimer && (
            <p className="text-[11px] text-amber-200/70 leading-relaxed mb-6 rounded-lg bg-amber-950/30 border border-amber-500/20 px-4 py-3">
              {report.disclaimer}
            </p>
          )}

          {/* รายการข้อสัญญา — กดเพื่อกาง/พับรายละเอียด */}
          <div className="space-y-2.5">
            {report.clauses.length === 0 ? (
              <p className="text-center text-neutral-600 py-12 text-sm border border-dashed border-neutral-800 rounded-xl">
                ไม่พบข้อสัญญาในไฟล์นี้
              </p>
            ) : (
              report.clauses.map((clause) => {
                const open = clause.id === selectedClauseId;
                return (
                  <div
                    key={clause.id}
                    className={`rounded-xl px-5 py-4 cursor-pointer transition-colors ${
                      open ? riskRowSelected[clause.riskLevel] : riskRow[clause.riskLevel]
                    }`}
                    onClick={() => setSelectedClauseId(open ? null : clause.id)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-[15px] font-medium text-neutral-100 leading-snug">
                        {clause.title}
                      </h3>
                      <span
                        className={`shrink-0 px-2.5 py-0.5 rounded-full text-[11px] font-medium ${
                          riskBadge[clause.riskLevel]
                        }`}
                      >
                        {riskLabel[clause.riskLevel] ?? clause.riskLevel}
                      </span>
                    </div>

                    <p className="mt-2 text-sm text-neutral-400 leading-relaxed">
                      {open ? clause.text : clause.excerpt}
                    </p>

                    {open && (
                      <div className="mt-4 space-y-3 border-t border-white/10 pt-3">
                        {clause.rationale && (
                          <div>
                            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">
                              เหตุผลของ AI
                            </p>
                            <p className="text-sm text-neutral-200 leading-relaxed">
                              {clause.rationale}
                            </p>
                          </div>
                        )}

                        {clause.suggestedFallback && (
                          <div>
                            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">
                              ภาษาสำรองที่เสนอ
                            </p>
                            <p className="text-sm text-neutral-300 leading-relaxed italic">
                              {clause.suggestedFallback}
                            </p>
                          </div>
                        )}

                        {clause.citations.length > 0 && (
                          <div>
                            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1.5">
                              อ้างอิง playbook
                            </p>
                            <ul className="space-y-1.5">
                              {clause.citations.map((citation) => (
                                <li
                                  key={citation.id}
                                  className="text-xs text-neutral-400 leading-relaxed"
                                >
                                  <span className="text-amber-400/80 font-mono">
                                    {citation.playbookPositionId}
                                  </span>
                                  {' — '}
                                  {citation.excerpt}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* ผลตรวจของ judge: rationale อ้างอิงข้อความจริงใน playbook หรือไม่ */}
                        <p
                          className={`text-[11px] ${
                            clause.verified ? riskAccent.LOW : riskAccent.UNKNOWN
                          }`}
                        >
                          {clause.verified
                            ? '✓ ตรวจสอบแล้วว่าอ้างอิงจาก playbook จริง'
                            : '• ยังไม่ผ่านการตรวจ grounding — ควรอ่านทวนเอง'}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* แถบปุ่มด้านล่าง: แก้ความเสี่ยง (ซ้าย) / ภาพรวม (ขวา) */}
      <div className="absolute inset-x-0 bottom-0 z-40 pointer-events-none">
        <div className="px-4 sm:px-6 pb-6">
          <div className="relative h-14 flex items-end justify-between">
            {/* override ต้องดูคู่กับสัญญาต้นฉบับ จึงส่งต่อไปหน้า workspace */}
            <Link
              to={`/contract?report=${encodeURIComponent(report.reportId)}`}
              className="pointer-events-auto rounded-full bg-amber-500 px-5 py-3 text-xs font-semibold text-neutral-950 whitespace-nowrap text-center hover:bg-amber-400 transition-colors"
            >
              แก้ระดับความเสี่ยง
            </Link>

            <button
              onClick={() => setShowOverview(true)}
              className="pointer-events-auto w-28 rounded-full bg-neutral-900 border border-neutral-800 px-5 py-3 text-xs font-medium text-neutral-300 ring-1 ring-neutral-700 whitespace-nowrap text-center hover:text-amber-300 hover:ring-amber-500/30 transition-all duration-300"
            >
              ภาพรวม
            </button>
          </div>
        </div>
      </div>

      {/* แผงภาพรวมทางขวา */}
      {showOverview && <SideDetail report={report} onClose={() => setShowOverview(false)} />}

      {/* ซ่อนอยู่บนจอ — print stylesheet จะสลับมาแสดงตัวนี้แทนทั้งแอป */}
      <PrintableReport report={report} />
    </div>
  );
}

export default Detail;
