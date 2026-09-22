import { MotionConfig, animate, useReducedMotion } from "motion/react";
import type { AnimationPlaybackControls } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { ApiError, getSamples, getStatus, scan } from "./api";
import { Advice } from "./components/Advice";
import { Background } from "./components/Background";
import { Hero } from "./components/Hero";
import { ResultPanel } from "./components/ResultPanel";
import { ScannerCard } from "./components/ScannerCard";
import { ScanProgress } from "./components/ScanProgress";
import { TopBar } from "./components/TopBar";
import type { IntegrationStatus, Sample, ScanReport } from "./types";

type Phase = "idle" | "loading" | "done";

/** Client-side check mirroring the server's rules, for instant feedback. */
export function validateInput(text: string, url: string): string | null {
  if (!text && !url) return "Paste the offer text or enter a link to scan.";
  if (url && !/^https?:\/\//i.test(url)) return "The link must start with http:// or https://";
  return null;
}

export function App() {
  const reduceMotion = useReducedMotion();
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [report, setReport] = useState<ScanReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [scanId, setScanId] = useState(0);
  const latestScan = useRef(0); // ignore responses from superseded scans
  const typing = useRef<AnimationPlaybackControls | null>(null); // sample typewriter
  const typingText = useRef<string | null>(null);

  useEffect(() => {
    getSamples().then(setSamples).catch(() => undefined); // samples are optional
    getStatus().then(setStatus).catch(() => undefined); // status is informational
  }, []);

  async function runScan(scanText: string, scanUrl: string) {
    const cleanText = scanText.trim();
    const cleanUrl = scanUrl.trim();
    const problem = validateInput(cleanText, cleanUrl);
    if (problem) {
      setError(problem);
      setAnnouncement(problem);
      return;
    }
    const id = ++latestScan.current;
    setError(null);
    setPhase("loading");
    setAnnouncement("Scanning…");
    try {
      const result = await scan(cleanText, cleanUrl || null);
      if (id !== latestScan.current) return;
      setReport(result);
      setScanId(id);
      setPhase("done");
      setAnnouncement(
        `Scan complete. Scam Threat Index ${result.result.score} out of 100, ${result.result.band}.`,
      );
    } catch (err) {
      if (id !== latestScan.current) return;
      const message = err instanceof ApiError ? err.message : "The scan failed. Please try again.";
      setError(message);
      setAnnouncement(message);
      setPhase(report ? "done" : "idle");
    }
  }

  /** Samples "type themselves" into the box, then scan. */
  /** Stop the sample typewriter; returns the full sample text if one was being typed. */
  function stopTyping(): string | null {
    const full = typingText.current;
    typing.current?.stop();
    typing.current = null;
    typingText.current = null;
    return full;
  }

  /** User edits always win over the sample typewriter. */
  function handleTextChange(value: string) {
    stopTyping();
    setText(value);
  }

  /**
   * One-click demo: the scan starts immediately with the full sample text.
   * The "typing" effect is purely decorative and never gates the scan, so a
   * paused or throttled animation can't stop the demo from working.
   */
  function handleSample(sample: Sample) {
    stopTyping();
    setUrl("");
    setText(sample.text);
    void runScan(sample.text, "");
    if (reduceMotion) return;
    typingText.current = sample.text;
    typing.current = animate(0, sample.text.length, {
      duration: 0.8,
      ease: "easeOut",
      onUpdate: (n) => setText(sample.text.slice(0, Math.round(n))),
      onComplete: () => {
        typing.current = null;
        typingText.current = null;
        setText(sample.text);
      },
    });
  }

  function clear() {
    stopTyping();
    latestScan.current += 1; // drop any in-flight result
    setText("");
    setUrl("");
    setError(null);
    setReport(null);
    setPhase("idle");
    document.getElementById("offer-text")?.focus();
  }

  return (
    <MotionConfig reducedMotion="user">
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <Background />
      <TopBar status={status} />
      <Hero />

      <main id="main" className="wrap">
        <ScannerCard
          text={text}
          url={url}
          loading={phase === "loading"}
          error={error}
          samples={samples}
          onTextChange={handleTextChange}
          onUrlChange={setUrl}
          onSubmit={() => {
            const full = stopTyping(); // mid-typewriter: use the whole sample, not a fragment
            if (full) setText(full);
            void runScan(full ?? text, url);
          }}
          onClear={clear}
          onSample={handleSample}
        />

        <p className="visually-hidden" role="status" aria-live="polite">
          {announcement}
        </p>

        {/* Results render as soon as data arrives. They must never wait on an
            exit animation, which can stall (background tab, throttled frames). */}
        {phase === "loading" && <ScanProgress status={status} />}
        {phase === "done" && report && <ResultPanel key={scanId} report={report} />}

        <Advice />
      </main>

      <footer className="site-footer wrap">
        <p>
          Your text is analysed only to produce this result and is never stored. The score is a risk estimate, not
          legal proof: always verify.
        </p>
      </footer>
    </MotionConfig>
  );
}
