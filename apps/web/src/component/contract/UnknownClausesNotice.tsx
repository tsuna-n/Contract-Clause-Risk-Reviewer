import type { ContractReport } from "./types";

/**
 * UnknownClausesNotice — says out loud that part of the review didn't happen.
 *
 * The pipeline isolates failures per clause on purpose, so a contract whose
 * every LLM call was rejected still comes back `200 OK` with a full-looking
 * report: the clauses are all there, each rated `unknown`. Nothing else on the
 * page distinguishes that from a review that ran and found nothing alarming —
 * a grey badge among green ones reads as "fine", and the summary line counts
 * "2 Unknown" the same way it counts "2 Low".
 *
 * That failure is routine rather than exotic: the Gemini free tier allows 20
 * requests a day and the pipeline spends roughly four per clause, so a single
 * mid-size contract exhausts it and every clause after that point comes back
 * unassessed.
 *
 * Both copies live here rather than in the two pages that use it, because the
 * thing being explained is the same in either language.
 */

interface UnknownClausesNoticeProps {
  report: ContractReport;
  /** Matches the surrounding page's chrome: `/contract` is English, `/manual` Thai. */
  locale?: "en" | "th";
  className?: string;
}

export default function UnknownClausesNotice({
  report,
  locale = "en",
  className = "",
}: UnknownClausesNoticeProps) {
  const unknown = report.summary.unknown;
  if (unknown === 0) return null;

  const total = report.clauses.length;
  const allFailed = unknown === total;

  const text =
    locale === "th"
      ? {
          headline: allFailed
            ? `ประเมินไม่สำเร็จทั้ง ${total} ข้อสัญญา`
            : `${unknown} จาก ${total} ข้อสัญญาประเมินไม่สำเร็จ`,
          body: "ข้อสัญญาเหล่านี้ยังไม่ได้ถูกวิเคราะห์ — ไม่ใช่ว่า “ไม่มีความเสี่ยง” ต้องอ่านเอง หรือลองตรวจใหม่อีกครั้ง",
          cause: "สาเหตุที่พบบ่อยคือโควตา Gemini หมด (free tier จำกัด 20 ครั้ง/วัน)",
        }
      : {
          headline: allFailed
            ? `None of the ${total} clauses could be assessed`
            : `${unknown} of ${total} clauses could not be assessed`,
          body: "These clauses were never analysed — this is not a finding of low risk. Read them yourself, or run the review again.",
          cause: "The usual cause is an exhausted Gemini quota (20 requests/day on the free tier).",
        };

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
          <p className="text-sm font-semibold text-amber-200">{text.headline}</p>
          <p className="text-xs leading-relaxed text-amber-100/80">{text.body}</p>
          <p className="text-[11px] leading-relaxed text-amber-200/50">{text.cause}</p>
        </div>
      </div>
    </div>
  );
}
