import { AlertCircle, Building2, Eraser, FileText, House, LoaderCircle, ScanSearch, ShieldCheck, TriangleAlert, Wand2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { FormEvent, MouseEvent, ReactNode } from "react";
import { useRef } from "react";
import { MAX_TEXT_CHARS, MAX_URL_CHARS } from "../config";
import type { Sample } from "../types";

const SAMPLE_ICONS: Record<string, ReactNode> = {
  obvious_scam: <TriangleAlert size={16} />,
  subtle_scam: <Building2 size={16} />,
  rental_scam: <House size={16} />,
  legitimate: <ShieldCheck size={16} />,
};

interface Props {
  text: string;
  url: string;
  loading: boolean;
  error: string | null;
  samples: Sample[];
  onTextChange: (value: string) => void;
  onUrlChange: (value: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  onSample: (sample: Sample) => void;
}

/** The input form: text, optional link, scan button and one-click samples. */
export function ScannerCard(props: Props) {
  const { text, url, loading, error, samples } = props;
  const cardRef = useRef<HTMLElement>(null);

  // Spotlight that follows the cursor (CSS variables set through the CSSOM, CSP-safe).
  function trackPointer(event: MouseEvent<HTMLElement>) {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    card.style.setProperty("--mx", `${event.clientX - rect.left}px`);
    card.style.setProperty("--my", `${event.clientY - rect.top}px`);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    props.onSubmit();
  }

  const nearLimit = text.length > MAX_TEXT_CHARS * 0.9;

  return (
    <motion.section
      ref={cardRef}
      className="card card-glow"
      aria-labelledby="scan-heading"
      onMouseMove={trackPointer}
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
    >
      <h2 id="scan-heading" className="card-title">
        <FileText size={24} aria-hidden="true" /> Scan an offer letter or message
      </h2>

      <form onSubmit={submit} noValidate aria-busy={loading}>
        <div className="field">
          <label htmlFor="offer-text">Offer letter, email or message text</label>
          <p id="offer-text-hint" className="hint">
            Paste the full text, including the sender's email address and any links.
          </p>
          <div className="input-shell">
            <textarea
              id="offer-text"
              rows={10}
              maxLength={MAX_TEXT_CHARS}
              spellCheck={false}
              value={text}
              onChange={(e) => props.onTextChange(e.target.value)}
              aria-describedby="offer-text-hint offer-text-count"
            />
            <AnimatePresence>
              {loading && (
                <motion.div
                  className="scan-overlay"
                  aria-hidden="true"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <motion.div
                    className="scan-line"
                    initial={{ top: "-60px" }}
                    animate={{ top: "100%" }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <p id="offer-text-count" className={`hint counter${nearLimit ? " near-limit" : ""}`}>
            {text.length.toLocaleString("en-IN")} / {MAX_TEXT_CHARS.toLocaleString("en-IN")} characters
          </p>
        </div>

        <div className="field">
          <label htmlFor="offer-url">
            Link from the message <span className="optional">(optional)</span>
          </label>
          <p id="offer-url-hint" className="hint">
            For example the "joining portal" or "payment" link. We safely read that page too.
          </p>
          <div className="input-shell">
            <input
              id="offer-url"
              type="url"
              inputMode="url"
              autoComplete="off"
              maxLength={MAX_URL_CHARS}
              placeholder="https://"
              value={url}
              onChange={(e) => props.onUrlChange(e.target.value)}
              aria-describedby="offer-url-hint"
            />
          </div>
        </div>

        <AnimatePresence>
          {error && (
            <motion.p
              className="form-error"
              role="alert"
              initial={{ opacity: 0, height: 0, x: 0 }}
              animate={{ opacity: 1, height: "auto", x: [0, -8, 8, -5, 5, 0] }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.45 }}
            >
              <AlertCircle size={18} aria-hidden="true" /> {error}
            </motion.p>
          )}
        </AnimatePresence>

        <div className="actions">
          <motion.button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            whileHover={{ scale: 1.03, y: -2 }}
            whileTap={{ scale: 0.97 }}
          >
            {loading ? (
              <LoaderCircle size={20} className="spin" aria-hidden="true" />
            ) : (
              <ScanSearch size={20} aria-hidden="true" />
            )}
            {loading ? "Scanning…" : "Scan for scam signals"}
          </motion.button>
          <motion.button
            type="button"
            className="btn btn-ghost"
            onClick={props.onClear}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            <Eraser size={18} aria-hidden="true" /> Clear
          </motion.button>
        </div>
      </form>

      {samples.length > 0 && (
        <div className="samples">
          <h2 id="samples-heading">
            <Wand2 size={18} aria-hidden="true" /> Try a sample (fictional, one click)
          </h2>
          <motion.ul
            className="sample-list"
            aria-labelledby="samples-heading"
            initial="hidden"
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.08, delayChildren: 0.6 } } }}
          >
            {samples.map((sample) => (
              <motion.li
                key={sample.id}
                variants={{ hidden: { opacity: 0, y: 12, scale: 0.9 }, show: { opacity: 1, y: 0, scale: 1 } }}
              >
                <motion.button
                  type="button"
                  className="chip"
                  data-kind={sample.id}
                  disabled={loading}
                  onClick={() => props.onSample(sample)}
                  whileHover={{ y: -3 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <span className="chip-icon" aria-hidden="true">
                    {SAMPLE_ICONS[sample.id] ?? <FileText size={16} />}
                  </span>
                  {sample.title}
                </motion.button>
              </motion.li>
            ))}
          </motion.ul>
        </div>
      )}
    </motion.section>
  );
}
