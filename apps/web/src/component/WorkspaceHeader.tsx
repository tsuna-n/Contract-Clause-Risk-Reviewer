import type { ReactNode } from "react";
import { BookOpen, FileSearch, Gauge, Activity, ArrowUpRight } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

const links = [
  { to: "/manual", label: "ตรวจสัญญา", icon: FileSearch },
  { to: "/playbook", label: "Playbook", icon: BookOpen },
  { to: "/evaluate", label: "Evaluate", icon: Gauge },
  { to: "/system", label: "System", icon: Activity },
];

export default function WorkspaceHeader({ actions }: { actions?: ReactNode }) {
  return (
    <header className="workspace-header">
      <Link to="/manual" className="brand-lockup" aria-label="UrRisk หน้าหลัก">
        <span className="brand-icon"><FileSearch size={21} /></span>
        <span>UrRisk<span className="brand-subtitle">CONTRACT INTELLIGENCE</span></span>
      </Link>
      <nav className="workspace-nav" aria-label="เมนูหลัก">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => `workspace-nav-link ${isActive ? "is-active" : ""}`}>
            <Icon size={16} /><span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="flex items-center gap-3">
        {actions}
        <Link to="/manual" className="header-return">กลับหน้าหลัก <ArrowUpRight size={15} /></Link>
      </div>
    </header>
  );
}
