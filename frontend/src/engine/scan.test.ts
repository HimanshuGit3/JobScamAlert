import { SAMPLES } from "./samples";
import { scanInBrowser } from "./scan";

// Same numbers as the backend's offline run of the samples (README "Sample results").
const EXPECTED: Record<string, { score: number; raw: number; band: string }> = {
  obvious_scam: { score: 100, raw: 120, band: "High Risk" },
  rental_scam: { score: 73, raw: 73, band: "High Risk" },
  subtle_scam: { score: 45, raw: 45, band: "Suspicious" },
  legitimate: { score: 0, raw: 0, band: "Low" },
};

describe("in-browser engine (static build)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  });
  afterEach(() => vi.unstubAllGlobals());

  it.each(SAMPLES.map((s) => [s.id, s.text]))("scores %s like the Python backend", async (id, text) => {
    const report = await scanInBrowser(text, null);
    expect(report.result.score).toBe(EXPECTED[id].score);
    expect(report.result.raw_total).toBe(EXPECTED[id].raw);
    expect(report.result.band).toBe(EXPECTED[id].band);
    for (const h of report.highlights) expect(text).toContain(h);
  });

  it("uses RDAP domain age when available", async () => {
    const registered = new Date(Date.now() - 5 * 86_400_000).toISOString();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ events: [{ eventAction: "registration", eventDate: registered }] })),
      ),
    );
    const report = await scanInBrowser("Apply at https://nexora-hr.co/onboarding", null);
    expect(report.result.breakdown.map((h) => h.id)).toContain("new_domain");
  });

  it("reports server-only checks as skipped and rejects bad URLs", async () => {
    const report = await scanInBrowser("hello", "https://example.com");
    const skipped = report.result.skipped_checks.map((c) => c.check);
    expect(skipped).toEqual(expect.arrayContaining(["Gemini extraction", "Google Safe Browsing", "Linked page content"]));
    await expect(scanInBrowser("", "ftp://x")).rejects.toThrow(/http/);
    await expect(scanInBrowser("  ", null)).rejects.toThrow(/Paste/);
  });
});
