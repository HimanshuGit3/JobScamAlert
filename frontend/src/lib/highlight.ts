/** A run of text that is either plain or highlighted. */
export interface Segment {
  text: string;
  marked: boolean;
}

/** Merge every occurrence of every phrase into sorted, non-overlapping [start, end) ranges. */
export function highlightRanges(text: string, phrases: string[]): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  for (const phrase of phrases) {
    if (!phrase) continue;
    let i = text.indexOf(phrase);
    while (i !== -1) {
      ranges.push([i, i + phrase.length]);
      i = text.indexOf(phrase, i + phrase.length);
    }
  }
  ranges.sort((a, b) => a[0] - b[0] || b[1] - a[1]);
  const merged: Array<[number, number]> = [];
  for (const [start, end] of ranges) {
    const last = merged[merged.length - 1];
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  return merged;
}

/**
 * Split text into plain and highlighted segments.
 * Segments are rendered by React as text, never parsed as HTML.
 */
export function toSegments(text: string, phrases: string[]): Segment[] {
  const segments: Segment[] = [];
  let pos = 0;
  for (const [start, end] of highlightRanges(text, phrases)) {
    if (start > pos) segments.push({ text: text.slice(pos, start), marked: false });
    segments.push({ text: text.slice(start, end), marked: true });
    pos = end;
  }
  if (pos < text.length) segments.push({ text: text.slice(pos), marked: false });
  return segments;
}
