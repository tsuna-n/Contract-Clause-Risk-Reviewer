import WorkspaceHeader from "../component/WorkspaceHeader";
import PageIntro from "../component/PageIntro";
import { useCallback, useEffect, useState } from "react";
import { checkHealth, checkHealthDb, checkRoot } from "../lib/system";

type ProbeState = "pending" | "up" | "down";

interface Probe {
  label: string;
  path: string;
  state: ProbeState;
  /** The raw response body on success, or the error message on failure. */
  detail: string;
}

const INITIAL: Probe[] = [
  { label: "Service root", path: "GET /", state: "pending", detail: "" },
  { label: "Liveness", path: "GET /health", state: "pending", detail: "" },
  { label: "Database readiness", path: "GET /health/db", state: "pending", detail: "" },
];

function describeBody(body: unknown): string {
  try {
    return JSON.stringify(body);
  } catch {
    return String(body);
  }
}

export default function SystemPage() {
  const [probes, setProbes] = useState<Probe[]>(INITIAL);
  const [checking, setChecking] = useState<boolean>(true);

  // The probe work, isolated from any synchronous setState so the mount effect
  // can call it without tripping set-state-in-effect: every state write happens
  // after an `await` (a callback, not the effect body). Mirrors the AuthProvider
  // session probe.
  const probeAll = useCallback(async () => {
    const checks: { label: string; path: string; fn: () => Promise<unknown> }[] = [
      { label: "Service root", path: "GET /", fn: checkRoot },
      { label: "Liveness", path: "GET /health", fn: checkHealth },
      { label: "Database readiness", path: "GET /health/db", fn: checkHealthDb },
    ];

    // Each probe folds its own result into state by label, so one slow probe
    // (the DB) doesn't delay the others' badges.
    await Promise.allSettled(
      checks.map(async (check) => {
        try {
          const body = await check.fn();
          setProbes((prev) =>
            prev.map((p) =>
              p.label === check.label
                ? { ...p, state: "up", detail: describeBody(body) }
                : p,
            ),
          );
        } catch (err: unknown) {
          setProbes((prev) =>
            prev.map((p) =>
              p.label === check.label
                ? {
                    ...p,
                    state: "down",
                    detail: err instanceof Error ? err.message : String(err),
                  }
                : p,
            ),
          );
        }
      }),
    );
    setChecking(false);
  }, []);

  // Refresh button handler: a sync reset is fine here because this runs from a
  // click, not from an effect.
  const run = useCallback(() => {
    setChecking(true);
    setProbes(INITIAL.map((p) => ({ ...p })));
    void probeAll();
  }, [probeAll]);

  useEffect(() => {
    void probeAll();
  }, [probeAll]);

  return (
    <div className="tool-page min-h-screen text-slate-100 flex flex-col">
      <WorkspaceHeader actions={
        <button onClick={run} disabled={checking} className="secondary-button">{checking ? "Checking…" : "↻ Refresh"}</button>
      } />

      <main className="flex-1 max-w-6xl w-full mx-auto px-8 py-10 space-y-6">
        <PageIntro eyebrow="SERVICE MONITOR" title="System status" description="ตรวจสอบความพร้อมของบริการและการเชื่อมต่อฐานข้อมูล" aside={<span className="count-chip">{checking ? "กำลังตรวจสอบ…" : `${probes.filter(p => p.state === "up").length} / ${probes.length} services online`}</span>} />
        <div className="grid gap-4">
          {probes.map((probe) => (
            <div
              key={probe.label}
              className="bg-navy-900 border border-navy-800 rounded-2xl p-6 flex items-center justify-between gap-4"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-navy-100">{probe.label}</p>
                <p className="text-xs text-navy-400 font-mono">{probe.path}</p>
                {probe.detail && (
                  <p className="text-xs text-navy-300 mt-3 font-mono break-all">
                    {probe.detail}
                  </p>
                )}
              </div>
              <span
                className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase flex-shrink-0 ${
                  probe.state === "up"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : probe.state === "down"
                      ? "bg-red-500/20 text-red-400 border border-red-500/30"
                      : "bg-navy-800 text-navy-400 border border-navy-700"
                }`}
              >
                {probe.state === "pending" ? "…" : probe.state}
              </span>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
