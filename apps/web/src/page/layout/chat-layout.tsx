import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../../component/sidebar/Sidebar";
import type { ContractReport, ReportSummary } from "../../component/contract/types";
import { useAuth } from "../../lib/auth-context";
import { ApiError } from "../../lib/api";
import { deleteReport, fetchReport, fetchReportHistory } from "../../lib/contracts";
import FileUploadPage from "../chat";
import Detail from "../detail";

/**
 * หน้าหลักหลัง login: ประวัติการตรวจทางซ้าย + อัปโหลด/รายงานทางขวา
 *
 * เจ้าของ state ของประวัติอยู่ที่นี่ ไม่ใช่ใน Sidebar เพราะการอัปโหลดสำเร็จ
 * (เกิดในแผงขวา) ต้องทำให้รายการทางซ้ายอัปเดตด้วย ถ้า Sidebar ดึงข้อมูลเอง
 * สองฝั่งจะไม่มีทางรู้จักกัน
 */
function Chat() {
  const navigate = useNavigate();
  const { status, user, signOut } = useAuth();

  // "loading" is the initial value, not something the effect sets — the effect
  // gates on it and only writes state from settled-promise callbacks, so a
  // fetch never triggers a cascading render. Same shape as AuthProvider's
  // session probe. Re-requesting the history is a matter of putting the status
  // back to "loading" from an event handler.
  const [historyStatus, setHistoryStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // `selectedId` แยกจาก `selected` เพราะรายงานที่โหลดไม่สำเร็จก็ยังต้องรู้ว่า
  // จะ retry ตัวไหน — ตอนนั้น `selected` เป็น null ไปแล้ว
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<ContractReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  /** session ตายแล้วกู้ในหน้านี้ไม่ได้ — ส่งกลับไป login */
  const handleApiError = useCallback(
    (err: unknown, fallback: string): string | null => {
      if (err instanceof ApiError && err.isUnauthorized) {
        navigate("/login", { replace: true });
        return null;
      }
      return err instanceof Error ? err.message : fallback;
    },
    [navigate]
  );

  useEffect(() => {
    if (historyStatus !== "loading") return;

    // ประวัติอาจตอบกลับมาหลังผู้ใช้ออกจากหน้านี้ไปแล้ว — ธงนี้กันไม่ให้เขียน
    // state ทับของใหม่
    let cancelled = false;

    fetchReportHistory().then(
      (rows) => {
        if (cancelled) return;
        setReports(rows);
        setHistoryStatus("ready");
      },
      (err: unknown) => {
        if (cancelled) return;
        setHistoryError(handleApiError(err, "โหลดประวัติไม่สำเร็จ"));
        setHistoryStatus("failed");
      }
    );

    return () => {
      cancelled = true;
    };
  }, [historyStatus, handleApiError]);

  const reloadHistory = useCallback(() => {
    setHistoryError(null);
    setHistoryStatus("loading");
  }, []);

  /** เปิดรายงานจากประวัติ — summary ไม่มี clause ต้องดึงฉบับเต็มก่อน */
  const openReport = useCallback(
    async (reportId: string) => {
      setSelectedId(reportId);
      setSelected(null);
      setReportLoading(true);
      setReportError(null);
      try {
        setSelected(await fetchReport(reportId));
      } catch (err) {
        setReportError(handleApiError(err, "เปิดรายงานไม่สำเร็จ"));
      } finally {
        setReportLoading(false);
      }
    },
    [handleApiError]
  );

  const clearSelection = useCallback(() => {
    setSelectedId(null);
    setSelected(null);
    setReportError(null);
  }, []);

  const handleDeleteReport = useCallback(
    async (reportId: string) => {
      try {
        await deleteReport(reportId);
        if (selectedId === reportId) {
          clearSelection();
        }
        reloadHistory();
      } catch (err) {
        setHistoryError(handleApiError(err, "ลบรายงานไม่สำเร็จ"));
      }
    },
    [selectedId, clearSelection, reloadHistory, handleApiError]
  );

  /**
   * อัปโหลดเสร็จ: แสดงรายงานที่เพิ่งได้เลย ไม่ต้องดึงซ้ำ — response ของ
   * /contracts/review คือรายงานฉบับเต็มอยู่แล้ว ส่วนประวัติค่อยรีเฟรชตาม
   * เพื่อให้แถวใหม่ (พร้อม created_at ที่ backend ตั้ง) โผล่ทางซ้าย
   */
  const handleReviewComplete = useCallback(
    (report: ContractReport) => {
      setSelectedId(report.reportId);
      setSelected(report);
      setReportError(null);
      reloadHistory();
    },
    [reloadHistory]
  );

  const showDetail = selectedId !== null;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <div className="flex-1 rounded-lg p-4 overflow-hidden">
        <Sidebar
          reports={reports}
          loading={historyStatus === "loading"}
          error={historyError}
          selectedReportId={selectedId}
          onRetry={reloadHistory}
          onNewReview={clearSelection}
          onSelectReport={(summary) => void openReport(summary.reportId)}
          onDeleteReport={handleDeleteReport}

          // ข้อมูลจริงจากบัญชี Google ที่ล็อกอิน (มาจาก GET /auth/me)
          // name/picture เป็น null ได้ถ้าบัญชีไม่ได้แชร์มา จึงแปลงเป็น undefined
          // ให้ prop ที่เป็น optional ทำงานถูกทาง
          user={{
            isLoggedIn: status === "authed",
            isLoading: status === "checking",
            name: user?.name ?? undefined,
            email: user?.email,
            picture: user?.picture ?? undefined,
          }}
          onLogout={() => void signOut()}
        />
      </div>

      {/* Main Content */}
      <div className="flex-[3] m-3 rounded-lg flex flex-col h-[calc(100vh-1.5rem)]">
        <div className="flex-1 min-h-0 border-2 border-navy-700 rounded-lg my-1 overflow-hidden">
          {showDetail ? (
            <Detail
              report={selected}
              loading={reportLoading}
              error={reportError}
              onBack={clearSelection}
              onRetry={selectedId ? () => void openReport(selectedId) : undefined}
            />
          ) : (
            <FileUploadPage
              onReviewComplete={handleReviewComplete}
              onUnauthorized={() => navigate("/login", { replace: true })}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default Chat;
