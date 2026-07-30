import { createPortal } from "react-dom";
import type { ContractReport, RiskLevel } from "./types";

/**
 * PrintableReport — the paper version of a report, for print and Save as PDF.
 *
 * Rendered through a portal onto `document.body` and hidden until the print
 * stylesheet reveals it (see `.print-root` in index.css). Doing it this way
 * rather than restyling the app for print means the printed page owes nothing
 * to the screen layout: the app is a dark, scrolling, two-panel workspace, and
 * a printout of it would be a dark, clipped screenshot of a workspace.
 *
 * Deliberately styled with borders and text weight rather than fills —
 * browsers drop background colours when printing unless the user opts into
 * background graphics, so a design that leans on them prints as blank boxes.
 */

interface PrintableReportProps {
  report: ContractReport;
}

const riskLabel: Record<RiskLevel, string> = {
  HIGH: "HIGH",
  MEDIUM: "MEDIUM",
  LOW: "LOW",
  UNKNOWN: "NOT ASSESSED",
};

function formatDate(iso: string): string {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.valueOf()) ? iso : parsed.toLocaleString();
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: "6pt" }}>
      <div
        style={{
          fontSize: "7.5pt",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "#555",
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: "9.5pt", lineHeight: 1.5 }}>{children}</div>
    </div>
  );
}

/** The metadata the document actually stated, as label/value pairs. */
function metadataPairs(report: ContractReport): [string, string][] {
  const { metadata } = report;
  const pairs: [string, string | null][] = [
    ["Parties", metadata.parties.join(" · ") || null],
    ["Agreement date", metadata.agreementDate],
    ["Effective date", metadata.effectiveDate],
    ["Expires", metadata.expirationDate],
    ["Value", metadata.contractValue],
    ["Governing law", metadata.governingLaw],
  ];
  return pairs.filter((pair): pair is [string, string] => Boolean(pair[1]));
}

export default function PrintableReport({ report }: PrintableReportProps) {
  const { summary } = report;
  const metadataRows = metadataPairs(report);

  return createPortal(
    <div
      className="print-root"
      style={{
        color: "#000",
        background: "#fff",
        fontFamily: 'Georgia, "Noto Serif Thai", serif',
        padding: "0",
      }}
    >
      {/* Masthead */}
      <header style={{ borderBottom: "2pt solid #000", paddingBottom: "8pt" }}>
        <div style={{ fontSize: "8pt", letterSpacing: "0.18em", textTransform: "uppercase" }}>
          Contract Clause Risk Review
        </div>
        <h1 style={{ fontSize: "16pt", margin: "4pt 0 0", lineHeight: 1.25 }}>
          {report.filename || report.contractId}
        </h1>
        <div style={{ fontSize: "8.5pt", color: "#444", marginTop: "4pt" }}>
          Reviewed {formatDate(report.createdAt)} · Report {report.reportId}
        </div>
      </header>

      {/* Verdict + counts */}
      <section style={{ marginTop: "10pt", fontSize: "10pt" }}>
        <strong>Overall risk: {riskLabel[report.overallRisk]}</strong>
        <span style={{ color: "#444" }}>
          {"  ·  "}
          {report.clauses.length} clauses ·{" "}
          {`${summary.high} high, ${summary.medium} medium, ${summary.low} low, ${summary.unknown} not assessed`}
        </span>
      </section>

      {/* The same caveat the screen shows: an unassessed clause is not a safe
          one, and on paper there is no badge colour left to carry that. */}
      {summary.unknown > 0 && (
        <p
          style={{
            marginTop: "8pt",
            padding: "6pt 8pt",
            border: "1pt solid #000",
            fontSize: "9pt",
            lineHeight: 1.45,
          }}
        >
          <strong>
            {summary.unknown} of {report.clauses.length} clauses could not be assessed
            automatically.
          </strong>{" "}
          They are marked NOT ASSESSED below. This is not a finding of low risk — those
          clauses were never evaluated and still need to be read.
        </p>
      )}

      {/* Contract-level facts, quoted from the document. Whoever reads the
          printout has no page to check them against, so they belong on it. */}
      {metadataRows.length > 0 && (
        <section style={{ marginTop: "10pt", fontSize: "9pt", lineHeight: 1.5 }}>
          {metadataRows.map(([label, value]) => (
            <div key={label}>
              <strong>{label}:</strong> {value}
            </div>
          ))}
        </section>
      )}

      {report.disclaimer && (
        <p style={{ marginTop: "8pt", fontSize: "8.5pt", color: "#444", lineHeight: 1.45 }}>
          {report.disclaimer}
        </p>
      )}

      {/* Clauses */}
      <section style={{ marginTop: "12pt" }}>
        {report.clauses.map((clause, index) => (
          <article
            key={clause.id}
            style={{
              // Splitting a clause across a page break separates a risk rating
              // from the text it rates.
              breakInside: "avoid",
              borderTop: "0.5pt solid #999",
              paddingTop: "8pt",
              marginTop: "10pt",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "12pt" }}>
              <h2 style={{ fontSize: "11pt", margin: 0, lineHeight: 1.3 }}>
                {index + 1}. {clause.title}
              </h2>
              <div style={{ fontSize: "9pt", whiteSpace: "nowrap", fontWeight: 700 }}>
                {riskLabel[clause.riskLevel]}
              </div>
            </div>

            <div style={{ fontSize: "8pt", color: "#555", marginTop: "2pt" }}>
              {clause.clauseType.replace(/_/g, " ")}
              {clause.page !== null && ` · page ${clause.page}`}
              {` · ${clause.verified ? "grounded in playbook" : "not grounded — verify manually"}`}
              {/* A printed report is what gets circulated and filed, so the
                  sign-off has to travel with it. */}
              {clause.accepted && ` · accepted by ${clause.acceptedBy ?? "reviewer"}`}
            </div>

            <Field label="Clause text">{clause.text}</Field>

            {clause.rationale && <Field label="AI rationale">{clause.rationale}</Field>}

            {clause.suggestedFallback && (
              <Field label="Suggested fallback">
                <em>{clause.suggestedFallback}</em>
              </Field>
            )}

            {clause.citations.length > 0 && (
              <Field label="Playbook citations">
                <ul style={{ margin: "2pt 0 0", paddingLeft: "14pt" }}>
                  {clause.citations.map((citation) => (
                    <li key={citation.id} style={{ marginBottom: "3pt" }}>
                      <span style={{ fontFamily: "ui-monospace, monospace", fontSize: "8.5pt" }}>
                        {citation.playbookPositionId}
                      </span>
                      {" — "}
                      {citation.excerpt}
                    </li>
                  ))}
                </ul>
              </Field>
            )}
          </article>
        ))}
      </section>

      <footer
        style={{
          marginTop: "16pt",
          paddingTop: "6pt",
          borderTop: "0.5pt solid #999",
          fontSize: "8pt",
          color: "#555",
        }}
      >
        Exported {new Date().toLocaleString()} · Contract Clause Risk Reviewer
      </footer>
    </div>,
    document.body
  );
}
