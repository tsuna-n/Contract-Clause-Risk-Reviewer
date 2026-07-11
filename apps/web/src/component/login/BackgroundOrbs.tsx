/**
 * BackgroundOrbs — animated radial-gradient orbs on a pure-black background.
 * Dimmed opacity to keep the black aesthetic crisp.
 */
export default function BackgroundOrbs() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden">
      {/* Top-left teal orb */}
      <div
        className="absolute -top-48 -left-48 h-[650px] w-[650px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(20,184,166,0.45) 0%, rgba(6,182,212,0.2) 40%, transparent 70%)",
          filter: "blur(80px)",
          opacity: 0.12,
          animation: "orbFloat1 9s ease-in-out infinite",
        }}
      />

      {/* Bottom-right violet orb */}
      <div
        className="absolute -bottom-40 -right-40 h-[560px] w-[560px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(99,102,241,0.55) 0%, rgba(139,92,246,0.3) 40%, transparent 70%)",
          filter: "blur(75px)",
          opacity: 0.1,
          animation: "orbFloat2 11s ease-in-out infinite",
        }}
      />

      {/* Very subtle center glow */}
      <div
        className="absolute top-1/2 left-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(20,184,166,0.6) 0%, transparent 70%)",
          filter: "blur(100px)",
          opacity: 0.03,
        }}
      />
    </div>
  );
}
