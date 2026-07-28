import type { ContractReport } from "./types";

/**
 * IncompleteReviewNotice — says out loud when a review didn't actually happen.
 *
 * The backend answers `200 OK` for two failures that look like successes on
 * screen, and this covers both:
 *
 * 1. **No clauses at all.** A PDF with no text layer — a scan, a photo, an
 *    export that flattened the page to an image — parses without error and
 *    yields zero characters. The report still renders with a filename, an
 *    "unknown" verdict and an all-zero summary, and the clause panel says "no
 *    contract loaded" while the header names the file.
 * 2. **Clauses rated `unknown`.** The pipeline isolates failures per clause on
 *    purpose, so a contract whose LLM calls were all rejected still comes back
 *    complete-looking, every clause rated `unknown`. A grey badge among green
 *    ones reads as "fine", and the summary counts "2 Unknown" exactly the way
 *    it counts "2 Low". That failure is routine rather than exotic: the Gemini
 *    free tier allows 20 requests a day and the pipeline spends roughly four
 *    per clause.
 *
 * Both copies live here rather than in the pages that use it, because what is
 * being explained is the same in either language.
 */

interface IncompleteReviewNoticeProps {
  report: ContractReport;
  /** Matches the surrounding page's chrome: `/contract` is English, `/manual` Thai. */
  locale?: "en" | "th";
  className?: string;
}

export default function IncompleteReviewNotice({
  report,
  locale = "en",
  className = "",
}: IncompleteReviewNoticeProps) {
  const total = report.clauses.length;
  const unknown = report.summary.unknown;

  if (total === 0) {
    return (
      <Notice
        className={className}
        headline={
          locale === "th"
            ? "อ่านข้อความจากไฟล์นี้ไม่ได้เลย"
            : "No readable text was found in this file"
        }
        body={
          locale === "th"
            ? "ไม่พบข้อสัญญาสักข้อ แปลว่าไฟล์นี้ยังไม่ได้ถูกตรวจ ไม่ใช่ว่าตรวจแล้วไม่พบความเสี่ยง"
            : "Not a single clause was extracted, so nothing here has been reviewed — this is not a finding that the contract is clean."
        }
        cause={
          locale === "th"
            ? "มักเกิดกับ PDF ที่เป็นภาพสแกนหรือถ่ายรูป ซึ่งไม่มีชั้นข้อความให้ดึง — ต้องใช้ไฟล์ที่เลือกคัดลอกข้อความได้ (export จาก Word หรือทำ OCR มาก่อน)"
            : "This usually means a scanned or photographed PDF with no text layer. Use a file whose text can be selected and copied — export from Word, or run OCR first."
        }
      />
    );
  }

  if (unknown === 0) return null;

  const allFailed = unknown === total;
  return (
    <Notice
      className={className}
      headline={
        locale === "th"
          ? allFailed
            ? `ประเมินไม่สำเร็จทั้ง ${total} ข้อสัญญา`
            : `${unknown} จาก ${total} ข้อสัญญาประเมินไม่สำเร็จ`
          : allFailed
            ? `None of the ${total} clauses could be assessed`
            : `${unknown} of ${total} clauses could not be assessed`
      }
      body={
        locale === "th"
          ? "ข้อสัญญาเหล่านี้ยังไม่ได้ถูกวิเคราะห์ — ไม่ใช่ว่า “ไม่มีความเสี่ยง” ต้องอ่านเอง หรือลองตรวจใหม่อีกครั้ง"
          : "These clauses were never analysed — this is not a finding of low risk. Read them yourself, or run the review again."
      }
      cause={
        locale === "th"
          ? "สาเหตุที่พบบ่อยคือโควตา Gemini หมด (free tier จำกัด 20 ครั้ง/วัน)"
          : "The usual cause is an exhausted Gemini quota (20 requests/day on the free tier)."
      }
    />
  );
}

function Notice({
  headline,
  body,
  cause,
  className,
}: {
  headline: string;
  body: string;
  cause: string;
  className: string;
}) {
  return (
    <div
      role="status"
      className={`rounded-xl border border-amber-500/40 bg-amber-950/40 px-4 py-3 ${className}`}
    >
      <div className="flex items-start gap-3">
        <svg
          className="w-4 h-4 shrink-0 mt-0.5 text-amber-400"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
          />
        </svg>
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-semibold text-amber-200">{headline}</p>
          <p className="text-xs leading-relaxed text-amber-100/80">{body}</p>
          <p className="text-[11px] leading-relaxed text-amber-200/50">{cause}</p>
        </div>
      </div>
    </div>
  );
}
