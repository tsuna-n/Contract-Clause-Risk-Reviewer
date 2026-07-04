import { FileSearch } from "lucide-react";

/**
 * BrandHeader — "UrRisk" brand on a pure black background.
 * Icon badge uses a very dark background with teal accent border.
 */
export default function BrandHeader() {
  return (
    <div className="flex flex-col items-center gap-5 text-center">
      {/* Icon badge */}
      <div
        className="flex h-[72px] w-[72px] items-center justify-center rounded-2xl border border-teal-500/20 bg-white/[0.03]"
        style={{
          boxShadow:
            "0 0 32px rgba(20,184,166,0.12), 0 4px 20px rgba(0,0,0,0.6)",
        }}
      >
        <FileSearch className="h-9 w-9 text-teal-400 drop-shadow-[0_0_6px_rgba(20,184,166,0.5)]" />
      </div>

      {/* Brand name */}
      <div className="space-y-2">
        <h1
          className="text-4xl font-bold tracking-tight text-white"
          style={{
            textShadow: "0 0 30px rgba(255,255,255,0.08)",
            letterSpacing: "-0.01em",
          }}
        >
          UrRisk
        </h1>
        <p className="text-sm text-zinc-500">
     
        </p>
      </div>
    </div>
  );
}
