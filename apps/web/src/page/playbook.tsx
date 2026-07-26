import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchPlaybookPositions,
  createPlaybookPosition,
  updatePlaybookPosition,
  deletePlaybookPosition,
  searchPlaybook,
  type PlaybookPosition,
  type RetrievalHit,
  type ClauseType,
  type RiskLevel,
  type CreatePlaybookPayload,
} from "../lib/playbook";

const CLAUSE_TYPES: ClauseType[] = [
  "confidentiality",
  "indemnification",
  "limitation_of_liability",
  "termination",
  "governing_law",
  "intellectual_property",
  "payment_terms",
  "warranty",
  "non_compete",
  "data_protection",
  "force_majeure",
  "other",
];

const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "unknown"];

export default function PlaybookPage() {
  const [positions, setPositions] = useState<PlaybookPosition[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedType, setSelectedType] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingPosition, setEditingPosition] = useState<PlaybookPosition | null>(null);

  // Form State
  const [formId, setFormId] = useState<string>("");
  const [formClauseType, setFormClauseType] = useState<ClauseType>("confidentiality");
  const [formTitle, setFormTitle] = useState<string>("");
  const [formPreferred, setFormPreferred] = useState<string>("");
  const [formFallback, setFormFallback] = useState<string>("");
  const [formRisk, setFormRisk] = useState<RiskLevel>("medium");
  const [formTags, setFormTags] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Semantic search (GET /playbook/search) — ค้นตามความหมายทั้ง playbook
  // แยกจาก searchQuery ซึ่งกรอง client-side แค่ในรายการที่โหลดมาแล้ว
  const [semanticQ, setSemanticQ] = useState<string>("");
  const [semanticResults, setSemanticResults] = useState<RetrievalHit[] | null>(null);
  const [semanticLoading, setSemanticLoading] = useState<boolean>(false);
  const [semanticError, setSemanticError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPlaybookPositions(selectedType || undefined);
      setPositions(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load playbook positions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedType]);

  const openCreateModal = () => {
    setEditingPosition(null);
    setFormId("");
    setFormClauseType("confidentiality");
    setFormTitle("");
    setFormPreferred("");
    setFormFallback("");
    setFormRisk("medium");
    setFormTags("");
    setIsModalOpen(true);
  };

  const openEditModal = (pos: PlaybookPosition) => {
    setEditingPosition(pos);
    setFormId(pos.id);
    setFormClauseType(pos.clause_type);
    setFormTitle(pos.title);
    setFormPreferred(pos.preferred_language);
    setFormFallback(pos.fallback_language);
    setFormRisk(pos.risk_if_absent);
    setFormTags(pos.tags ? pos.tags.join(", ") : "");
    setIsModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle.trim() || !formPreferred.trim() || !formFallback.trim()) {
      alert("Please fill in Title, Preferred Language, and Fallback Language");
      return;
    }

    const tagsList = formTags
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    try {
      setSubmitting(true);
      if (editingPosition) {
        // Update
        await updatePlaybookPosition(editingPosition.id, {
          clause_type: formClauseType,
          title: formTitle,
          preferred_language: formPreferred,
          fallback_language: formFallback,
          risk_if_absent: formRisk,
          tags: tagsList,
        });
      } else {
        // Create
        const payload: CreatePlaybookPayload = {
          id: formId.trim() || undefined,
          clause_type: formClauseType,
          title: formTitle,
          preferred_language: formPreferred,
          fallback_language: formFallback,
          risk_if_absent: formRisk,
          tags: tagsList,
        };
        await createPlaybookPosition(payload);
      }
      setIsModalOpen(false);
      await loadData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Error saving position");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(`Are you sure you want to delete position "${id}"?`)) return;
    try {
      await deletePlaybookPosition(id);
      await loadData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Error deleting position");
    }
  };

  const runSemanticSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!semanticQ.trim()) return;
    try {
      setSemanticLoading(true);
      setSemanticError(null);
      const hits = await searchPlaybook(semanticQ.trim());
      setSemanticResults(hits);
    } catch (err: unknown) {
      setSemanticError(err instanceof Error ? err.message : "Semantic search failed");
      setSemanticResults(null);
    } finally {
      setSemanticLoading(false);
    }
  };

  const clearSemanticSearch = () => {
    setSemanticResults(null);
    setSemanticError(null);
    setSemanticQ("");
  };

  const filteredPositions = positions.filter((p) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      p.title.toLowerCase().includes(q) ||
      p.id.toLowerCase().includes(q) ||
      p.preferred_language.toLowerCase().includes(q)
    );
  });

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-neutral-800 bg-neutral-900/80 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to="/manual" className="text-amber-500 font-serif text-xl font-bold tracking-wide">
            Contract Risk Reviewer
          </Link>
          <span className="text-neutral-600">/</span>
          <h1 className="text-neutral-200 text-lg font-medium">Playbook Management (CRUD)</h1>
        </div>
        <div className="flex items-center space-x-3">
          <Link
            to="/manual"
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-neutral-800 text-neutral-300 hover:bg-neutral-700 transition"
          >
            ← Back to App
          </Link>
          <button
            onClick={openCreateModal}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-amber-500 text-neutral-950 hover:bg-amber-400 font-semibold transition"
          >
            + Add Position
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Filter & Search Toolbar */}
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <label className="text-xs uppercase tracking-wider text-neutral-400 font-medium">
              Category:
            </label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500"
            >
              <option value="">All Categories ({positions.length})</option>
              {CLAUSE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="w-full sm:w-80">
            <input
              type="text"
              placeholder="Search title, ID, text..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-4 py-2 placeholder-neutral-500 focus:outline-none focus:border-amber-500"
            />
          </div>
        </div>

        {/* Semantic search (GET /playbook/search) — ค้นตามความหมาย
            แยกจากช่องกรองด้านบน ซึ่งกรองแค่ในรายการที่โหลดมาแล้ว */}
        <form
          onSubmit={runSemanticSearch}
          className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 flex flex-col sm:flex-row gap-3 items-stretch sm:items-center"
        >
          <label className="text-xs uppercase tracking-wider text-neutral-400 font-medium sm:w-32">
            Semantic:
          </label>
          <input
            type="text"
            value={semanticQ}
            onChange={(e) => setSemanticQ(e.target.value)}
            placeholder="Search by meaning across all positions (e.g. 'who pays if data leaks')"
            className="flex-1 bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-4 py-2 placeholder-neutral-500 focus:outline-none focus:border-amber-500"
          />
          <button
            type="submit"
            disabled={semanticLoading || !semanticQ.trim()}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-neutral-800 text-neutral-200 hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {semanticLoading ? "Searching…" : "Search"}
          </button>
          {semanticResults !== null && (
            <button
              type="button"
              onClick={clearSemanticSearch}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-neutral-800 text-neutral-400 hover:text-neutral-200 transition"
            >
              ← Back to list
            </button>
          )}
        </form>
        {semanticError && (
          <div className="bg-red-950/40 border border-red-800/60 text-red-300 p-3 rounded-xl text-sm">
            {semanticError}
          </div>
        )}

        {/* Content Table / Cards */}
        {semanticResults !== null ? (
          semanticResults.length === 0 ? (
            <div className="bg-neutral-900/60 border border-dashed border-neutral-800 rounded-xl py-16 text-center text-neutral-500">
              No matching positions.
            </div>
          ) : (
            <div className="space-y-3">
              {semanticResults.map((hit, i) => (
                <div
                  key={hit.position.id}
                  className="bg-neutral-900 border border-neutral-800 rounded-xl p-4"
                >
                  <div className="flex items-center justify-between mb-2 gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xs font-mono text-neutral-500 flex-shrink-0">#{i + 1}</span>
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20 flex-shrink-0">
                        {hit.position.clause_type}
                      </span>
                      <h3 className="text-sm font-medium text-neutral-100 truncate">
                        {hit.position.title}
                      </h3>
                    </div>
                    <div className="flex items-center gap-2 text-xs flex-shrink-0">
                      <span className="text-neutral-400">score {hit.score.toFixed(3)}</span>
                      <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-400 uppercase">
                        {hit.source}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-neutral-400 line-clamp-2">
                    {hit.position.preferred_language}
                  </p>
                  <p className="text-[11px] text-neutral-600 mt-1 font-mono">{hit.position.id}</p>
                </div>
              ))}
            </div>
          )
        ) : loading ? (
          <div className="text-center py-20 text-neutral-500">Loading playbook positions...</div>
        ) : error ? (
          <div className="bg-red-950/40 border border-red-800/60 text-red-300 p-4 rounded-xl text-center">
            {error}
          </div>
        ) : filteredPositions.length === 0 ? (
          <div className="bg-neutral-900/60 border border-dashed border-neutral-800 rounded-xl py-16 text-center text-neutral-500">
            No playbook positions found.
          </div>
        ) : (
          <div className="overflow-x-auto border border-neutral-800 rounded-xl bg-neutral-900">
            <table className="w-full text-left border-collapse text-sm text-neutral-300">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-950/50 text-xs uppercase tracking-wider text-neutral-400">
                  <th className="py-3.5 px-4 font-semibold">ID</th>
                  <th className="py-3.5 px-4 font-semibold">Clause Type</th>
                  <th className="py-3.5 px-4 font-semibold">Title</th>
                  <th className="py-3.5 px-4 font-semibold">Risk If Absent</th>
                  <th className="py-3.5 px-4 font-semibold">Preferred Standard</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800">
                {filteredPositions.map((pos) => (
                  <tr key={pos.id} className="hover:bg-neutral-850 transition">
                    <td className="py-3.5 px-4 font-mono text-xs text-neutral-400">{pos.id}</td>
                    <td className="py-3.5 px-4">
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20">
                        {pos.clause_type}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-medium text-neutral-100">{pos.title}</td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                          pos.risk_if_absent === "high"
                            ? "bg-red-500/20 text-red-400 border border-red-500/30"
                            : pos.risk_if_absent === "medium"
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        }`}
                      >
                        {pos.risk_if_absent}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-neutral-400 max-w-xs truncate">
                      {pos.preferred_language}
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-2">
                      <button
                        onClick={() => openEditModal(pos)}
                        className="px-3 py-1 text-xs font-medium bg-neutral-800 text-neutral-200 hover:bg-neutral-700 rounded transition"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(pos.id)}
                        className="px-3 py-1 text-xs font-medium bg-red-950/60 text-red-400 border border-red-900/60 hover:bg-red-900/80 rounded transition"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {/* Create / Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <h2 className="text-xl font-semibold text-neutral-100 border-b border-neutral-800 pb-3">
              {editingPosition ? "Edit Playbook Position" : "Create Playbook Position"}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {!editingPosition && (
                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">
                    ID (Optional, auto-generated if empty)
                  </label>
                  <input
                    type="text"
                    value={formId}
                    onChange={(e) => setFormId(e.target.value)}
                    placeholder="e.g. pb_confidentiality_01"
                    className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500 font-mono"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">
                    Clause Category
                  </label>
                  <select
                    value={formClauseType}
                    onChange={(e) => setFormClauseType(e.target.value as ClauseType)}
                    className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500"
                  >
                    {CLAUSE_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">
                    Risk If Absent
                  </label>
                  <select
                    value={formRisk}
                    onChange={(e) => setFormRisk(e.target.value as RiskLevel)}
                    className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500 uppercase"
                  >
                    {RISK_LEVELS.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">Title</label>
                <input
                  type="text"
                  required
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="e.g. Standard Confidentiality Clause"
                  className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  Preferred Standard Language
                </label>
                <textarea
                  required
                  rows={3}
                  value={formPreferred}
                  onChange={(e) => setFormPreferred(e.target.value)}
                  placeholder="Ideal clause text..."
                  className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  Fallback Language
                </label>
                <textarea
                  required
                  rows={2}
                  value={formFallback}
                  onChange={(e) => setFormFallback(e.target.value)}
                  placeholder="Acceptable fallback text..."
                  className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  Tags (Comma separated)
                </label>
                <input
                  type="text"
                  value={formTags}
                  onChange={(e) => setFormTags(e.target.value)}
                  placeholder="e.g. standard, strict, high-risk"
                  className="w-full bg-neutral-800 border border-neutral-700 text-neutral-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm text-neutral-400 hover:text-neutral-200 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 text-sm font-medium bg-amber-500 text-neutral-950 hover:bg-amber-400 font-semibold rounded-lg transition"
                >
                  {submitting ? "Saving..." : editingPosition ? "Update Position" : "Create Position"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
