import type { Infro } from './sidebar';

interface SideDetailProps {
  infro: Infro;
  onClose: () => void;
}

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

// SideDetail.tsx — แผงสรุปข้อมูลทั้งหมดของเรื่อง แสดงเป็น sidebar ทางขวา
// ใช้คู่กับปุ่ม "ภาพรวม" ใน Detail.tsx โดยส่ง prop `infro` เข้ามา
// และ `onClose` สำหรับปิดแผงกลับไปสถานะปกติ
// component นี้เป็น standalone แยกออกมา นำไปวางต่อกับหน้าไหนก็ได้ที่มี infro
function SideDetail({ infro, onClose }: SideDetailProps) {
  return (
    <>
      {/* ฉากหลังจาง ๆ คลิกเพื่อปิด */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-neutral-950/60 backdrop-blur-sm transition-opacity duration-200"
        aria-hidden="true"
      />

      {/* แผง sidebar ทางขวา */}
      <aside
        className="fixed inset-y-0 right-0 z-50 w-full max-w-sm border-l border-neutral-800 bg-neutral-950 shadow-2xl shadow-black/50 overflow-y-auto transition-transform duration-300 ease-out"
        role="dialog"
        aria-label="ภาพรวมข้อมูลเรื่อง"
      >
        <div className="px-6 py-6">
          {/* หัวแผง */}
          <div className="mb-6 flex items-start justify-between gap-3 border-b border-neutral-800 pb-5">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-amber-500/70 mb-1">
                ภาพรวม · {infro.contractId}
              </p>
              <h2
                className="text-lg font-semibold text-neutral-100 leading-snug"
                style={{ fontFamily: 'Georgia, "Noto Serif Thai", serif' }}
              >
                {infro.title}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="shrink-0 rounded-full p-1.5 text-neutral-500 hover:text-amber-400 hover:bg-neutral-900 transition-colors"
              aria-label="ปิดแผงภาพรวม"
            >
              ✕
            </button>
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
          <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-4 py-4 mb-4">
            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-2">รายละเอียด</p>
            <p className="text-sm text-neutral-200 leading-relaxed">{infro.detail}</p>
          </div>

          {/* ข้อมูลเพิ่มเติม */}
          <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-4 py-4 mb-4 grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">สร้างเมื่อ</p>
              <p className="text-sm text-neutral-200">{formatDate(infro.createdAt)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">อัปเดตล่าสุด</p>
              <p className="text-sm text-neutral-200">{formatDate(infro.updatedAt)}</p>
            </div>
            <div className="col-span-2">
              <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">ผู้ร่วมสนทนา</p>
              <p className="text-sm text-neutral-200">{infro.participants.join(', ')}</p>
            </div>
            <div className="col-span-2">
              <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">จำนวนข้อความ</p>
              <p className="text-sm text-neutral-200">{infro.messageCount} ข้อความ</p>
            </div>
          </div>

          {/* แท็ก */}
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-2">แท็ก</p>
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
      </aside>
    </>
  );
}

export default SideDetail;