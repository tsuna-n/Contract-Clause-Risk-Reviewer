import type { ContractMetadataView } from "./types";

/**
 * ContractMetadataPanel — who signed what, when, for how much.
 *
 * Every value here is a quote: the backend extracts these from the document
 * and throws away anything it cannot find in the text word-for-word, so the
 * panel renders them as-is. In particular the dates are *not* reformatted —
 * "the 3rd day of March, 2019" is what the contract says, and turning it into
 * "2019-03-03" would replace a fact with an interpretation the reviewer can no
 * longer check against the page.
 *
 * Fields the document doesn't state are omitted rather than shown blank, and a
 * report with nothing extracted renders nothing at all. A row reading
 * "Parties: —" invites the reader to wonder what went wrong; the honest answer
 * is that the contract never said, and silence carries that better.
 */

interface ContractMetadataPanelProps {
  metadata: ContractMetadataView;
  /** Matches the surrounding page's chrome: `/contract` is English, `/manual` Thai. */
  locale?: "en" | "th";
  className?: string;
}

const LABELS = {
  en: {
    parties: "Parties",
    agreementDate: "Agreement date",
    effectiveDate: "Effective date",
    expirationDate: "Expires",
    contractValue: "Value",
    governingLaw: "Governing law",
  },
  th: {
    parties: "คู่สัญญา",
    agreementDate: "วันที่ทำสัญญา",
    effectiveDate: "วันที่มีผล",
    expirationDate: "สิ้นสุด",
    contractValue: "มูลค่า",
    governingLaw: "กฎหมายที่ใช้บังคับ",
  },
} as const;

export default function ContractMetadataPanel({
  metadata,
  locale = "en",
  className = "",
}: ContractMetadataPanelProps) {
  const labels = LABELS[locale];
  const fields: { label: string; value: string }[] = [];

  if (metadata.parties.length > 0) {
    fields.push({ label: labels.parties, value: metadata.parties.join(" · ") });
  }
  if (metadata.agreementDate) {
    fields.push({ label: labels.agreementDate, value: metadata.agreementDate });
  }
  if (metadata.effectiveDate) {
    fields.push({ label: labels.effectiveDate, value: metadata.effectiveDate });
  }
  if (metadata.expirationDate) {
    fields.push({ label: labels.expirationDate, value: metadata.expirationDate });
  }
  if (metadata.contractValue) {
    fields.push({ label: labels.contractValue, value: metadata.contractValue });
  }
  if (metadata.governingLaw) {
    fields.push({ label: labels.governingLaw, value: metadata.governingLaw });
  }

  if (fields.length === 0) return null;

  return (
    <dl
      className={`flex flex-wrap gap-x-8 gap-y-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3 ${className}`}
    >
      {fields.map((field) => (
        <div key={field.label} className="min-w-0 space-y-0.5">
          <dt className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
            {field.label}
          </dt>
          <dd className="text-sm text-slate-200 break-words">{field.value}</dd>
        </div>
      ))}
    </dl>
  );
}
