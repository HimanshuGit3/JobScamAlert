import {
  Ban, CalendarClock, ChevronDown, Clock, Fingerprint, Globe, IdCard, IndianRupee, Link2,
  LockOpen, Mail, ShieldAlert, SpellCheck, TrendingUp, UserX, Wallet,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";
import { useId, useState } from "react";
import { useCountUp } from "../hooks/useCountUp";
import type { SignalHit } from "../types";

const ICONS: Record<string, ReactNode> = {
  safe_browsing: <ShieldAlert size={20} />,
  payment_demand: <IndianRupee size={20} />,
  new_domain: <CalendarClock size={20} />,
  young_domain: <CalendarClock size={20} />,
  lookalike_domain: <Fingerprint size={20} />,
  free_email: <Mail size={20} />,
  sensitive_documents: <IdCard size={20} />,
  untraceable_payment: <Wallet size={20} />,
  domain_mismatch: <Globe size={20} />,
  no_interview: <UserX size={20} />,
  unrealistic_salary: <TrendingUp size={20} />,
  suspicious_tld: <Ban size={20} />,
  urgency: <Clock size={20} />,
  url_shortener: <Link2 size={20} />,
  insecure_url: <LockOpen size={20} />,
  poor_grammar: <SpellCheck size={20} />,
};

/** The largest single weight in app/scoring.py; used to scale the bar. */
const MAX_WEIGHT = 40;

export const cardVariants = {
  hidden: { opacity: 0, y: 24, scale: 0.97 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring" as const, stiffness: 170, damping: 20 } },
};

interface Props {
  hit: SignalHit;
  index: number;
  defaultOpen?: boolean;
}

/** One fired signal: icon, animated points, weight bar and expandable evidence. */
export function SignalCard({ hit, index, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const points = useCountUp(hit.points, 0.9, 0.5 + index * 0.08);
  const evidenceId = useId();

  return (
    <motion.li className="signal" variants={cardVariants} whileHover={{ y: -2 }}>
      <div className="signal-head">
        <span className="signal-icon" aria-hidden="true">
          {ICONS[hit.id] ?? <ShieldAlert size={20} />}
        </span>
        <p className="signal-name">{hit.signal}</p>
        <span className="signal-points" aria-label={`${hit.points} points`}>
          +{points}
        </span>
      </div>
      <div className="signal-bar" aria-hidden="true">
        <motion.div
          className="signal-bar-fill"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: Math.min(hit.points / MAX_WEIGHT, 1) }}
          transition={{ delay: 0.5 + index * 0.08, duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
      <p className="signal-explanation">{hit.explanation}</p>
      <button
        type="button"
        className="evidence-toggle"
        aria-expanded={open}
        aria-controls={evidenceId}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? "Hide evidence" : `Show evidence (${hit.evidence.length})`}
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={evidenceId}
            className="evidence"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            <ul>
              {hit.evidence.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}
