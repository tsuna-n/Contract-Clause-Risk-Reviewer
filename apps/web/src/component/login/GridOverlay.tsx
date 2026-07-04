/**
 * GridOverlay — ultra-subtle grid on black background.
 * Opacity lowered so the pure-black feel is preserved.
 */
export default function GridOverlay() {
  return (
    <div
      className="pointer-events-none fixed inset-0"
      style={{
        backgroundImage: `
          linear-gradient(rgba(255,255,255,1) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)
        `,
        backgroundSize: "44px 44px",
        opacity: 0.018,
      }}
    />
  );
}
