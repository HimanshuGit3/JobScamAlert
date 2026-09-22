import { CircleCheck, CircleDashed, CircleSlash, LoaderCircle } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import type { IntegrationStatus } from "../types";

interface Stage {
  label: string;
  /** False when the check is not configured on the server, so it won't run. */
  enabled: boolean;
}

/** The checks that really run on the server (several in parallel). */
export function stagesFor(status: IntegrationStatus | null): Stage[] {
  return [
    { label: "Extracting links, emails and payment requests", enabled: true },
    { label: "Reading the letter with Gemini", enabled: status?.gemini ?? true },
    { label: "Checking domain age (RDAP)", enabled: true },
    { label: "Checking Google Safe Browsing", enabled: status?.safe_browsing ?? true },
    { label: "Calculating the Scam Threat Index", enabled: true },
  ];
}

const BLIPS = [
  { top: "28%", left: "62%", delay: "0.3s" },
  { top: "58%", left: "30%", delay: "1.1s" },
  { top: "70%", left: "66%", delay: "1.7s" },
];

type StageState = "done" | "active" | "pending" | "skipped";

function StageIcon({ state }: { state: StageState }) {
  return (
    <>
      {state === "done" ? (
        <motion.span
          key="done"
          initial={{ scale: 0, rotate: -90 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ type: "spring", stiffness: 400, damping: 15 }}
        >
          <CircleCheck size={20} />
        </motion.span>
      ) : state === "active" ? (
        <motion.span key="active" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <LoaderCircle size={20} className="spin" />
        </motion.span>
      ) : state === "skipped" ? (
        <motion.span key="skipped">
          <CircleSlash size={20} />
        </motion.span>
      ) : (
        <motion.span key="pending">
          <CircleDashed size={20} />
        </motion.span>
      )}
    </>
  );
}

/**
 * Shown while a scan is running: a radar sweep and a checklist that animates
 * through the checks during the single /api/scan request.
 */
export function ScanProgress({ status }: { status: IntegrationStatus | null }) {
  const stages = stagesFor(status);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActive((i) => Math.min(i + 1, stages.length - 1));
    }, 650);
    return () => window.clearInterval(timer);
  }, [stages.length]);

  return (
    <motion.section
      className="card progress-card"
      aria-label="Scan in progress"
      initial={{ opacity: 0, y: 30, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4 }}
    >
      <div className="radar" aria-hidden="true">
        <div className="radar-sweep" />
        {BLIPS.map((b) => (
          <span key={b.top} className="radar-blip" style={{ top: b.top, left: b.left, animationDelay: b.delay }} />
        ))}
      </div>
      <ol className="stage-list">
        {stages.map((stage, i) => {
          const state: StageState = !stage.enabled
            ? "skipped"
            : i < active
              ? "done"
              : i === active
                ? "active"
                : "pending";
          return (
            <motion.li
              key={stage.label}
              className={`stage ${state}`}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 }}
            >
              <span className="stage-icon" aria-hidden="true">
                <StageIcon state={state} />
              </span>
              <span>
                {stage.label}
                {state === "skipped" && <span className="stage-note"> (not configured, skipped)</span>}
              </span>
            </motion.li>
          );
        })}
      </ol>
    </motion.section>
  );
}
