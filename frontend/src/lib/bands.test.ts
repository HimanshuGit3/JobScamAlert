import { BANDS, bandForScore } from "./bands";

describe("bandForScore mirrors app/scoring.py thresholds", () => {
  it.each([
    [0, "Low"],
    [29, "Low"],
    [30, "Suspicious"],
    [59, "Suspicious"],
    [60, "High Risk"],
    [100, "High Risk"],
  ] as const)("%i -> %s", (score, band) => {
    expect(bandForScore(score)).toBe(band);
  });

  it("has copy for every band", () => {
    for (const info of Object.values(BANDS)) {
      expect(info.headline).not.toBe("");
      expect(info.advice).not.toBe("");
    }
  });
});
