import {
  useCallback,
  useRef,
  useState,
  type DragEvent,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";
import { UploadCloud, FileText, X, CheckCircle2, AlertTriangle } from "lucide-react";
import type { ContractReport } from "../component/contract/types";
import {
  ACCEPTED_EXTENSIONS,
  ACCEPT_ATTRIBUTE,
  isSupportedFile,
  reviewContract,
} from "../lib/contracts";
import { ApiError } from "../lib/api";

interface FileUploadPageProps {
  /** เรียกเมื่อ POST /contracts/review สำเร็จ พร้อมรายงานฉบับเต็ม */
  onReviewComplete?: (report: ContractReport) => void;
  /** session ตาย (401) — ให้หน้าแม่พาไป /login */
  onUnauthorized?: () => void;
}

type EntryStatus = "reviewing" | "done" | "failed";

interface FileEntry {
  id: number;
  name: string;
  size: number;
  status: EntryStatus;
  /** ข้อความ error เมื่อ status === "failed" */
  message: string | null;
  /** report ที่ได้เมื่อสำเร็จ — กดที่รายการเพื่อเปิดดู */
  report: ContractReport | null;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 KB";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

let idCounter = 0;

/**
 * หน้าอัปโหลดสัญญา — ยิงเข้า POST /contracts/review จริง
 *
 * ไม่มีแถบ progress: request เดียวกินเวลาทั้ง pipeline (segment → classify →
 * match → score → judge) และ backend ไม่ได้ stream ความคืบหน้ากลับมา แถบที่เดิน
 * ตามเวลาที่เดาเองจึงเป็นได้แค่ภาพลวง — ตัวหมุนที่ไม่โกหกว่ารู้ว่าเหลืออีกเท่าไร
 * ตรงกับความจริงมากกว่า
 */
export default function FileUploadPage({
  onReviewComplete,
  onUnauthorized,
}: FileUploadPageProps = {}) {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const patch = useCallback((id: number, changes: Partial<FileEntry>) => {
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...changes } : e)));
  }, []);

  const ingest = useCallback(
    (fileList: FileList) => {
      for (const file of Array.from(fileList)) {
        const id = ++idCounter;
        const supported = isSupportedFile(file);

        setEntries((prev) => [
          {
            id,
            name: file.name,
            size: file.size,
            status: supported ? "reviewing" : "failed",
            message: supported
              ? null
              : `รองรับเฉพาะ ${ACCEPTED_EXTENSIONS.join(" และ ")} เท่านั้น`,
            report: null,
          },
          ...prev,
        ]);

        // นามสกุลที่ backend ไม่มี parser ให้ ตัดตั้งแต่ที่นี่ ไม่ต้องเสียเวลา
        // อัปโหลดไปให้โดน 422 กลับมา
        if (!supported) continue;

        void reviewContract(file)
          .then((report) => {
            patch(id, { status: "done", report });
            onReviewComplete?.(report);
          })
          .catch((err: unknown) => {
            if (err instanceof ApiError && err.isUnauthorized) {
              onUnauthorized?.();
              return;
            }
            patch(id, {
              status: "failed",
              message: err instanceof Error ? err.message : "ตรวจสัญญาไม่สำเร็จ",
            });
          });
      }
    },
    [patch, onReviewComplete, onUnauthorized]
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files?.length) ingest(e.dataTransfer.files);
    },
    [ingest]
  );

  const removeEntry = (id: number) => setEntries((prev) => prev.filter((e) => e.id !== id));

  return (
    <div className="h-full w-full bg-black text-white font-sans flex flex-col items-center justify-center px-6 py-8 overflow-y-auto">
      <style>{`
        .font-sans { font-family: 'Inter', ui-sans-serif, system-ui, sans-serif; }
        .font-mono-tix { font-family: ui-monospace, SFMono-Regular, monospace; }
        .manifest-item { animation: slideIn 0.35s ease both; }
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(-6px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div className="w-full max-w-[560px] flex flex-col items-center">
        {/* Upload zone */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e: KeyboardEvent<HTMLDivElement>) =>
            (e.key === "Enter" || e.key === " ") && inputRef.current?.click()
          }
          onDragOver={(e: DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`w-full shrink-0 rounded-2xl border-2 border-dashed px-8 py-10 text-center cursor-pointer transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#7C5CFC]
            ${dragging ? "border-[#7C5CFC] bg-[#7C5CFC]/[0.08]" : "border-[#3A3D47] bg-[#111114] hover:border-[#4A4D57]"}`}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            accept={ACCEPT_ATTRIBUTE}
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              if (e.target.files?.length) ingest(e.target.files);
              // เลือกไฟล์เดิมซ้ำจะไม่เกิด change event ถ้าไม่ล้างค่า — และการลอง
              // ใหม่หลังพลาดก็คือเคสนั้นพอดี
              e.target.value = "";
            }}
          />
          <div className="w-11 h-11 mx-auto mb-4 rounded-[10px] bg-[#1A1A1E] border border-[#2A2C33] flex items-center justify-center">
            <UploadCloud
              size={20}
              className={dragging ? "text-[#7C5CFC]" : "text-[#9A9DA6]"}
              strokeWidth={1.75}
            />
          </div>
          <div className="text-[15px]">
            <span className="text-[#A78BFA] font-semibold">คลิกเพื่อเลือกไฟล์</span>
            <span className="text-white"> หรือลากมาวางตรงนี้</span>
          </div>
          <div className="text-[13px] text-[#8A8D96] mt-1.5">
            รองรับ {ACCEPTED_EXTENSIONS.join(" และ ")} — ตรวจหนึ่งฉบับใช้เวลาหลายนาที
          </div>
        </div>

        {/* Manifest list */}
        {entries.length > 0 && (
          <div className="w-full mt-6 max-h-[40vh] overflow-y-auto pr-1">
            <div className="font-mono-tix text-[11px] tracking-[0.1em] text-[#8A8D96] uppercase mb-3 flex justify-between">
              <span>Manifest</span>
              <span>
                {entries.length} item{entries.length > 1 ? "s" : ""}
              </span>
            </div>

            <div className="flex flex-col gap-2.5">
              {entries.map((entry, idx) => (
                <div
                  key={entry.id}
                  onClick={() => entry.report && onReviewComplete?.(entry.report)}
                  className={`manifest-item flex items-center bg-[#111114] border rounded-xl overflow-hidden ${
                    entry.status === "failed" ? "border-[#7F2A34]" : "border-[#2A2C33]"
                  } ${entry.report ? "cursor-pointer hover:border-[#4A4D57]" : ""}`}
                >
                  {/* sequence stub */}
                  <div className="w-11 self-stretch flex items-center justify-center font-mono-tix text-xs text-[#6A6D76] border-r border-dashed border-[#2A2C33]">
                    {String(entries.length - idx).padStart(2, "0")}
                  </div>

                  <div className="w-10 h-10 m-3.5 rounded-lg bg-[#1A1A1E] border border-[#2A2C33] flex-shrink-0 flex items-center justify-center">
                    <FileText size={18} className="text-[#9A9DA6]" strokeWidth={1.75} />
                  </div>

                  {/* meta */}
                  <div className="flex-1 min-w-0 py-2.5">
                    <div className="text-sm font-medium text-white overflow-hidden text-ellipsis whitespace-nowrap">
                      {entry.name}
                    </div>
                    <div className="font-mono-tix text-[11.5px] text-[#8A8D96] mt-0.5">
                      {formatBytes(entry.size)}
                      {entry.status === "reviewing" && " · กำลังตรวจ…"}
                      {entry.status === "done" &&
                        entry.report &&
                        ` · ${entry.report.clauses.length} ข้อสัญญา`}
                    </div>
                    {entry.message && (
                      <div className="text-[11.5px] text-[#F87171] mt-1 leading-snug">
                        {entry.message}
                      </div>
                    )}
                  </div>

                  {/* status / remove */}
                  <div className="flex items-center gap-2.5 px-3.5 flex-shrink-0">
                    {entry.status === "reviewing" && (
                      <span className="w-4 h-4 rounded-full border-2 border-[#7C5CFC] border-t-transparent animate-spin" />
                    )}
                    {entry.status === "done" && (
                      <CheckCircle2 size={16} className="text-[#34D399]" strokeWidth={2} />
                    )}
                    {entry.status === "failed" && (
                      <AlertTriangle size={16} className="text-[#F87171]" strokeWidth={2} />
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeEntry(entry.id);
                      }}
                      aria-label={`Remove ${entry.name}`}
                      className="bg-transparent border-none text-[#8A8D96] cursor-pointer p-1 flex rounded-md hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#7C5CFC]"
                    >
                      <X size={15} strokeWidth={2} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
