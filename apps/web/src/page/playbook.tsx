import WorkspaceHeader from "../component/WorkspaceHeader";
import PageIntro from "../component/PageIntro";
import { useEffect, useState } from "react";
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

// รายการประเภท clause ที่หน้า playbook ใช้เป็น filter และ dropdown
// ช่วยให้ admin เลือกดูตำแหน่งในแต่ละหมวดได้ง่ายขึ้น
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

// ระดับความเสี่ยงที่สามารถตั้งให้กับ playbook position ได้
const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "unknown"];

function clauseTypeLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, char => char.toUpperCase());
}

export default function PlaybookPage() {
  // รายการ playbook ที่ดึงมาจาก backend เพื่อแสดงบนตาราง
  const [positions, setPositions] = useState<PlaybookPosition[]>([]);
  const [error, setError] = useState<string | null>(null);

  // generation ใช้บอกว่า list ถูก refresh ไปแล้วกี่รอบ
  // มีไว้เพื่อให้ fetch หลัง create/update/delete ทำงานแบบ deterministic
  // โดยไม่ต้องเพิ่ม flag ซ้อนกันใน effect
  const [generation, setGeneration] = useState<number>(0);

  // loadedKey = key ของ request ล่าสุดที่โหลดเสร็จแล้ว
  // ถ้า loadedKey ไม่ตรงกับ requestedKey แปลว่ารอ fetch ใหม่หรือกำลังโหลด
  const [loadedKey, setLoadedKey] = useState<string | null>(null);

  // --- Filter / search state สำหรับกรองรายการในตาราง ---
  const [selectedType, setSelectedType] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // --- Modal state สำหรับหน้าต่าง create/edit position ---
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingPosition, setEditingPosition] = useState<PlaybookPosition | null>(null);

  // --- Form state สำหรับข้อมูลที่กรอกใน modal ---
  const [formId, setFormId] = useState<string>("");
  const [formClauseType, setFormClauseType] = useState<ClauseType>("confidentiality");
  const [formTitle, setFormTitle] = useState<string>("");
  const [formPreferred, setFormPreferred] = useState<string>("");
  const [formFallback, setFormFallback] = useState<string>("");
  const [formRisk, setFormRisk] = useState<RiskLevel>("medium");
  const [formTags, setFormTags] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  // --- Semantic search state: ค้นหาตามความหมายทั้ง playbook ออกจาก backend ---
  // ตรงนี้แยกจาก searchQuery เพราะ searchQuery เป็นการกรองเฉพาะข้อมูลที่โหลดมาแล้วบน client
  const [semanticQ, setSemanticQ] = useState<string>("");
  const [semanticResults, setSemanticResults] = useState<RetrievalHit[] | null>(null);
  const [semanticLoading, setSemanticLoading] = useState<boolean>(false);
  const [semanticError, setSemanticError] = useState<string | null>(null);

  // requestedKey = key ของรายการที่หน้าอยากให้แสดงตอนนี้
  // loading จะเท่ากับ true ในช่วงรอ fetch ใหม่ เพื่อให้ UI แสดงสถานะ loading
  // และหลีกเลี่ยงปัญหา old request land บน top of new request
  const requestedKey = `${generation}:${selectedType}`;
  const loading = loadedKey !== requestedKey;

  // --- ดึงรายการ playbook จาก backend ตาม filter ที่เลือก ---
  // effect นี้ทำงานทุกครั้งที่ generation หรือ selectedType เปลี่ยน
  // เพื่อให้ fetch ไม่สะท้อนผลลัพธ์เก่าบนคำขอใหม่
  useEffect(() => {
    let cancelled = false;

    fetchPlaybookPositions(selectedType || undefined).then(
      (data) => {
        if (cancelled) return;
        setPositions(data);
        setError(null);
        setLoadedKey(requestedKey);
      },
      (err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load playbook positions");
        // Marked loaded even on failure, or the effect would retry forever.
        setLoadedKey(requestedKey);
      }
    );

    return () => {
      cancelled = true;
    };
  }, [requestedKey, selectedType]);

  // หลังจาก create/update/delete ให้เรียก reload เพื่อ fetch list ใหม่
  const reload = () => setGeneration((n) => n + 1);

  const buildPayload = (): CreatePlaybookPayload => {
    const tagsList = formTags
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    return {
      id: formId.trim() || undefined,
      clause_type: formClauseType,
      title: formTitle,
      preferred_language: formPreferred,
      fallback_language: formFallback,
      risk_if_absent: formRisk,
      tags: tagsList,
    };
  };

  // --- Modal helpers สำหรับ create/edit position ---
  const openCreateModal = () => {
    setFormError(null);
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
    setFormError(null);
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
    if (submitting) return;
    if (!formTitle.trim() || !formPreferred.trim() || !formFallback.trim()) {
      setFormError("Please fill in Title, Preferred Language, and Fallback Language");
      return;
    }

    try {
      setSubmitting(true);
      setFormError(null);
      const payload = buildPayload();
      if (editingPosition) {
        await updatePlaybookPosition(editingPosition.id, payload);
      } else {
        await createPlaybookPosition(payload);
      }
      setIsModalOpen(false);
      reload();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to save position");
    } finally {
      setSubmitting(false);
    }
  };

  // --- ลบ playbook item หลังจากยืนยันแล้ว ---
  const handleDelete = async (id: string) => {
    if (!confirm(`Are you sure you want to delete position "${id}"?`)) return;
    try {
      await deletePlaybookPosition(id);
      reload();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Error deleting position");
    }
  };

  // --- Semantic search แบบค้นหาตามความหมายของ playbook ทั้งหมด ---
  // ไม่ใช่กรองบน client และใช้ endpoint GET /playbook/search
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

  // --- กรองรายการที่แสดงบนตารางตาม title/id/preferred text ---
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
    <div className="tool-page min-h-screen text-slate-100 flex flex-col">
      {/* --- Top bar: header ของหน้า + ปุ่มกลับสู่ app + ปุ่มเพิ่ม position --- */}
      <WorkspaceHeader actions={
        <button onClick={openCreateModal} className="primary-button">+ Add Position</button>
      } />

      {/* --- Main content container: toolbar + table/list + semantic search --- */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto px-8 py-10 space-y-6">
        <PageIntro eyebrow="KNOWLEDGE LIBRARY" title="Playbook" description="จัดการมาตรฐานข้อสัญญาและค้นหาแนวทางที่เหมาะกับการตรวจของคุณ" aside={<span className="count-chip">{loading ? "กำลังโหลด…" : `${positions.length} positions`}</span>} />
        {/* --- Toolbar สำหรับกำหนด category filter และ text search ของรายการที่แสดงอยู่ --- */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-4 flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <label className="text-xs uppercase tracking-wider text-navy-400 font-medium">
              Category:
            </label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400"
            >
              <option value="">All Categories ({positions.length})</option>
              {CLAUSE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {clauseTypeLabel(t)}
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
              className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-4 py-2 placeholder-navy-500 focus:outline-none focus:border-teal-400"
            />
          </div>
        </div>

        {/* --- Semantic search panel: ค้นหาตามความหมายเต็ม playbook ไม่ใช่แค่ filter local --- */}
        <form
          onSubmit={runSemanticSearch}
          className="bg-navy-900 border border-navy-800 rounded-xl p-4 flex flex-col sm:flex-row gap-3 items-stretch sm:items-center"
        >
          <label className="text-xs uppercase tracking-wider text-navy-400 font-medium sm:w-32">
            Semantic:
          </label>
          <input
            type="text"
            value={semanticQ}
            onChange={(e) => setSemanticQ(e.target.value)}
            placeholder="Search by meaning across all positions (e.g. 'who pays if data leaks')"
            className="flex-1 bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-4 py-2 placeholder-navy-500 focus:outline-none focus:border-teal-400"
          />
          <button
            type="submit"
            disabled={semanticLoading || !semanticQ.trim()}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-navy-800 text-navy-200 hover:bg-navy-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {semanticLoading ? "Searching…" : "Search"}
          </button>
          {semanticResults !== null && (
            <button
              type="button"
              onClick={clearSemanticSearch}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-navy-800 text-navy-400 hover:text-navy-200 transition"
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

        {/* --- เนื้อหาหลัก: แสดงผลลัพธ์ semantic search หรือตาราง playbook ปกติ --- */}
        {semanticResults !== null ? (
          semanticResults.length === 0 ? (
            <div className="bg-navy-900/60 border border-dashed border-navy-800 rounded-xl py-16 text-center text-navy-400">
              No matching positions.
            </div>
          ) : (
            <div className="space-y-3">
              {semanticResults.map((hit, i) => (
                <div
                  key={hit.position.id}
                  className="bg-navy-900 border border-navy-800 rounded-xl p-4"
                >
                  <div className="flex items-center justify-between mb-2 gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xs font-mono text-navy-400 flex-shrink-0">#{i + 1}</span>
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-teal-400/5 text-teal-200 border border-teal-400/15 flex-shrink-0">
                        {clauseTypeLabel(hit.position.clause_type)}
                      </span>
                      <h3 className="text-sm font-medium text-navy-100 truncate">
                        {hit.position.title}
                      </h3>
                    </div>
                    <div className="flex items-center gap-2 text-xs flex-shrink-0">
                      <span className="text-navy-400">score {hit.score.toFixed(3)}</span>
                      <span className="px-2 py-0.5 rounded bg-navy-800 text-navy-400 uppercase">
                        {hit.source}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-navy-400 line-clamp-2">
                    {hit.position.preferred_language}
                  </p>
                  <p className="text-[11px] text-navy-400 mt-1 font-mono">{hit.position.id}</p>
                </div>
              ))}
            </div>
          )
        ) : loading ? (
          <div className="text-center py-20 text-navy-400">Loading playbook positions...</div>
        ) : error ? (
          <div className="bg-red-950/40 border border-red-800/60 text-red-300 p-4 rounded-xl text-center">
            {error}
          </div>
        ) : filteredPositions.length === 0 ? (
          <div className="bg-navy-900/60 border border-dashed border-navy-800 rounded-xl py-16 text-center text-navy-400">
            No playbook positions found.
          </div>
        ) : (
          <div className="overflow-x-auto border border-navy-800 rounded-xl bg-navy-900">
            <table className="w-full text-left border-collapse text-sm text-navy-300">
              <thead>
                <tr className="border-b border-navy-800 bg-navy-950/50 text-xs uppercase tracking-wider text-navy-400">
                  <th className="py-3.5 px-4 font-semibold">ID</th>
                  <th className="py-3.5 px-4 font-semibold">Clause Type</th>
                  <th className="py-3.5 px-4 font-semibold">Title</th>
                  <th className="py-3.5 px-4 font-semibold">Risk If Absent</th>
                  <th className="py-3.5 px-4 font-semibold">Preferred Standard</th>
                  <th className="py-3.5 px-4 font-semibold">Fallback Language</th>
                  <th className="py-3.5 px-4 font-semibold">Tags</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800">
                {filteredPositions.map((pos) => (
                  <tr key={pos.id} className="hover:bg-navy-800/50 transition align-top">
                    <td className="py-3.5 px-4 font-mono text-xs text-navy-400">{pos.id}</td>
                    <td className="py-3.5 px-4">
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-teal-400/5 text-teal-200 border border-teal-400/15">
                        {clauseTypeLabel(pos.clause_type)}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-medium text-navy-100 max-w-[220px]">
                      {pos.title}
                    </td>
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
                    <td className="py-3.5 px-4 text-xs text-navy-400 max-w-[240px] align-top">
                      <div className="line-clamp-3">{pos.preferred_language}</div>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-navy-400 max-w-[240px] align-top">
                      <div className="line-clamp-3">{pos.fallback_language}</div>
                    </td>
                    <td className="py-3.5 px-4 align-top">
                      {pos.tags && pos.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5 max-w-[180px]">
                          {pos.tags.map((tag) => (
                            <span
                              key={`${pos.id}-${tag}`}
                              className="px-2 py-0.5 rounded-full text-[10px] bg-navy-800 text-navy-300 border border-navy-700"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[11px] text-navy-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-2 align-top">
                      <button
                        onClick={() => openEditModal(pos)}
                        className="px-3 py-1 text-xs font-medium bg-navy-800 text-navy-200 hover:bg-navy-700 rounded transition"
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

      {/* --- Modal สำหรับสร้าง/แก้ไข playbook position --- */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div role="dialog" aria-modal="true" aria-labelledby="playbook-dialog-title" className="bg-navy-900 border border-navy-700 rounded-2xl max-w-xl w-full max-h-[90vh] overflow-y-auto p-7 shadow-2xl space-y-4">
            <h2 id="playbook-dialog-title" className="text-xl font-semibold text-navy-100 border-b border-navy-800 pb-3">
              {editingPosition ? "Edit Playbook Position" : "Create Playbook Position"}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && <p role="alert" className="text-sm text-rose-400">{formError}</p>}
              {!editingPosition && (
                <div>
                  <label className="block text-xs font-medium text-navy-400 mb-1">
                    ID (Optional, auto-generated if empty)
                  </label>
                  <input
                    type="text"
                    value={formId}
                    onChange={(e) => setFormId(e.target.value)}
                    placeholder="e.g. pb_confidentiality_01"
                    className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400 font-mono"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-navy-400 mb-1">
                    Clause Category
                  </label>
                  <select
                    value={formClauseType}
                    onChange={(e) => setFormClauseType(e.target.value as ClauseType)}
                    className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400"
                  >
                    {CLAUSE_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {clauseTypeLabel(t)}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-navy-400 mb-1">
                    Risk If Absent
                  </label>
                  <select
                    value={formRisk}
                    onChange={(e) => setFormRisk(e.target.value as RiskLevel)}
                    className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400 uppercase"
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
                <label className="block text-xs font-medium text-navy-400 mb-1">Title</label>
                <input
                  type="text"
                  required
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="e.g. Standard Confidentiality Clause"
                  className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-navy-400 mb-1">
                  Preferred Standard Language
                </label>
                <textarea
                  required
                  rows={3}
                  value={formPreferred}
                  onChange={(e) => setFormPreferred(e.target.value)}
                  placeholder="Ideal clause text..."
                  className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-navy-400 mb-1">
                  Fallback Language
                </label>
                <textarea
                  required
                  rows={2}
                  value={formFallback}
                  onChange={(e) => setFormFallback(e.target.value)}
                  placeholder="Acceptable fallback text..."
                  className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-navy-400 mb-1">
                  Tags (Comma separated)
                </label>
                <input
                  type="text"
                  value={formTags}
                  onChange={(e) => setFormTags(e.target.value)}
                  placeholder="e.g. standard, strict, high-risk"
                  className="w-full bg-navy-800 border border-navy-700 text-navy-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-teal-400"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-navy-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm text-navy-400 hover:text-navy-200 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 text-sm font-medium bg-teal-300 text-navy-950 hover:bg-teal-200 font-semibold rounded-lg transition"
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
