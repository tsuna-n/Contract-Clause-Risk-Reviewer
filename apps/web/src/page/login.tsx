import { FileSearch, ScanText, BookOpen, ArrowUpRight, CheckCheck } from "lucide-react";
import { BackgroundOrbs, GridOverlay, LoginCard } from "../component/login";

export default function LoginPage() {
  return (
    <div className="login-page">
      <BackgroundOrbs />
      <GridOverlay />
      <header className="login-header">
        <div className="brand-lockup"><span className="brand-icon"><FileSearch size={23} /></span><span>UrRisk<span className="brand-subtitle">CONTRACT INTELLIGENCE</span></span></div>
        <span className="text-xs tracking-wide text-slate-400">Your legal review workspace</span>
      </header>
      <main className="login-main">
        <section className="login-story animate-fade-in-up">
          <p className="eyebrow"><span className="inline-block h-1.5 w-1.5 rounded-full bg-teal-300 mr-2" /> A CLEARER VIEW OF EVERY CONTRACT</p>
          <h1>อ่านสัญญาให้ชัด<br /><span>เห็นความเสี่ยงให้ครบ</span></h1>
          <p className="login-description">เปลี่ยนเอกสารที่ซับซ้อนเป็นข้อสัญญาที่เข้าใจง่าย<br />ให้ AI ช่วยตรวจ พร้อมเหตุผลและมาตรฐานอ้างอิงในที่เดียว</p>
          <div className="login-features">
            <div><ScanText size={21} /><span>ตรวจเป็นรายข้อ<small>แยกประเด็นจากเอกสารสัญญา</small></span></div>
            <div><BookOpen size={21} /><span>มีมาตรฐานอ้างอิง<small>เชื่อมโยงผลตรวจกับ Playbook</small></span></div>
            <div><CheckCheck size={21} /><span>ตัดสินใจได้ด้วยตัวเอง<small>ทบทวนและรับรองผลการตรวจ</small></span></div>
          </div>
          <div className="login-note"><span className="note-line" /> จากเอกสารสู่การตัดสินใจที่รอบคอบ <ArrowUpRight size={16} /></div>
        </section>
        <section className="login-auth animate-fade-in-up anim-delay-1" aria-label="เข้าสู่ระบบ">
          <LoginCard />
          <p className="mt-6 text-center text-xs leading-relaxed text-slate-400">AI ช่วยประกอบการพิจารณา<br />ผลการตรวจไม่ใช่คำแนะนำทางกฎหมาย</p>
        </section>
      </main>
      <footer className="login-footer"><span>UrRisk · Contract Clause Risk Reviewer</span><span>Review with clarity.</span></footer>
    </div>
  );
}
