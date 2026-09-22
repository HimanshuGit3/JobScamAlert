import { ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import type { IntegrationStatus } from "../types";

interface Props {
  status: IntegrationStatus | null;
}

/** Logo plus live indicators of which integrations are switched on. */
export function TopBar({ status }: Props) {
  const pills = status
    ? [
        { label: "Gemini AI", on: status.gemini },
        { label: "Safe Browsing", on: status.safe_browsing },
        { label: "Domain age", on: true },
        { label: "Link reading", on: status.fetch_linked_pages },
      ]
    : [];

  return (
    <header className="topbar">
      <div className="wrap topbar-inner">
        <motion.p
          className="logo"
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          <span className="logo-mark" aria-hidden="true">
            <ShieldCheck size={20} strokeWidth={2.5} />
          </span>
          Offer Letter Inspector
        </motion.p>
        {pills.length > 0 && (
          <ul className="status-pills" aria-label="Checks available">
            {pills.map((p, i) => (
              <motion.li
                key={p.label}
                className="pill"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * i + 0.2 }}
              >
                <span className={`dot${p.on ? " on" : ""}`} aria-hidden="true" />
                {p.label}
                <span className="visually-hidden">: {p.on ? "on" : "off"}</span>
              </motion.li>
            ))}
          </ul>
        )}
      </div>
    </header>
  );
}
