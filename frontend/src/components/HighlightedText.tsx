import { useMemo } from "react";
import { toSegments } from "../lib/highlight";

interface Props {
  text: string;
  phrases: string[];
}

/**
 * The analysed text with suspicious phrases wrapped in <mark>.
 * Rendered as React text nodes only (no HTML parsing), so pasted markup can't run.
 * Each mark "sweeps" in one after another via a CSS animation delay.
 */
export function HighlightedText({ text, phrases }: Props) {
  const segments = useMemo(() => toSegments(text, phrases), [text, phrases]);
  let markIndex = 0;
  return (
    <pre className="letter" tabIndex={0} aria-label="Analysed text with suspicious parts highlighted">
      {segments.map((segment, i) => {
        if (!segment.marked) return segment.text;
        const delay = `${0.8 + markIndex++ * 0.18}s`;
        return (
          <mark key={i} className="hl" style={{ animationDelay: delay }}>
            {segment.text}
          </mark>
        );
      })}
    </pre>
  );
}
