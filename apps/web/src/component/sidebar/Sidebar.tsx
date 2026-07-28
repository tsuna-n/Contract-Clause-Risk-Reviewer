import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { ReportSummary } from '../contract/types';
import { riskAccent, riskBadge } from '../contract/riskStyles';
import { ACCEPTED_EXTENSIONS } from '../../lib/contracts';

export interface SidebarUser {
  isLoggedIn: boolean;
  /** ยังรอคำตอบจาก /auth/me อยู่ — แสดงสถานะกำลังโหลดแทนชื่อ Guest */
  isLoading?: boolean;
  name?: string;
  email?: string;
  /** รูปโปรไฟล์จาก Google (คีย์ picture ใน userinfo) */
  picture?: string;
}

interface SidebarProps {
  /** ประวัติการรีวิวจริงจาก GET /contracts (ใหม่สุดอยู่บน) */
  reports: ReportSummary[];
  /** ยังโหลดประวัติไม่เสร็จ — ต่างจาก "โหลดเสร็จแล้วแต่ไม่มีเรื่อง" */
  loading?: boolean;
  /** โหลดประวัติไม่สำเร็จ; ข้อความพร้อมแสดง */
  error?: string | null;
  /** report ที่เลือกอยู่ตอนนี้ ใช้ไฮไลต์รายการ */
  selectedReportId?: string | null;
  onNewReview?: () => void;
  onSelectReport?: (report: ReportSummary) => void;
  onRetry?: () => void;
  user?: SidebarUser;
  onLogout?: () => void;
}

// ตัวย่อสำหรับวงกลมโปรไฟล์ ใช้ตอนไม่มีรูปจาก Google หรือรูปโหลดไม่ขึ้น
function initialOf(name?: string, email?: string) {
  const source = name?.trim() || email?.trim() || '';
  return source ? source[0]!.toUpperCase() : '?';
}

const riskLabel: Record<string, string> = {
  HIGH: 'เสี่ยงสูง',
  MEDIUM: 'เสี่ยงปานกลาง',
  LOW: 'เสี่ยงต่ำ',
  UNKNOWN: 'ยังไม่ประเมิน',
};

