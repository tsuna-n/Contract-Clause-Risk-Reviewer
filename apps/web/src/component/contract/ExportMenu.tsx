import { useEffect, useRef, useState } from "react";
import type { ContractReport } from "./types";
import { downloadReportCsv, downloadReportJson } from "../../lib/export";

/**
 * ExportMenu — download the report on screen, or send it to the printer.
 *
 * Everything here runs in the browser against the report already in memory;
 * the backend has no export endpoint and none is needed. Print relies on
 * `PrintableReport` being mounted by the page, which is what `window.print()`
 * ends up rendering.
 */

interface ExportMenuProps {
  report: ContractReport;
  /** Extra classes for the trigger, so each page can match its own chrome. */
  className?: string;
}

export default function ExportMenu({ report, className = "" }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // A menu that survives a click elsewhere on the page reads as stuck.
  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const run = (action: () => void) => {
    setOpen(false);
    action();
  };

  const items: { label: string; hint: string; onSelect: () => void }[] = [
    {
      label: "JSON",
      hint: "Full report data",
      onSelect: () => downloadReportJson(report),
    },
    {
      label: "CSV",
      hint: "One row per clause, for Excel",
      onSelect: () => downloadReportCsv(report),
    },
    {
      label: "Print / Save as PDF",
      hint: "Opens the print dialog",
      // The menu has to be closed *and painted* before the print dialog
      // freezes the page, or it prints into the screenshot the browser takes.
      onSelect: () => requestAnimationFrame(() => window.print()),
    },
  ];

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={className}
      >
        Export
        <svg
          className="w-3 h-3 shrink-0"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.5}
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-2 z-50 w-60 overflow-hidden rounded-xl border border-neutral-700 bg-neutral-900 shadow-2xl shadow-black/50"
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              onClick={() => run(item.onSelect)}
              className="block w-full px-4 py-2.5 text-left transition-colors hover:bg-neutral-800 focus-visible:bg-neutral-800 focus-visible:outline-none"
            >
              <span className="block text-sm font-medium text-neutral-100">{item.label}</span>
              <span className="block text-[11px] text-neutral-500">{item.hint}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
