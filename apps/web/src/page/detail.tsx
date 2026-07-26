import { useState } from 'react';
import type { Infro } from '../component/sidebar/sidebar';
import SideDetail from '../component/sidebar/SideDetail';

interface DetailProps {
  infro: Infro;
  onBack?: () => void;
  onAsk?: (question: string) => void;
}

type BottomMode = 'idle' | 'ask' | 'overall';

const statusLabel: Record<string, string> = {
  resolved: 'ดำเนินการเสร็จสิ้น',
  pending: 'รอดำเนินการ',
  open: 'เปิดเรื่อง',
  closed: 'ปิดเรื่อง',
};

const statusColor: Record<string, string> = {
  resolved: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30',
  pending: 'bg-amber-500/10 text-amber-300 ring-amber-500/30',
  open: 'bg-sky-500/10 text-sky-300 ring-sky-500/30',
  closed: 'bg-neutral-500/10 text-neutral-300 ring-neutral-500/30',
};

const categoryLabel: Record<string, string> = {
  lease: 'สัญญาเช่า',
  sale: 'สัญญาซื้อขาย',
  service: 'สัญญาบริการ',
  employment: 'สัญญาจ้างงาน',
  dispute: 'ข้อพิพาท',
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('th-TH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

// Detail.tsx เป็น component แบบ standalone — สามารถนำไปวางในหน้าอื่นได้เลย
// เพียงส่ง prop `infro` (ข้อมูลเรื่องที่ต้องการแสดง) เข้ามา
// ส่วน `onBack` เป็น optional เผื่อหน้านั้นต้องการปุ่มย้อนกลับ
// ด้านล่างมีปุ่ม "ถาม" (ask) ทางซ้าย และ "ภาพรวม" (overall) ทางขวา:
//   - กด "ถาม" -> ปุ่ม "ภาพรวม" จะหายไป และปุ่ม "ถาม" จะขยายมาอยู่กึ่งกลางล่างจอ กลายเป็นช่องพิมพ์แชท
//   - กด "ภาพรวม" -> เปิดแผง SideDetail ทางขวาแสดงข้อมูลทั้งหมดของเรื่อง
function Detail({ infro, onBack, onAsk }: DetailProps) {
  const [mode, setMode] = useState<BottomMode>('idle');
  const [question, setQuestion] = useState('');

  function handleAskSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;
    onAsk?.(trimmed);
    setQuestion('');
  }

  return (
    <div className="relative h-full bg-neutral-950 overflow-hidden">
      {/* ส่วนเนื้อหา — scroll ได้อิสระ ไม่กระทบตำแหน่งปุ่มด้านล่าง */}
      <div className="h-full overflow-y-auto flex justify-center py-10 px-4">
      <div className="w-full max-w-2xl pb-28">
        {/* หัวข้อ + ปุ่มย้อนกลับ */}
        <div className="mb-8 border-b border-neutral-800 pb-5">
          {onBack && (
            <button
              onClick={onBack}
              className="mb-4 text-xs text-neutral-500 hover:text-amber-400 transition-colors flex items-center gap-1"
            >
              ← กลับไปหน้ารายการ
            </button>
          )}
          <p className="text-xs uppercase tracking-[0.2em] text-amber-500/70 mb-1">
            {infro.contractId}
          </p>
          <h1
            className="text-2xl font-semibold text-neutral-100 leading-snug"
            style={{ fontFamily: 'Georgia, "Noto Serif Thai", serif' }}
          >
            {infro.title}
          </h1>
        </div>

        {/* สถานะ + หมวดหมู่ */}
        <div className="flex flex-wrap gap-2 mb-6">
          <span
            className={`px-3 py-1 rounded-full text-[11px] font-medium ring-1 ${
              statusColor[infro.status] ?? statusColor.open
            }`}
          >
            {statusLabel[infro.status] ?? infro.status}
          </span>
          <span className="px-3 py-1 rounded-full text-[11px] font-medium bg-neutral-800 text-neutral-300 ring-1 ring-neutral-700">
            {categoryLabel[infro.category] ?? infro.category}
          </span>
        </div>

        {/* รายละเอียด */}
        <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-5 py-4 mb-4">
          <p className="text-xs uppercase tracking-wide text-neutral-500 mb-2">รายละเอียด</p>
          <p className="text-[15px] text-neutral-200 leading-relaxed">{infro.detail}</p>
        </div>

        {/* ข้อมูลเพิ่มเติม */}
        <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-5 py-4 mb-4 grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">สร้างเมื่อ</p>
            <p className="text-sm text-neutral-200">{formatDate(infro.createdAt)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">อัปเดตล่าสุด</p>
            <p className="text-sm text-neutral-200">{formatDate(infro.updatedAt)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">ผู้ร่วมสนทนา</p>
            <p className="text-sm text-neutral-200">{infro.participants.join(', ')}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">จำนวนข้อความ</p>
            <p className="text-sm text-neutral-200">{infro.messageCount} ข้อความ</p>
          </div>
        </div>

        {/* แท็ก */}
        <div className="flex flex-wrap gap-2">
          {infro.tags.map((tag, i) => (
            <span
              key={i}
              className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/30"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
      </div>

      {/* แถบปุ่มด้านล่าง: ถาม (ซ้าย) / ภาพรวม (ขวา) */}
      <div className="absolute inset-x-0 bottom-0 z-40 pointer-events-none">
        <div className="px-4 sm:px-6 pb-6">
          <div className="relative h-14">
            {/* ปุ่มภาพรวม — อยู่ขวา ซ่อนเมื่ออยู่โหมดถาม */}
            <button
              onClick={() => setMode('overall')}
              disabled={mode === 'ask'}
              className={`pointer-events-auto absolute right-0 bottom-0 w-28 rounded-full bg-neutral-900 border border-neutral-800 px-5 py-3 text-xs font-medium text-neutral-300 ring-1 ring-neutral-700 whitespace-nowrap text-center hover:text-amber-300 hover:ring-amber-500/30 transition-all duration-300 ${
                mode === 'ask'
                  ? 'opacity-0 translate-y-3 pointer-events-none'
                  : 'opacity-100 translate-y-0'
              }`}
            >
              ภาพรวม
            </button>

            {/* ปุ่มถาม — ตอนปกติมีขนาดเท่ากับปุ่มภาพรวม อยู่มุมซ้าย, ขยายเต็มความกว้างและกลายเป็นช่องพิมพ์เมื่อกด */}
            <div
              className={`pointer-events-auto absolute bottom-0 left-0 transition-all duration-300 ease-out ${
                mode === 'ask' ? 'right-0' : 'w-28'
              }`}
            >
              {mode === 'ask' ? (
                <form
                  onSubmit={handleAskSubmit}
                  className="flex items-center gap-2 rounded-full bg-neutral-900 border border-amber-500/30 ring-1 ring-amber-500/20 px-4 py-2.5 shadow-2xl shadow-black/50"
                >
                  <button
                    type="button"
                    onClick={() => setMode('idle')}
                    className="shrink-0 text-neutral-500 hover:text-neutral-300 transition-colors"
                    aria-label="ปิดช่องถาม"
                  >
                    ←
                  </button>
                  <input
                    autoFocus
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="พิมพ์คำถามเกี่ยวกับเรื่องนี้..."
                    className="flex-1 bg-transparent text-sm text-neutral-100 placeholder:text-neutral-600 outline-none"
                  />
                  <button
                    type="submit"
                    disabled={!question.trim()}
                    className="shrink-0 rounded-full bg-amber-500 px-4 py-1.5 text-xs font-semibold text-neutral-950 hover:bg-amber-400 transition-colors disabled:opacity-40 disabled:hover:bg-amber-500"
                  >
                    ส่ง
                  </button>
                </form>
              ) : (
                <button
                  onClick={() => setMode('ask')}
                  className="w-full rounded-full bg-amber-500 px-5 py-3 text-xs font-semibold text-neutral-950 whitespace-nowrap text-center hover:bg-amber-400 transition-colors"
                >
                  ถาม
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* แผงภาพรวมทางขวา */}
      {mode === 'overall' && (
        <SideDetail infro={infro} onClose={() => setMode('idle')} />
      )}
    </div>
  );
}

export default Detail;