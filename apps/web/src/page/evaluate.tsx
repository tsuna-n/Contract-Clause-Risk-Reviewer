import WorkspaceHeader from "../component/WorkspaceHeader";
import PageIntro from "../component/PageIntro";
import { useState } from "react";
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
    <div className="tool-page min-h-screen text-slate-100 flex flex-col">
      <WorkspaceHeader />

      <main className="flex-1 max-w-6xl w-full mx-auto px-8 py-10 space-y-6">
        <PageIntro eyebrow="QUALITY & ACCURACY" title="Evaluation" description="วัดความแม่นยำของการตรวจสัญญาเทียบกับชุดข้อมูลมาตรฐาน" />
        <form
          onSubmit={run}
          className="bg-navy-900 border border-navy-800 rounded-xl p-5 space-y-4"
        >
          <h2 className="panel-title">Configure evaluation</h2>
          <p className="text-sm text-navy-300 leading-relaxed">
            Run the review pipeline against a gold-set annotation file and report accuracy metrics.
            Each evaluation may take several minutes.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_180px] gap-4">
            <div>
              <label className="block text-xs font-medium text-navy-400 mb-1">
                Gold set path (on the backend)
              </label>
              <input
                type="text"
                value={goldSetPath}
                onChange={(e) => setGoldSetPath(e.target.value)}
                placeholder="data/gold/annotations.jsonl"
                className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400 font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-navy-400 mb-1">
                Limit (optional)
              </label>
              <input
                type="number"
                min={1}
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="all"
                className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 text-sm font-semibold rounded-lg bg-teal-300 text-navy-950 hover:bg-teal-200 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "Running…" : "Run Evaluation"}
            </button>
            {loading && (
              <span className="text-xs text-navy-400">
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
                  className="bg-navy-900 border border-navy-800 rounded-xl p-4"
                >
                  <p className="text-xs uppercase tracking-wider text-navy-400 mb-1">
                    {card.label}
                  </p>
                  <p className="text-3xl font-semibold text-teal-300">{pct(card.value)}</p>
                  <p className="text-[11px] text-navy-400 mt-1">{card.hint}</p>
                </div>
              ))}
            </div>

            {metrics.per_type.length > 0 && (
              <div className="overflow-x-auto border border-navy-800 rounded-xl bg-navy-900">
                <table className="w-full text-left border-collapse text-sm text-navy-300">
                  <thead>
                    <tr className="border-b border-navy-800 bg-navy-950/50 text-xs uppercase tracking-wider text-navy-400">
                      <th className="py-3 px-4 font-semibold">Clause Type</th>
                      <th className="py-3 px-4 font-semibold text-right">Support</th>
                      <th className="py-3 px-4 font-semibold text-right">Accuracy</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-navy-800">
                    {metrics.per_type.map((row) => (
                      <tr key={row.clause_type} className="hover:bg-navy-800/50 transition">
                        <td className="py-3 px-4 font-medium text-navy-100">{row.clause_type}</td>
                        <td className="py-3 px-4 text-right text-navy-400">{row.support}</td>
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
