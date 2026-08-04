import { FileSearch } from "lucide-react";

/**
 * BrandHeader — "UrRisk" brand on the navy background.
 * Icon badge uses a very dark background with navy accent border.
 */
export default function BrandHeader() {
  return (
    <div className="flex flex-col items-center gap-5 text-center">
      {/* Icon badge */}
      <div
        className="flex h-[72px] w-[72px] items-center justify-center rounded-2xl border border-navy-500/30 bg-navy-500/10"
        style={{
          boxShadow:
            "0 0 32px rgba(58,100,168,0.25), 0 4px 20px rgba(0,0,0,0.6)",
        }}
      >
        <FileSearch className="h-9 w-9 text-navy-300 drop-shadow-[0_0_6px_rgba(58,100,168,0.5)]" />
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
        <p className="text-sm text-navy-300">
      
        </p>
      </div>
    </div>
  );
}
