/**
 * Decorative, slow-moving sky background (hidden from assistive tech):
 * a shifting sky gradient, a pulsing sun with rotating rays, drifting colour
 * glows and clouds, a faint grid, rising bubbles and flowing waves.
 * Pure CSS animations; all are switched off under prefers-reduced-motion.
 */

// Fixed values so the render is deterministic (no Math.random in render).
const BUBBLES = [
  { left: "6%", color: "#e0f2fe", delay: "0s", duration: "36s", size: 8 },
  { left: "14%", color: "#bae6fd", delay: "-9s", duration: "42s", size: 5 },
  { left: "23%", color: "#cffafe", delay: "-17s", duration: "33s", size: 10 },
  { left: "31%", color: "#e0e7ff", delay: "-4s", duration: "46s", size: 6 },
  { left: "42%", color: "#e0f2fe", delay: "-22s", duration: "39s", size: 7 },
  { left: "53%", color: "#bae6fd", delay: "-13s", duration: "35s", size: 9 },
  { left: "61%", color: "#cffafe", delay: "-28s", duration: "44s", size: 5 },
  { left: "70%", color: "#e0e7ff", delay: "-6s", duration: "38s", size: 8 },
  { left: "79%", color: "#e0f2fe", delay: "-19s", duration: "41s", size: 6 },
  { left: "88%", color: "#bae6fd", delay: "-25s", duration: "37s", size: 10 },
  { left: "95%", color: "#cffafe", delay: "-11s", duration: "48s", size: 5 },
];

// Clouds cross the sky at different heights, sizes and speeds.
const CLOUDS = [
  { top: "12%", scale: 1, delay: "0s", duration: "150s", opacity: 0.85 },
  { top: "30%", scale: 0.7, delay: "-60s", duration: "190s", opacity: 0.7 },
  { top: "6%", scale: 0.55, delay: "-110s", duration: "170s", opacity: 0.65 },
  { top: "46%", scale: 0.9, delay: "-35s", duration: "220s", opacity: 0.55 },
];

const WAVE_PATH =
  "M0 120 C 180 60 360 180 540 120 C 720 60 900 180 1080 120 C 1260 60 1440 180 1620 120 " +
  "C 1800 60 1980 180 2160 120 C 2340 60 2520 180 2700 120 C 2880 60 3060 180 3240 120 V 220 H 0 Z";

function Wave({ className }: { className: string }) {
  return (
    <svg className={`wave ${className}`} viewBox="0 0 3240 220" preserveAspectRatio="none">
      <path d={WAVE_PATH} />
    </svg>
  );
}

export function Background() {
  return (
    <div className="bg" aria-hidden="true">
      <div className="bg-base" />
      <div className="bg-rays" />
      <div className="sun" />
      <div className="blob blob-1" />
      <div className="blob blob-2" />
      <div className="blob blob-3" />
      <div className="blob blob-4" />
      <div className="blob blob-5" />
      {CLOUDS.map((c) => (
        <span
          key={c.top}
          className="cloud"
          style={{
            top: c.top,
            scale: String(c.scale),
            opacity: c.opacity,
            animationDelay: c.delay,
            animationDuration: c.duration,
          }}
        />
      ))}
      <div className="bg-grid" />
      {BUBBLES.map((b) => (
        <span
          key={b.left}
          className="particle"
          style={{
            left: b.left,
            bottom: "-2%",
            width: b.size,
            height: b.size,
            background: b.color,
            border: "1px solid rgb(255 255 255 / 60%)",
            boxShadow: `0 0 10px 1px ${b.color}`,
            animationDelay: b.delay,
            animationDuration: b.duration,
          }}
        />
      ))}
      <div className="waves">
        <Wave className="wave-1" />
        <Wave className="wave-2" />
      </div>
    </div>
  );
}
