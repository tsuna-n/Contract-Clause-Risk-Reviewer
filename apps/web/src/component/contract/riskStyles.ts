import type { RiskLevel } from "./types";

// One source of truth for risk colouring. Previously each panel kept its own
// copy of these maps, which is how CRITICAL survived in some and not others.

export const riskBadge: Record<RiskLevel, string> = {
  LOW: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
  MEDIUM: "bg-amber-500/20 text-amber-300 border border-amber-500/40",
  HIGH: "bg-red-500/20 text-red-300 border border-red-500/40",
  UNKNOWN: "bg-slate-500/20 text-slate-300 border border-slate-500/40",
};

export const riskRow: Record<RiskLevel, string> = {
  LOW: "border-l-4 border-emerald-400 bg-emerald-950/30",
  MEDIUM: "border-l-4 border-amber-400 bg-amber-950/30",
  HIGH: "border-l-4 border-red-400 bg-red-950/30",
  UNKNOWN: "border-l-4 border-slate-500 bg-slate-800/30",
};

export const riskRowSelected: Record<RiskLevel, string> = {
  LOW: "border-l-4 border-emerald-300 bg-emerald-900/55 ring-2 ring-navy-400/25 shadow-[0_0_0_1px_rgba(58,100,168,0.15)]",
  MEDIUM: "border-l-4 border-amber-300 bg-amber-900/55 ring-2 ring-navy-400/25 shadow-[0_0_0_1px_rgba(58,100,168,0.15)]",
  HIGH: "border-l-4 border-red-300 bg-red-900/55 ring-2 ring-navy-400/25 shadow-[0_0_0_1px_rgba(58,100,168,0.15)]",
  UNKNOWN: "border-l-4 border-slate-400 bg-slate-700/55 ring-2 ring-navy-400/20 shadow-[0_0_0_1px_rgba(58,100,168,0.12)]",
};

export const riskAccent: Record<RiskLevel, string> = {
  LOW: "text-emerald-400",
  MEDIUM: "text-amber-400",
  HIGH: "text-red-400",
  UNKNOWN: "text-slate-400",
};

export const riskAcceptButton: Record<RiskLevel, string> = {
  LOW: "bg-emerald-600 hover:bg-emerald-500 text-white",
  MEDIUM: "bg-amber-600 hover:bg-amber-500 text-white",
  HIGH: "bg-red-600 hover:bg-red-500 text-white",
  UNKNOWN: "bg-slate-600 hover:bg-slate-500 text-white",
};
