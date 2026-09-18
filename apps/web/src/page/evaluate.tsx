import WorkspaceHeader from "../component/WorkspaceHeader";
import PageIntro from "../component/PageIntro";
import { useEffect, useState } from "react";
import { startEvaluation, getEvaluation, type EvalJob, type EvalMetrics } from "../lib/evaluate";
import { getToken } from "../lib/api";

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
  const [limit, setLimit] = useState<string>("1");
  const [order, setOrder] = useState<"file" | "shortest">("shortest");
  const [jobId, setJobId] = useState<string | null>(() => {
    const saved = localStorage.getItem("evaluation_job");
    if (!saved) return null;
    try {
      const value = JSON.parse(saved);
      return value.token === getToken() ? value.jobId : null;
    } catch { return null; }
  });
  const [progress, setProgress] = useState<EvalJob | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(jobId));
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<EvalMetrics | null>(null);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const job = await getEvaluation(jobId, controller.signal);
        if (controller.signal.aborted) return;
        setProgress(job);
        setError(null);
        if (job.status === "running") {
          timer = setTimeout(poll, 1500);
          return;
        }
        setMetrics(job.metrics);
        setError(job.error);
        setLoading(false);
        setJobId(null);
        localStorage.removeItem("evaluation_job");
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Cannot fetch evaluation progress");
        // A missing/expired job cannot resume. A temporary connection failure can.
        if (err && typeof err === "object" && "status" in err &&
            (err.status === 404 || err.status === 401)) {
          setLoading(false);
          setJobId(null);
          localStorage.removeItem("evaluation_job");
          return;
        }
        timer = setTimeout(poll, 5000);
      }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobId]);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);
      setMetrics(null);
      const parsedLimit = limit.trim() ? Number(limit) : undefined;
      setProgress(null);
      if (parsedLimit !== undefined && (!Number.isInteger(parsedLimit) || parsedLimit < 1)) {
        throw new Error("จำนวนสัญญาต้องเป็นจำนวนเต็มตั้งแต่ 1 ขึ้นไป");
      }
      const result = await startEvaluation({
        gold_set_path: goldSetPath.trim() || undefined,
        limit: parsedLimit,
        order,
      });
      localStorage.setItem("evaluation_job", JSON.stringify({ jobId: result.job_id, token: getToken() }));
      setProgress(result);
      setJobId(result.job_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Evaluation failed");
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
            1 รายการคือ 1 สัญญาทั้งฉบับ ซึ่งอาจมีหลายสิบข้อและใช้เวลาหลายนาที เลือกสัญญาสั้นก่อนเพื่อลองได้เร็วขึ้น
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
                จำนวนสัญญา (เว้นว่าง = ทั้งหมด)
              </label>
              <input
                type="number"
                min={1}
                step={1}
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="all"
                className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400"
              />
            </div>
          </div>
          <label className="block text-xs text-navy-400">
            ลำดับสัญญา
            <select value={order} disabled={loading}
              onChange={(e) => setOrder(e.target.value as "file" | "shortest")}
              className="ml-3 bg-navy-800 border border-navy-700 text-navy-200 rounded-lg px-3 py-2">
              <option value="shortest">สัญญาที่มีข้อน้อยที่สุดก่อน</option>
              <option value="file">ตามลำดับในชุดข้อมูล</option>
            </select>
          </label>
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
                กำลังตรวจสัญญา สามารถออกจากหน้านี้แล้วกลับมาดูความคืบหน้าได้
              </span>
            )}
          </div>
        </form>

        {progress && (
          <div role="status" aria-live="polite" className="bg-navy-900 border border-navy-800 rounded-xl p-4 space-y-2">
            <p className="text-sm text-navy-200">
              สัญญาที่เสร็จ {progress.completed_contracts}/{progress.total_contracts} ·
              ข้อที่ตรวจเสร็จ {progress.completed_clauses}/{progress.total_clauses} ·
              ใช้เวลา {Math.floor(progress.elapsed_seconds / 60)} นาที {Math.floor(progress.elapsed_seconds % 60)} วินาที
            </p>
            {progress.contract_id && <p className="text-xs text-navy-400 break-all">{progress.contract_id}</p>}
            <progress className="w-full accent-teal-300" value={progress.completed_clauses} max={Math.max(1, progress.total_clauses)} />
            {progress.status === "running" && progress.total_clauses === 0 && <p className="text-xs text-navy-400">กำลังเตรียมข้อมูลสัญญา…</p>}
            {progress.status === "completed" && <p className="text-xs text-teal-300">ประเมินเสร็จแล้ว</p>}
          </div>
        )}

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
