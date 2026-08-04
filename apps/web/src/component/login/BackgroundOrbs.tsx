/**
 * BackgroundOrbs — animated radial-gradient orbs on the navy background.
 * Dimmed opacity to keep the navy aesthetic crisp.
 */
export default function BackgroundOrbs() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden">
      {/* Top-left navy orb */}
      <div
        className="absolute -top-48 -left-48 h-[650px] w-[650px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(58,100,168,0.45) 0%, rgba(84,128,191,0.2) 40%, transparent 70%)",
          filter: "blur(80px)",
          opacity: 0.18,
          animation: "orbFloat1 9s ease-in-out infinite",
        }}
      />

      {/* Bottom-right blue orb */}
      <div
        className="absolute -bottom-40 -right-40 h-[560px] w-[560px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(44,77,130,0.55) 0%, rgba(33,58,99,0.3) 40%, transparent 70%)",
          filter: "blur(75px)",
          opacity: 0.16,
          animation: "orbFloat2 11s ease-in-out infinite",
        }}
      />

      {/* Very subtle center glow */}
      <div
        className="absolute top-1/2 left-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(58,100,168,0.6) 0%, transparent 70%)",
          filter: "blur(100px)",
          opacity: 0.05,
        }}
      />
    </div>
  );
}
