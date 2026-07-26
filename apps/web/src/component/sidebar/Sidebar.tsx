import { useState, useEffect } from 'react';

export interface Infro {
  id: string;
  title: string;
  detail: string;
  createdAt: string;
  updatedAt: string;
  status: string;
  contractId: string;
  category: string;
  participants: string[];
  messageCount: number;
  tags: string[];
}

export interface SidebarUser {
  isLoggedIn: boolean;
  name?: string;
  email?: string;
}

interface SidebarProps {
  onNewChat?: () => void;
  onSelectChat?: (infro: Infro) => void;
  user?: SidebarUser;
  onLogout?: () => void;
}

// ปกปิดอีเมลให้เหลือแค่ ***@gmail.com
function maskEmail(email?: string) {
  if (!email) return '***@gmail.com';
  const domain = email.includes('@') ? email.split('@')[1] : 'gmail.com';
  return `***@${domain}`;
}

function Sidebar({ onNewChat, onSelectChat, user, onLogout }: SidebarProps = {}) {
  const [infros, setInfros] = useState<Infro[]>([]);

  const infroData: Infro[] = [{
    "id": "chat_001",
    "title": "สอบถามเงื่อนไขสัญญาเช่าอาคารสำนักงาน",
    "detail": "ลูกค้าต้องการทราบเงื่อนไขการต่อสัญญาเช่าและอัตราค่าเช่าที่ปรับเพิ่มขึ้นในปีที่ 3",
    "createdAt": "2026-07-20T09:15:00+07:00",
    "updatedAt": "2026-07-20T09:40:00+07:00",
    "status": "resolved",
    "contractId": "CT-2026-0087",
    "category": "lease",
    "participants": ["user_123", "agent_45"],
    "messageCount": 12,
    "tags": ["ต่อสัญญา", "อัตราค่าเช่า"]
  },
  {
    "id": "chat_002",
    "title": "แก้ไขข้อสัญญาซื้อขายสินค้า",
    "detail": "ขอเปลี่ยนแปลงเงื่อนไขการชำระเงินจากเงินสดเป็นเครดิต 30 วัน",
    "createdAt": "2026-07-21T13:42:00+07:00",
    "updatedAt": "2026-07-21T14:10:00+07:00",
    "status": "pending",
    "contractId": "CT-2026-0091",
    "category": "sale",
    "participants": ["user_456", "agent_12"],
    "messageCount": 8,
    "tags": ["เงื่อนไขชำระเงิน", "เครดิต"]
  },
  {
    "id": "chat_003",
    "title": "ยกเลิกสัญญาบริการรายเดือน",
    "detail": "ลูกค้าแจ้งยกเลิกสัญญาบริการก่อนกำหนด ต้องตรวจสอบค่าปรับตามข้อตกลง",
    "createdAt": "2026-07-22T10:05:00+07:00",
    "updatedAt": "2026-07-22T10:50:00+07:00",
    "status": "open",
    "contractId": "CT-2026-0102",
    "category": "service",
    "participants": ["user_789", "agent_45"],
    "messageCount": 15,
    "tags": ["ยกเลิกสัญญา", "ค่าปรับ"]
  },
  {
    "id": "chat_004",
    "title": "ต่ออายุสัญญาจ้างพนักงาน",
    "detail": "ฝ่าย HR สอบถามขั้นตอนการต่อสัญญาจ้างพนักงานที่จะหมดอายุสิ้นเดือนนี้",
    "createdAt": "2026-07-23T15:30:00+07:00",
    "updatedAt": "2026-07-23T16:00:00+07:00",
    "status": "closed",
    "contractId": "CT-2026-0115",
    "category": "employment",
    "participants": ["user_321", "agent_09"],
    "messageCount": 6,
    "tags": ["ต่อสัญญาจ้าง", "HR"]
  },
  {
    "id": "chat_005",
    "title": "ข้อพิพาทเรื่องสัญญาเช่ารถยนต์",
    "detail": "ลูกค้าโต้แย้งเรื่องค่าเสียหายเมื่อคืนรถยนต์เช่าก่อนกำหนด",
    "createdAt": "2026-07-24T11:20:00+07:00",
    "updatedAt": "2026-07-24T12:05:00+07:00",
    "status": "open",
    "contractId": "CT-2026-0130",
    "category": "dispute",
    "participants": ["user_654", "agent_22"],
    "messageCount": 20,
    "tags": ["ข้อพิพาท", "ค่าเสียหาย", "เช่ารถ"]
  }];

  // โหลดข้อมูลอัตโนมัติเมื่อ component mount
  useEffect(() => {
    setInfros(infroData);
  }, []);

  const isLoggedIn = user?.isLoggedIn ?? false;
  const displayName = isLoggedIn ? (user?.name || 'ผู้ใช้งาน') : 'Guest';
  const displayEmail = isLoggedIn ? maskEmail(user?.email) : '***@gmail.com';

  return (
    // เดิมใช้ min-h-screen + py-10 ทำให้ความสูงยืดตามเนื้อหา footer จึงไม่ชิดขอบล่างของกรอบ
    // เปลี่ยนเป็น h-screen (สูงคงที่เท่าจอ/กรอบ) และตัด padding แนวตั้งออก
    // แล้วค่อยใส่ padding ให้ container ด้านในแทน เพื่อให้ footer ล็อกอยู่ขอบล่างเสมอ
    <div className="h-screen bg-neutral-950 flex justify-center px-4 overflow-hidden">
      <div className="w-full max-w-2xl flex flex-col h-full py-10">
        {/* หัวข้อ */}
        <div className="mb-8 flex items-end justify-between border-b border-neutral-800 pb-5 flex-shrink-0">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-amber-500/70 mb-1">Legal desk</p>
            <h1 className="text-2xl font-semibold text-neutral-100" style={{ fontFamily: 'Georgia, "Noto Serif Thai", serif' }}>
              เรื่องที่ปรึกษา
            </h1>
          </div>
          <span className="text-xs text-neutral-500">{infros.length} เรื่อง</span>
        </div>

        {/* ปุ่มเพิ่มปุ่ม (ไม่มีฟังก์ชัน) */}
        <div className="mb-6 flex-shrink-0">
          <button
            onClick={onNewChat}
            className="px-4 py-2 text-sm font-medium bg-amber-500 text-neutral-950 rounded-lg hover:bg-amber-400 transition-colors"
          >
            +Newchat
          </button>
        </div>

        {/* รายการเรื่องที่ปรึกษา: เลื่อน (scroll) ได้เมื่อรายการเยอะเกินพื้นที่ */}
        {/* สไตล์ scrollbar ให้เข้ากับธีม: บาง โปร่ง สีเทาเข้ม และเปลี่ยนเป็นสีอำพันตอน hover */}
        <div
          className="space-y-3 flex-1 min-h-0 overflow-y-auto pr-2 -mr-2
            [&::-webkit-scrollbar]:w-1.5
            [&::-webkit-scrollbar-track]:bg-transparent
            [&::-webkit-scrollbar-thumb]:bg-neutral-800
            [&::-webkit-scrollbar-thumb]:rounded-full
            hover:[&::-webkit-scrollbar-thumb]:bg-amber-500/40"
          style={{ scrollbarWidth: 'thin', scrollbarColor: '#262626 transparent' }}
        >
          {infros.length === 0 ? (
            <div className="text-center text-neutral-600 py-16 text-sm border border-dashed border-neutral-800 rounded-xl">
              กำลังโหลดข้อมูล...
            </div>
          ) : (
            infros.map((chat) => (
              <div
                key={chat.id}
                onClick={() => onSelectChat?.(chat)}
                className="rounded-xl bg-neutral-900 border border-neutral-800 hover:border-neutral-700 transition-colors px-5 py-4 cursor-pointer"
              >
                <h3 className="text-[15px] font-medium text-neutral-100 leading-snug mb-2">
                  {chat.title}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {chat.tags.map((tag, i) => (
                    <span
                      key={i}
                      className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/30"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer: โปรไฟล์ผู้ใช้ + ปุ่ม logout — ล็อกอยู่ขอบล่างของกรอบเสมอ */}
        <div className="mt-4 pt-4 border-t border-neutral-800 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {/* วงกลมโปรไฟล์เปล่า */}
            <div className="w-10 h-10 rounded-full border-2 border-neutral-700 flex-shrink-0" />

            <div className="min-w-0">
              <p className="text-sm font-medium text-neutral-100 truncate">
                {displayName}
              </p>
              <p className="text-xs text-neutral-500 truncate">
                {displayEmail}
              </p>
            </div>
          </div>

          {/* ปุ่ม logout (สัญลักษณ์) */}
          <button
            onClick={onLogout}
            aria-label="logout"
            title="ออกจากระบบ"
            className="p-2 rounded-lg text-neutral-500 hover:text-amber-400 hover:bg-neutral-900 transition-colors flex-shrink-0"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;