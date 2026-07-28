import { useState, type MouseEvent } from 'react';
import { Trash2, Plus, LogOut, BookOpen, ShieldCheck, Cpu, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ReportSummary } from '../contract/types';
import { riskAccent, riskBadge } from '../contract/riskStyles';
import { ACCEPTED_EXTENSIONS } from '../../lib/contracts';

export interface SidebarUser {
  isLoggedIn: boolean;
  isLoading?: boolean;
  name?: string;
  email?: string;
  picture?: string;
}

interface SidebarProps {
  reports: ReportSummary[];
  loading?: boolean;
  error?: string | null;
  selectedReportId?: string | null;
  onNewReview?: () => void;
  onSelectReport?: (report: ReportSummary) => void;
  onDeleteReport?: (reportId: string) => void | Promise<void>;
  onRetry?: () => void;
  user?: SidebarUser;
  onLogout?: () => void;
}

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
  onDeleteReport,
  onRetry,
  user,
  onLogout,
}: SidebarProps) {
  const [avatarFailed, setAvatarFailed] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const isLoggedIn = user?.isLoggedIn ?? false;
  const isLoading = user?.isLoading ?? false;

  const displayName = isLoggedIn
    ? user?.name || user?.email || 'ผู้ใช้งาน'
    : isLoading
      ? 'กำลังโหลด…'
      : 'Guest';
  const displayEmail = isLoggedIn ? (user?.email ?? '') : isLoading ? '' : '***@gmail.com';
  const avatarUrl = isLoggedIn && !avatarFailed ? user?.picture : undefined;

  async function handleDelete(e: MouseEvent, reportId: string) {
    e.stopPropagation();
    if (!onDeleteReport) return;
    if (!window.confirm('คุณต้องการลบรายงานสัญญานี้ออกจากระบบหรือไม่?')) return;

    try {
      setDeletingId(reportId);
      await onDeleteReport(reportId);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="h-screen bg-neutral-950 flex justify-center px-4 overflow-hidden">
      <div className="w-full max-w-2xl flex flex-col h-full py-10">
        <div className="mb-8 flex items-end justify-between border-b border-neutral-800 pb-5 flex-shrink-0">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-amber-500/70 mb-1 font-mono">Legal desk</p>
            <h1 className="text-2xl font-semibold text-neutral-100" style={{ fontFamily: 'Georgia, "Noto Serif Thai", serif' }}>
              สัญญาที่ตรวจแล้ว
            </h1>
          </div>
          <span className="text-xs text-neutral-500 font-medium">
            {loading ? '' : `${reports.length} ฉบับ`}
          </span>
        </div>

        <div className="mb-6 flex-shrink-0 flex items-center justify-between">
          <button
            onClick={onNewReview}
            className="px-4 py-2 text-sm font-medium bg-amber-500 text-neutral-950 rounded-lg hover:bg-amber-400 active:scale-[0.98] transition-all flex items-center gap-2 shadow-sm font-sans"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>ตรวจสัญญาใหม่</span>
          </button>
        </div>

        <div className="mb-6 flex-shrink-0 flex items-center gap-2 text-xs">
          <Link
            to="/playbook"
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-all group"
          >
            <BookOpen className="w-3.5 h-3.5 text-neutral-400 group-hover:text-amber-300 transition-colors" />
            <span>Playbook</span>
          </Link>
          <Link
            to="/evaluate"
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-all group"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-neutral-400 group-hover:text-amber-300 transition-colors" />
            <span>Evaluate</span>
          </Link>
          <Link
            to="/system"
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 hover:border-amber-500/40 hover:text-amber-300 transition-all group"
          >
            <Cpu className="w-3.5 h-3.5 text-neutral-400 group-hover:text-amber-300 transition-colors" />
            <span>System</span>
          </Link>
        </div>

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
                className={`rounded-xl bg-neutral-900 border transition-all px-5 py-4 cursor-pointer relative group ${
                  report.reportId === selectedReportId
                    ? 'border-amber-500/50 bg-neutral-900/90 shadow-sm'
                    : 'border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900/60'
                }`}
              >
                <div className="flex items-start justify-between gap-3 mb-1">
                  <h3 className="text-[15px] font-medium text-neutral-100 leading-snug truncate flex-1" title={titleOf(report)}>
                    {titleOf(report)}
                  </h3>
                  <button
                    type="button"
                    disabled={deletingId === report.reportId}
                    onClick={(e) => void handleDelete(e, report.reportId)}
                    title="ลบรายงานนี้ออกจากระบบ"
                    aria-label="ลบรายงาน"
                    className="p-1.5 -mr-1.5 -mt-1 rounded-lg text-neutral-500 opacity-60 group-hover:opacity-100 hover:text-rose-400 hover:bg-rose-500/10 transition-all flex-shrink-0 disabled:opacity-50"
                  >
                    {deletingId === report.reportId ? (
                      <Loader2 className="w-4 h-4 animate-spin text-rose-400" />
                    ) : (
                      <Trash2 className="w-4 h-4 transition-transform hover:scale-110" />
                    )}
                  </button>
                </div>

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

        <div className="mt-4 pt-4 border-t border-neutral-800 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={displayName}
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

          <button
            onClick={onLogout}
            aria-label="logout"
            title="ออกจากระบบ"
            className="p-2 rounded-lg text-neutral-400 hover:text-amber-400 hover:bg-neutral-900 transition-colors flex-shrink-0 flex items-center justify-center"
          >
            <LogOut className="w-4.5 h-4.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;

