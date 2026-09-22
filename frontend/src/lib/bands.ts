import type { RiskBand } from "../types";

export interface BandInfo {
  className: string;
  headline: string;
  advice: string;
}

export const BANDS: Record<RiskBand, BandInfo> = {
  Low: {
    className: "band-low",
    headline: "Few scam signals found",
    advice: "No scanner is perfect. Verify with the company's official website before you pay or share anything.",
  },
  Suspicious: {
    className: "band-suspicious",
    headline: "Several warning signs",
    advice: "Don't pay or share documents until you verify the offer through official channels.",
  },
  "High Risk": {
    className: "band-high",
    headline: "This looks like a scam",
    advice: "Don't pay, don't share documents, and stop replying to the sender. Report it at cybercrime.gov.in or call 1930.",
  },
};

/** Band for a score, mirroring app/scoring.py thresholds (used for gauge colour while counting up). */
export function bandForScore(score: number): RiskBand {
  if (score >= 60) return "High Risk";
  if (score >= 30) return "Suspicious";
  return "Low";
}
