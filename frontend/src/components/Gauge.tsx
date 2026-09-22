import { motion } from "motion/react";
import { useAnimatedValue } from "../hooks/useCountUp";
import { bandForScore } from "../lib/bands";
import type { RiskBand } from "../types";

const CX = 130;
const CY = 130;
const R = 105;
const ARC = `M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`;
const TONE: Record<RiskBand, string> = { Low: "tone-low", Suspicious: "tone-suspicious", "High Risk": "tone-high" };

/** Point on the semicircle for a 0-100 value (0 = left, 100 = right). */
function polar(value: number, radius: number): [number, number] {
  const angle = Math.PI - (Math.PI * value) / 100;
  return [CX + radius * Math.cos(angle), CY - radius * Math.sin(angle)];
}

const TICKS = Array.from({ length: 11 }, (_, i) => i * 10);

interface Props {
  score: number;
  band: RiskBand;
}

/** Semicircular gauge whose arc, needle, number and colour animate together. */
export function Gauge({ score, band }: Props) {
  const value = useAnimatedValue(score, 1.8, 0.2);
  const shown = Math.round(value);
  const [nx, ny] = polar(value, R - 26);
  const tone = TONE[bandForScore(shown)];

  return (
    <motion.div
      className="gauge"
      role="img"
      aria-label={`Scam Threat Index ${score} out of 100: ${band}`}
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 120, damping: 14 }}
    >
      <svg viewBox="0 0 260 160" aria-hidden="true">
        <defs>
          <linearGradient id="gauge-gradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" className="stop-low" />
            <stop offset="45%" className="stop-suspicious" />
            <stop offset="100%" className="stop-high" />
          </linearGradient>
          <filter id="gauge-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path className="gauge-track" d={ARC} pathLength={100} />
        <path
          className="gauge-value"
          d={ARC}
          pathLength={100}
          stroke="url(#gauge-gradient)"
          strokeDasharray={`${value} 100`}
          filter="url(#gauge-glow)"
        />
        {TICKS.map((t) => {
          const [x1, y1] = polar(t, R + 14);
          const [x2, y2] = polar(t, R + (t % 50 === 0 ? 22 : 18));
          return <line key={t} className="gauge-tick" x1={x1} y1={y1} x2={x2} y2={y2} />;
        })}
        <line className="gauge-needle" x1={CX} y1={CY} x2={nx} y2={ny} />
        <circle className="gauge-hub" cx={CX} cy={CY} r={7} />
      </svg>
      <div className="gauge-readout">
        <div className={`gauge-number ${tone}`}>
          {shown}
          <small>/100</small>
        </div>
        <div className="gauge-label">Scam Threat Index</div>
      </div>
    </motion.div>
  );
}
