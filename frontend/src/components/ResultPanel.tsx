import { Bot, CircleCheck, Highlighter, Info, ListChecks, OctagonX, ShieldCheck, TriangleAlert } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { BANDS } from "../lib/bands";
import type { RiskBand, ScanReport } from "../types";
import { Gauge } from "./Gauge";
import { HighlightedText } from "./HighlightedText";
import { SignalCard } from "./SignalCard";

const BAND_ICON: Record<RiskBand, ReactNode> = {
  Low: <ShieldCheck size={24} aria-hidden="true" />,
  Suspicious: <TriangleAlert size={24} aria-hidden="true" />,
  "High Risk": <OctagonX size={24} aria-hidden="true" />,
};

interface Props {
  report: ScanReport;
}

/** Scan results. On mount, focus moves to the heading (keyboard and screen-reader users). */
export function ResultPanel({ report }: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    const heading = headingRef.current;
    if (!heading) return;
    heading.focus({ preventScroll: true });
    heading.scrollIntoView?.({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  }, [reduceMotion]);

  const { score, band, breakdown, skipped_checks: skipped, raw_total: raw } = report.result;
  const info = BANDS[band];

  return (
    <motion.section
      className="card"
      aria-labelledby="results-heading"
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
    >
      <h2 id="results-heading" className="card-title" tabIndex={-1} ref={headingRef}>
        <ListChecks size={24} aria-hidden="true" /> Scan result
      </h2>

      <div className="results-head">
        <Gauge score={score} band={band} />
        <div>
          <motion.p
            className={`band-badge ${info.className}`}
            initial={{ opacity: 0, scale: 0.5, rotate: -8 }}
            animate={
              band === "High Risk"
                ? { opacity: 1, scale: 1, rotate: [0, -3, 3, -2, 2, 0] }
                : { opacity: 1, scale: 1, rotate: 0 }
            }
            transition={{ delay: 1.4, type: "spring", stiffness: 260, damping: 14 }}
          >
            {BAND_ICON[band]} {band}
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.6 }}>
            <p className="verdict">{info.headline}</p>
            <p className="verdict-advice">{info.advice}</p>
            <div className="meta-row">
              <span className="meta">
                <strong>{breakdown.length}</strong> signal{breakdown.length === 1 ? "" : "s"} fired
              </span>
              {raw > score && (
                <span className="meta">
                  Raw total <strong>{raw}</strong>, capped at 100
                </span>
              )}
              <span className="meta">
                <Bot size={15} aria-hidden="true" />
                {report.ai_extraction_used ? "Gemini extraction used" : "Deterministic checks only"}
              </span>
            </div>
          </motion.div>
        </div>
      </div>

      {skipped.length > 0 && (
        <motion.div
          className="notice"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          transition={{ delay: 1.8, duration: 0.4 }}
        >
          <h3>
            <Info size={18} aria-hidden="true" /> Some checks were skipped
          </h3>
          <p className="hint">These checks couldn't run, so they added no points. The real risk may be higher than shown.</p>
          <ul>
            {skipped.map((s) => (
              <li key={`${s.check}-${s.reason}`}>
                <strong>{s.check}:</strong> {s.reason}
              </li>
            ))}
          </ul>
        </motion.div>
      )}

      <h3 className="section-title">
        <ListChecks size={20} aria-hidden="true" /> Why this score
      </h3>
      {breakdown.length === 0 ? (
        <motion.p className="no-signals" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
          <CircleCheck size={20} aria-hidden="true" /> No scam signals found. Still verify through the company's official website.
        </motion.p>
      ) : (
        <motion.ol
          className="signals"
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.08, delayChildren: 0.4 } } }}
        >
          {breakdown.map((hit, i) => (
            <SignalCard key={hit.id} hit={hit} index={i} defaultOpen={i < 2} />
          ))}
        </motion.ol>
      )}

      {report.highlights.length > 0 && (
        <>
          <h3 className="section-title">
            <Highlighter size={20} aria-hidden="true" /> Suspicious sentences
          </h3>
          <p className="hint">
            Highlighted, underlined parts triggered a signal. If you entered a link, the linked page's text follows yours.
          </p>
          <HighlightedText text={report.analyzed_text} phrases={report.highlights} />
        </>
      )}
    </motion.section>
  );
}
