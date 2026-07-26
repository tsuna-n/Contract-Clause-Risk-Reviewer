import { useState } from "react";
import { Link } from "react-router-dom";
import { runEvaluation, type EvalMetrics } from "../lib/evaluate";

/** 0.0–1.0 → "83%", kept readable for a perfect 1.0 ("100%" not "100.0%"). */
function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

interface MetricCard {
  label: string;
  value: number;
  hint: string;
}

export default function EvaluatePage() {
  const [goldSetPath, setGoldSetPath] = useState<string>("data/gold/annotations.jsonl");
  const [limit, setLimit] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<EvalMetrics | null>(null);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);
      setMetrics(null);
      const parsedLimit = limit.trim() ? Number(limit) : undefined;
      const result = await runEvaluation({
        gold_set_path: goldSetPath.trim() || undefined,
        limit: parsedLimit !== undefined && Number.isFinite(parsedLimit) ? parsedLimit : undefined,
      });
      setMetrics(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Evaluation failed");
    } finally {
      setLoading(false);
    }
  };

  const cards: MetricCard[] = metrics
    ? [
        { label: "Segmentation F1", value: metrics.segmentation_f1, hint: "Clause boundary detection" },
        { label: "Classification Acc.", value: metrics.classification_accuracy, hint: "Clause type prediction" },
        { label: "Risk Acc.", value: metrics.risk_accuracy, hint: "Risk level prediction" },
        { label: "Citation Validity", value: metrics.citation_validity, hint: "Grounding to playbook" },
      ]
    : [];

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans">
      <header className="border-b border-neutral-800 bg-neutral-900/80 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to="/manual" className="text-amber-500 font-serif text-xl font-bold tracking-wide">
            Contract Risk Reviewer
          </Link>
          <span className="text-neutral-600">/</span>
          <h1 className="text-neutral-200 text-lg font-medium">Evaluation Harness</h1>
        </div>
        <Link
          to="/manual"
          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-neutral-800 text-neutral-300 hover:bg-neutral-700 transition"
        >
          ← Back to App
        </Link>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto p-6 space-y-6">
        <form
          onSubmit={run}
          className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-4"
        >
          <p className="text-sm text-neutral-400">
            Run the review pipeline against a gold-set annotation file and report accuracy metrics.
            This calls <code className="text-amber-300">POST /evaluate</code> and may take several minutes.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_180px] gap-4">
            <div>
              <label className="block text-xs font-medium text-neutral-400 mb-1">
                Gold set path (on the backend)
              </label>
              <input
                type="text"
                value={goldSetPath}
                onChange={(e) => setGoldSetPath(e.target.value)}
                placeholder="data/gold/annotations.jsonl"
                className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500 font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-400 mb-1">
                Limit (optional)
              </label>
              <input
                type="number"
                min={1}
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="all"
                className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 text-sm font-semibold rounded-lg bg-amber-500 text-neutral-950 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "Running…" : "Run Evaluation"}
            </button>
            {loading && (
              <span className="text-xs text-neutral-500">
                The pipeline runs serially per item — please keep this tab open.
              </span>
            )}
          </div>
        </form>

        {error && (
          <div className="bg-red-950/40 border border-red-800/60 text-red-300 p-4 rounded-xl text-sm">
            {error}
          </div>
        )}

        {metrics && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {cards.map((card) => (
                <div
                  key={card.label}
                  className="bg-neutral-900 border border-neutral-800 rounded-xl p-4"
                >
                  <p className="text-xs uppercase tracking-wider text-neutral-500 mb-1">
                    {card.label}
                  </p>
                  <p className="text-3xl font-semibold text-amber-400">{pct(card.value)}</p>
                  <p className="text-[11px] text-neutral-600 mt-1">{card.hint}</p>
                </div>
              ))}
            </div>

            {metrics.per_type.length > 0 && (
              <div className="overflow-x-auto border border-neutral-800 rounded-xl bg-neutral-900">
                <table className="w-full text-left border-collapse text-sm text-neutral-300">
                  <thead>
                    <tr className="border-b border-neutral-800 bg-neutral-950/50 text-xs uppercase tracking-wider text-neutral-400">
                      <th className="py-3 px-4 font-semibold">Clause Type</th>
                      <th className="py-3 px-4 font-semibold text-right">Support</th>
                      <th className="py-3 px-4 font-semibold text-right">Accuracy</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-800">
                    {metrics.per_type.map((row) => (
                      <tr key={row.clause_type} className="hover:bg-neutral-850 transition">
                        <td className="py-3 px-4 font-medium text-neutral-100">{row.clause_type}</td>
                        <td className="py-3 px-4 text-right text-neutral-400">{row.support}</td>
                        <td className="py-3 px-4 text-right">
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20">
                            {pct(row.accuracy)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
