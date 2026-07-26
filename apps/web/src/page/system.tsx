import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
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
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans">
      <header className="border-b border-neutral-800 bg-neutral-900/80 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to="/manual" className="text-amber-500 font-serif text-xl font-bold tracking-wide">
            Contract Risk Reviewer
          </Link>
          <span className="text-neutral-600">/</span>
          <h1 className="text-neutral-200 text-lg font-medium">System Status</h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => void run()}
            disabled={checking}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-neutral-800 text-neutral-300 hover:bg-neutral-700 disabled:opacity-50 transition"
          >
            {checking ? "Checking…" : "Refresh"}
          </button>
          <Link
            to="/manual"
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-neutral-800 text-neutral-300 hover:bg-neutral-700 transition"
          >
            ← Back to App
          </Link>
        </div>
      </header>

      <main className="flex-1 max-w-3xl w-full mx-auto p-6 space-y-4">
        <div className="grid gap-4">
          {probes.map((probe) => (
            <div
              key={probe.label}
              className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 flex items-center justify-between gap-4"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-neutral-100">{probe.label}</p>
                <p className="text-xs text-neutral-500 font-mono">{probe.path}</p>
                {probe.detail && (
                  <p className="text-[11px] text-neutral-600 mt-1 font-mono truncate">
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
                      : "bg-neutral-800 text-neutral-400 border border-neutral-700"
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
