import { highlightRanges, toSegments } from "./highlight";

describe("highlightRanges", () => {
  it("finds every occurrence of every phrase", () => {
    expect(highlightRanges("pay now, pay now", ["pay now"])).toEqual([
      [0, 7],
      [9, 16],
    ]);
  });

  it("merges overlapping and adjacent ranges", () => {
    expect(highlightRanges("abcdefgh", ["abcd", "cdef", "fg"])).toEqual([[0, 7]]);
  });

  it("ignores empty and missing phrases", () => {
    expect(highlightRanges("hello", ["", "absent"])).toEqual([]);
  });
});

describe("toSegments", () => {
  it("splits text into plain and marked runs that rebuild the original", () => {
    const text = "Dear candidate, pay Rs. 500 within 24 hours.";
    const segments = toSegments(text, ["pay Rs. 500", "within 24 hours"]);
    expect(segments.map((s) => s.text).join("")).toBe(text);
    expect(segments.filter((s) => s.marked).map((s) => s.text)).toEqual(["pay Rs. 500", "within 24 hours"]);
  });

  it("returns the whole text unmarked when nothing matches", () => {
    expect(toSegments("clean", ["x"])).toEqual([{ text: "clean", marked: false }]);
  });
});
