import { ScanSearch, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useCountUp } from "../hooks/useCountUp";

const TITLE = ["Is", "that", "offer", "letter"];

function Stat({ value, suffix = "", label, delay }: { value: number; suffix?: string; label: string; delay: number }) {
  const n = useCountUp(value, 1.6, delay);
  return (
    <motion.li
      className="stat"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: "spring", stiffness: 180, damping: 18 }}
    >
      <strong>
        {Math.round(n)}
        {suffix}
      </strong>
      <span>{label}</span>
    </motion.li>
  );
}

/** Animated intro: orbiting shield, word-by-word title and counters. */
export function Hero() {
  return (
    <section className="hero wrap" aria-labelledby="hero-title">
      <motion.div
        className="hero-shield"
        aria-hidden="true"
        initial={{ scale: 0.4, opacity: 0, rotate: -30 }}
        animate={{ scale: 1, opacity: 1, rotate: 0 }}
        transition={{ type: "spring", stiffness: 140, damping: 14 }}
      >
        <span className="orbit" />
        <span className="orbit orbit-2">
          <span className="orbit-dot" />
        </span>
        <motion.span
          className="core"
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
        >
          <ScanSearch size={38} strokeWidth={2.2} />
        </motion.span>
      </motion.div>

      <motion.p
        className="eyebrow"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <Sparkles size={15} aria-hidden="true" /> Gemini reads it · deterministic rules score it
      </motion.p>

      <h1 id="hero-title">
        {TITLE.map((word, i) => (
          <motion.span
            key={word}
            className="word"
            initial={{ opacity: 0, y: 28, filter: "blur(8px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ delay: 0.25 + i * 0.09, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            {word}
          </motion.span>
        ))}{" "}
        <motion.span
          className="word gradient-text"
          initial={{ opacity: 0, scale: 0.7 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.7, type: "spring", stiffness: 200, damping: 12 }}
        >
          a scam?
        </motion.span>
      </h1>

      <motion.p
        className="hero-sub"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.6 }}
      >
        Paste a job offer, appointment letter or rental message. Get an explainable Scam Threat Index
        from 0 to 100, with every point traced to a red flag, before you pay or share anything.
      </motion.p>

      <ul className="hero-stats" aria-label="What the scanner checks">
        <Stat value={16} label="red-flag signals" delay={1.0} />
        <Stat value={25} label="brands protected" delay={1.1} />
        <Stat value={0} suffix=" bytes" label="of your text stored" delay={1.2} />
      </ul>
    </section>
  );
}
