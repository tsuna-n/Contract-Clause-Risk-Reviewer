import {
  useCallback,
  useRef,
  useState,
  type DragEvent,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";
import { UploadCloud, FileText, X, CheckCircle2, AlertTriangle } from "lucide-react";
import PageIntro from "../component/PageIntro";
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
    <div className="upload-page h-full w-full text-white flex flex-col px-10 py-8 overflow-y-auto">
      <PageIntro eyebrow="YOUR REVIEW WORKSPACE" title="ตรวจสัญญาใหม่" description="เริ่มจากอัปโหลดเอกสาร แล้วให้ AI ช่วยแยกข้อสัญญาและประเมินความเสี่ยง" />
      <div className="upload-body">
      <div className="w-full max-w-[720px] flex flex-col items-center">
        {/* Upload zone */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          aria-label="เลือกไฟล์สัญญาเพื่อเริ่มตรวจ"
          onDragOver={(e: DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`w-full shrink-0 upload-zone rounded-2xl border border-dashed px-8 py-14 text-center cursor-pointer transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-navy-500
            ${dragging ? "border-teal-300 bg-teal-400/10" : "border-navy-600 bg-navy-900/60 hover:border-teal-400/60 hover:bg-teal-400/5"}`}
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
          <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-teal-400/10 border border-teal-400/20 flex items-center justify-center">
            <UploadCloud
              size={29}
              className={dragging ? "text-teal-200" : "text-teal-300"}
              strokeWidth={1.75}
            />
          </div>
          <div className="text-lg">
            <span className="text-teal-300 font-semibold">คลิกเพื่อเลือกไฟล์</span>
            <span className="text-white"> หรือลากมาวางตรงนี้</span>
          </div>
          <div className="text-[13px] text-slate-400 mt-1.5">
            รองรับ {ACCEPTED_EXTENSIONS.join(" และ ")} — ตรวจหนึ่งฉบับใช้เวลาหลายนาที
          </div>
        </div>

        {/* Manifest list */}
        {entries.length > 0 && (
          <div className="w-full mt-6 max-h-[40vh] overflow-y-auto pr-1">
            <div className="font-mono text-[11px] tracking-[0.1em] text-slate-400 uppercase mb-3 flex justify-between">
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
                  className={`manifest-item flex items-center bg-navy-900 border rounded-xl overflow-hidden ${
                    entry.status === "failed" ? "border-rose-500/40" : "border-navy-800"
                  } ${entry.report ? "cursor-pointer hover:border-navy-600" : ""}`}
                >
                  {/* sequence stub */}
                  <div className="w-11 self-stretch flex items-center justify-center font-mono text-xs text-slate-500 border-r border-dashed border-navy-800">
                    {String(entries.length - idx).padStart(2, "0")}
                  </div>

                  <div className="w-10 h-10 m-3.5 rounded-lg bg-navy-800 border border-navy-700 flex-shrink-0 flex items-center justify-center">
                    <FileText size={18} className="text-slate-400" strokeWidth={1.75} />
                  </div>

                  {/* meta */}
                  <div className="flex-1 min-w-0 py-2.5">
                    <div className="text-sm font-medium text-white overflow-hidden text-ellipsis whitespace-nowrap">
                      {entry.name}
                    </div>
                    <div className="font-mono text-[11.5px] text-slate-400 mt-0.5">
                      {formatBytes(entry.size)}
                      {entry.status === "reviewing" && " · กำลังตรวจ…"}
                      {entry.status === "done" &&
                        entry.report &&
                        ` · ${entry.report.clauses.length} ข้อสัญญา`}
                    </div>
                    {entry.message && (
                      <div className="text-[11.5px] text-rose-400 mt-1 leading-snug">
                        {entry.message}
                      </div>
                    )}
                  </div>

                  {/* status / remove */}
                  <div className="flex items-center gap-2.5 px-3.5 flex-shrink-0">
                    {entry.status === "reviewing" && (
                      <span className="w-4 h-4 rounded-full border-2 border-navy-500 border-t-transparent animate-spin" />
                    )}
                    {entry.status === "done" && (
                      <CheckCircle2 size={16} className="text-emerald-400" strokeWidth={2} />
                    )}
                    {entry.status === "failed" && (
                      <AlertTriangle size={16} className="text-rose-400" strokeWidth={2} />
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeEntry(entry.id);
                      }}
                      aria-label={`Remove ${entry.name}`}
                      className="bg-transparent border-none text-slate-400 cursor-pointer p-1 flex rounded-md hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy-500"
                    >
                      <X size={15} strokeWidth={2} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="upload-steps">
          <div><span>01</span><p>อัปโหลดเอกสาร<small>เลือกไฟล์สัญญาที่ต้องการตรวจ</small></p></div>
          <div><span>02</span><p>วิเคราะห์รายข้อ<small>ตรวจความเสี่ยงเทียบ Playbook</small></p></div>
          <div><span>03</span><p>ทบทวนผลการตรวจ<small>อ่านเหตุผลและรับรองผลด้วยตัวเอง</small></p></div>
        </div>
      </div>
      </div>
    </div>
  );
}