// ชื่อไฟล์ที่อัปโหลดคือชื่อเรื่อง — ตัดนามสกุลออกเพราะซ้ำกับที่รู้อยู่แล้ว
function titleOf(report: ReportSummary) {
  return report.filename.replace(/\.(pdf|docx|txt)$/i, '') || report.contractId;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('th-TH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function Sidebar({
  reports,
  loading = false,
  error = null,
  selectedReportId = null,
  onNewReview,
  onSelectReport,
  onRetry,
  user,
  onLogout,
}: SidebarProps) {
  // รูปโปรไฟล์ Google ตอบ 429/403 ได้เมื่อโดน rate limit — ถ้าโหลดไม่ขึ้น
  // ให้ตกกลับไปใช้ตัวย่อ ไม่ปล่อยให้เห็นไอคอนรูปเสีย
  const [avatarFailed, setAvatarFailed] = useState(false);

  const isLoggedIn = user?.isLoggedIn ?? false;
  const isLoading = user?.isLoading ?? false;

  // ชื่อจาก Google อาจเป็น null ได้ (บางบัญชีไม่แชร์) แต่อีเมลมีเสมอ
  const displayName = isLoggedIn
    ? user?.name || user?.email || 'ผู้ใช้งาน'
    : isLoading
      ? 'กำลังโหลด…'
      : 'Guest';
  const displayEmail = isLoggedIn ? (user?.email ?? '') : isLoading ? '' : '***@gmail.com';
  const avatarUrl = isLoggedIn && !avatarFailed ? user?.picture : undefined;

  return (
    // เดิมใช้ min-h-screen + py-10 ทำให้ความสูงยืดตามเนื้อหา footer จึงไม่ชิดขอบล่างของกรอบ
    // เปลี่ยนเป็น h-screen (สูงคงที่เท่าจอ/กรอบ) และตัด padding แนวตั้งออก
    // แล้วค่อยใส่ padding ให้ container ด้านในแทน เพื่อให้ footer ล็อกอยู่ขอบล่างเสมอ
    <div className="h-screen bg-neutral-950 flex justify-center px-4 overflow-hidden">
      <div className="w-full max-w-2xl flex flex-col h-full py-10">
        {/* หัวข้อ */}
        <div className="mb-8 flex items-end justify-between border-b border-neutral-800 pb-5 flex-shrink-0">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-amber-500/70 mb-1">Legal desk</p>
            <h1 className="text-2xl font-semibold text-neutral-100" style={{ fontFamily: 'Georgia, "Noto Serif Thai", serif' }}>
              สัญญาที่ตรวจแล้ว
            </h1>
          </div>
          {/* ระหว่างโหลดยังไม่รู้จำนวน — เลี่ยงการโชว์ "0 ฉบับ" แล้วกระโดดเป็นเลขจริง */}
          <span className="text-xs text-neutral-500">
            {loading ? '' : `${reports.length} ฉบับ`}
          </span>
        </div>

        {/* เริ่มตรวจฉบับใหม่ — ล้าง selection กลับไปหน้าอัปโหลด */}
        <div className="mb-6 flex-shrink-0">
          <button
            onClick={onNewReview}
            className="px-4 py-2 text-sm font-medium bg-amber-500 text-neutral-950 rounded-lg hover:bg-amber-400 transition-colors"
          >
            + ตรวจสัญญาใหม่
          </button>
        </div>

        {/* Tools: ลิงก์ไปหน้าจัดการ Playbook / รัน Evaluation / สถานะระบบ
            แยกจากรายการสัญญา ไม่ใช่ "เรื่อง" เลยใส่เป็น row ของลิงก์เล็ก ๆ */}
        <div className="mb-6 flex-shrink-0 flex items-center gap-2 text-xs">
          <Link
            to="/playbook"
            className="flex-1 text-center px-2 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-colors"
          >
            Playbook
          </Link>
          <Link
            to="/evaluate"
            className="flex-1 text-center px-2 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-colors"
          >
            Evaluate
          </Link>
          <Link
            to="/system"
            className="flex-1 text-center px-2 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-colors"
          >
            System
          </Link>
        </div>

        {/* รายการสัญญา: เลื่อน (scroll) ได้เมื่อรายการเยอะเกินพื้นที่ */}
        {/* สไตล์ scrollbar ให้เข้ากับธีม: บาง โปร่ง สีเทาเข้ม และเปลี่ยนเป็นสีอำพันตอน hover */}
        <div
          className="space-y-3 flex-1 min-h-0 overflow-y-auto pr-2 -mr-2
            [&::-webkit-scrollbar]:w-1.5
            [&::-webkit-scrollbar-track]:bg-transparent
            [&::-webkit-scrollbar-thumb]:bg-neutral-800
            [&::-webkit-scrollbar-thumb]:rounded-full
            hover:[&::-webkit-scrollbar-thumb]:bg-amber-500/40"
          style={{ scrollbarWidth: 'thin', scrollbarColor: '#262626 transparent' }}
        >
          {error ? (
            <div className="text-center text-neutral-400 py-12 text-sm border border-dashed border-rose-500/40 rounded-xl px-4">
              <p className="text-rose-300 mb-3">{error}</p>
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="text-xs px-3 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-colors"
                >
                  ลองใหม่
                </button>
              )}
            </div>
          ) : loading ? (
            <div className="text-center text-neutral-600 py-16 text-sm border border-dashed border-neutral-800 rounded-xl">
              กำลังโหลดประวัติ...
            </div>
          ) : reports.length === 0 ? (
            <div className="text-center text-neutral-600 py-16 text-sm border border-dashed border-neutral-800 rounded-xl px-6 leading-relaxed">
              ยังไม่มีสัญญาที่ตรวจ
              <br />
              อัปโหลดไฟล์ {ACCEPTED_EXTENSIONS.join(' / ')} ทางขวาเพื่อเริ่ม
            </div>
          ) : (
            reports.map((report) => (
              <div
                key={report.reportId}
                onClick={() => onSelectReport?.(report)}
                className={`rounded-xl bg-neutral-900 border transition-colors px-5 py-4 cursor-pointer ${
                  report.reportId === selectedReportId
                    ? 'border-amber-500/50'
                    : 'border-neutral-800 hover:border-neutral-700'
                }`}
              >
                <h3 className="text-[15px] font-medium text-neutral-100 leading-snug mb-1 truncate">
                  {titleOf(report)}
                </h3>
                <p className="text-[11px] text-neutral-500 mb-2.5">
                  {formatDate(report.createdAt)} · {report.clauseCount} ข้อสัญญา
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium ${
                      riskBadge[report.overallRisk]
                    }`}
                  >
                    {riskLabel[report.overallRisk] ?? report.overallRisk}
                  </span>
                  {/* นับเฉพาะระดับที่มีจริง — "0 สูง" ไม่ได้บอกอะไรนอกจากรบกวนสายตา */}
                  {report.summary.high > 0 && (
                    <span className={`text-[11px] ${riskAccent.HIGH}`}>
                      สูง {report.summary.high}
                    </span>
                  )}
                  {report.summary.medium > 0 && (
                    <span className={`text-[11px] ${riskAccent.MEDIUM}`}>
                      กลาง {report.summary.medium}
                    </span>
                  )}
                  {report.summary.low > 0 && (
                    <span className={`text-[11px] ${riskAccent.LOW}`}>
                      ต่ำ {report.summary.low}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer: โปรไฟล์ผู้ใช้ + ปุ่ม logout — ล็อกอยู่ขอบล่างของกรอบเสมอ */}
        <div className="mt-4 pt-4 border-t border-neutral-800 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {/* วงกลมโปรไฟล์: รูปจาก Google ถ้ามี ไม่มีก็ใช้ตัวย่อของชื่อ */}
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={displayName}
                // Google ไม่ส่งรูปให้เมื่อมี referrer ข้ามโดเมน — ต้องปิด referrer
                referrerPolicy="no-referrer"
                onError={() => setAvatarFailed(true)}
                className="w-10 h-10 rounded-full border-2 border-neutral-700 object-cover flex-shrink-0"
              />
            ) : (
              <div className="w-10 h-10 rounded-full border-2 border-neutral-700 flex-shrink-0 flex items-center justify-center text-sm font-medium text-neutral-400">
                {isLoggedIn ? initialOf(user?.name, user?.email) : ''}
              </div>
            )}

            <div className="min-w-0">
              <p className="text-sm font-medium text-neutral-100 truncate">
                {displayName}
              </p>
              <p className="text-xs text-neutral-500 truncate" title={displayEmail}>
                {displayEmail}
              </p>
            </div>
          </div>

          {/* ปุ่ม logout (สัญลักษณ์) */}
          <button
            onClick={onLogout}
            aria-label="logout"
            title="ออกจากระบบ"
            className="p-2 rounded-lg text-neutral-500 hover:text-amber-400 hover:bg-neutral-900 transition-colors flex-shrink-0"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
