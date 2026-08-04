import type { ContractReport, RiskLevel } from '../contract/types';
import { riskAccent, riskBadge } from '../contract/riskStyles';

interface SideDetailProps {
  report: ContractReport;
  onClose: () => void;
}

const riskLabel: Record<string, string> = {
  HIGH: 'เสี่ยงสูง',
  MEDIUM: 'เสี่ยงปานกลาง',
  LOW: 'เสี่ยงต่ำ',
  UNKNOWN: 'ยังไม่ประเมิน',
};

// เรียงจากเสี่ยงมากไปน้อย — แถวบนสุดคือสิ่งที่ต้องดูก่อน
const RISK_ROWS: RiskLevel[] = ['HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'];

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('th-TH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

// SideDetail.tsx — แผงสรุปรายงานหนึ่งฉบับ แสดงเป็น sidebar ทางขวา
// ใช้คู่กับปุ่ม "ภาพรวม" ใน Detail.tsx โดยส่ง prop `report` เข้ามา
// และ `onClose` สำหรับปิดแผงกลับไปสถานะปกติ
function SideDetail({ report, onClose }: SideDetailProps) {
  const counts: Record<RiskLevel, number> = {
    HIGH: report.summary.high,
    MEDIUM: report.summary.medium,
    LOW: report.summary.low,
    UNKNOWN: report.summary.unknown,
  };
  const total = report.clauses.length;

  // จัดกลุ่มตามประเภทข้อสัญญาที่ classifier ตอบมา เรียงจากมากไปน้อย
  const byType = [...report.clauses.reduce((acc, clause) => {
    acc.set(clause.clauseType, (acc.get(clause.clauseType) ?? 0) + 1);
    return acc;
  }, new Map<string, number>())].sort((a, b) => b[1] - a[1]);

  return (
    <>
      {/* ฉากหลังจาง ๆ คลิกเพื่อปิด */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-navy-950/70 backdrop-blur-sm transition-opacity duration-200"
        aria-hidden="true"
      />

      {/* แผง sidebar ทางขวา */}
      <aside
        className="fixed inset-y-0 right-0 z-50 w-full max-w-sm border-l border-navy-800 bg-navy-950 shadow-2xl shadow-navy-950/50 overflow-y-auto transition-transform duration-300 ease-out"
        role="dialog"
        aria-label="ภาพรวมรายงาน"
      >
        <div className="px-6 py-6">
          {/* หัวแผง */}
          <div className="mb-6 flex items-start justify-between gap-3 border-b border-navy-800 pb-5">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.2em] text-navy-300 mb-1">ภาพรวม</p>
              <h2
                className="text-lg font-semibold text-white leading-snug break-words"
                style={{ fontFamily: 'Georgia, "Noto Serif Thai", serif' }}
              >
                {report.filename || report.contractId}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="shrink-0 rounded-full p-1.5 text-slate-500 hover:text-navy-200 hover:bg-navy-900 transition-colors"
              aria-label="ปิดแผงภาพรวม"
            >
              ✕
            </button>
          </div>

          {/* ความเสี่ยงรวม */}
          <div className="flex flex-wrap gap-2 mb-6">
            <span
              className={`px-3 py-1 rounded-full text-[11px] font-medium ${
                riskBadge[report.overallRisk]
              }`}
            >
              รวม: {riskLabel[report.overallRisk] ?? report.overallRisk}
            </span>
            <span className="px-3 py-1 rounded-full text-[11px] font-medium bg-navy-800 text-slate-300 ring-1 ring-navy-700">
              {total} ข้อสัญญา
            </span>
          </div>

          {/* กระจายความเสี่ยง — แถบสัดส่วนอ่านเร็วกว่าตัวเลขล้วน */}
          <div className="rounded-xl bg-navy-900 border border-navy-800 px-4 py-4 mb-4">
            <p className="text-xs uppercase tracking-wide text-slate-400 mb-3">
              กระจายความเสี่ยง
            </p>
            <div className="space-y-2.5">
              {RISK_ROWS.map((level) => (
                <div key={level} className="flex items-center gap-3">
                  <span className={`w-24 shrink-0 text-xs ${riskAccent[level]}`}>
                    {riskLabel[level]}
                  </span>
                  <div className="flex-1 h-1.5 rounded-full bg-navy-800 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        level === 'HIGH'
                          ? 'bg-red-400'
                          : level === 'MEDIUM'
                            ? 'bg-amber-400'
                            : level === 'LOW'
                              ? 'bg-emerald-400'
                              : 'bg-slate-500'
                      }`}
                      style={{ width: total ? `${(counts[level] / total) * 100}%` : '0%' }}
                    />
                  </div>
                  <span className="w-6 shrink-0 text-right text-xs text-slate-300">
                    {counts[level]}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* ประเภทข้อสัญญาที่พบ */}
          {byType.length > 0 && (
            <div className="rounded-xl bg-navy-900 border border-navy-800 px-4 py-4 mb-4">
              <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">
                ประเภทข้อสัญญาที่พบ
              </p>
              <div className="flex flex-wrap gap-2">
                {byType.map(([type, count]) => (
                  <span
                    key={type}
                    className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-navy-500/10 text-navy-300 ring-1 ring-navy-500/30"
                  >
                    {type.replace(/_/g, ' ')} · {count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ข้อมูลรายงาน */}
          <div className="rounded-xl bg-navy-900 border border-navy-800 px-4 py-4 mb-4 space-y-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">ตรวจเมื่อ</p>
              <p className="text-sm text-slate-200">{formatDate(report.createdAt)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">Report ID</p>
              <p className="text-xs text-slate-300 font-mono break-all">{report.reportId}</p>
            </div>
          </div>

          {report.disclaimer && (
            <p className="text-[11px] text-amber-200/70 leading-relaxed">{report.disclaimer}</p>
          )}
        </div>
      </aside>
    </>
  );
}

export default SideDetail;
