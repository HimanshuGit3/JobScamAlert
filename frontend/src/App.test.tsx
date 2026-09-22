import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { App, validateInput } from "./App";
import type { IntegrationStatus, Sample, ScanReport } from "./types";

const XSS = '<img src=x onerror="alert(1)">';

const SAMPLES: Sample[] = [{ id: "obvious_scam", title: "Obvious scam", text: "Pay the registration fee now." }];
const STATUS: IntegrationStatus = { gemini: false, safe_browsing: true, model: "m", fetch_linked_pages: true };

function report(text: string): ScanReport {
  return {
    result: {
      score: 85,
      band: "High Risk",
      raw_total: 95,
      breakdown: [
        {
          id: "payment_demand",
          signal: "Asks you to pay money",
          points: 30,
          evidence: ["Pay the registration fee now."],
          explanation: "Real employers never charge a fee.",
        },
      ],
      skipped_checks: [{ check: "Gemini extraction", reason: "GEMINI_API_KEY is not configured" }],
    },
    analyzed_text: text,
    highlights: ["Pay the registration fee now."],
    company_name: null,
    urls: [],
    emails: [],
    ai_extraction_used: false,
  };
}

function mockApi(scanResponse: (body: { text: string }) => Response) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/samples") return Response.json(SAMPLES);
    if (url === "/api/status") return Response.json(STATUS);
    if (url === "/api/scan") return scanResponse(JSON.parse(String(init?.body)));
    return new Response(null, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("validateInput", () => {
  it("requires text or a URL", () => {
    expect(validateInput("", "")).toMatch(/Paste the offer text/);
  });
  it("rejects non-http links", () => {
    expect(validateInput("", "javascript:alert(1)")).toMatch(/http/);
  });
  it("accepts text alone", () => {
    expect(validateInput("hello", "")).toBeNull();
  });
});

describe("App", () => {
  it("loads samples and shows which integrations are on", async () => {
    mockApi(() => Response.json({}));
    render(<App />);
    expect(await screen.findByRole("button", { name: /Obvious scam/ })).toBeInTheDocument();
    const pills = screen.getByRole("list", { name: "Checks available" });
    expect(within(pills).getByText(/Gemini AI/)).toHaveTextContent("Gemini AI: off");
    expect(within(pills).getByText(/Safe Browsing/)).toHaveTextContent("Safe Browsing: on");
  });

  it("shows an accessible error for an empty submission without calling the API", async () => {
    const fetchMock = mockApi(() => Response.json({}));
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Scan for scam signals/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Paste the offer text");
    expect(fetchMock).not.toHaveBeenCalledWith("/api/scan", expect.anything());
  });

  it("scans, announces the result, moves focus and renders the breakdown", async () => {
    mockApi(({ text }) => Response.json(report(text)));
    render(<App />);
    await userEvent.type(screen.getByLabelText(/Offer letter, email or message text/), "Pay the registration fee now.");
    await userEvent.click(screen.getByRole("button", { name: /Scan for scam signals/ }));

    const heading = await screen.findByRole("heading", { name: /Scan result/ });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByRole("status")).toHaveTextContent("Scam Threat Index 85 out of 100, High Risk");
    expect(screen.getByRole("img", { name: "Scam Threat Index 85 out of 100: High Risk" })).toBeInTheDocument();
    expect(screen.getByText("Asks you to pay money")).toBeInTheDocument();
    expect(screen.getByText(/GEMINI_API_KEY is not configured/)).toBeInTheDocument();
    expect(document.querySelector("mark.hl")).toHaveTextContent("Pay the registration fee now.");
  });

  it("renders pasted HTML as inert text, never as markup", async () => {
    mockApi(({ text }) => Response.json({ ...report(text), highlights: [XSS] }));
    render(<App />);
    const box = screen.getByLabelText(/Offer letter, email or message text/);
    await userEvent.click(box);
    await userEvent.paste(XSS);
    await userEvent.click(screen.getByRole("button", { name: /Scan for scam signals/ }));

    await screen.findByRole("heading", { name: /Scan result/ });
    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByLabelText("Analysed text with suspicious parts highlighted")).toHaveTextContent(XSS);
  });

  it("shows results immediately and again on every later scan (regression)", async () => {
    let calls = 0;
    mockApi(({ text }) => {
      calls += 1;
      return Response.json({ ...report(text), result: { ...report(text).result, score: calls === 1 ? 85 : 40, band: calls === 1 ? "High Risk" : "Suspicious" } });
    });
    render(<App />);
    const box = screen.getByLabelText(/Offer letter, email or message text/);
    await userEvent.type(box, "first letter");
    await userEvent.click(screen.getByRole("button", { name: /Scan for scam signals/ }));
    expect(await screen.findByRole("img", { name: /85 out of 100/ })).toBeInTheDocument();

    // The user edits the text and scans again: new results must replace the old ones.
    await userEvent.clear(box);
    await userEvent.type(box, "my own second letter");
    await userEvent.click(screen.getByRole("button", { name: /Scan for scam signals/ }));
    expect(await screen.findByRole("img", { name: /40 out of 100: Suspicious/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Scan in progress")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: /Scan result/ })).toHaveLength(1);
  });

  it("scans the user's own text after they edit a sample", async () => {
    const fetchMock = mockApi(({ text }) => Response.json(report(text)));
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: /Obvious scam/ }));
    await screen.findByRole("heading", { name: /Scan result/ });
    const box = screen.getByLabelText(/Offer letter, email or message text/);
    await userEvent.clear(box);
    await userEvent.type(box, "typed by me");
    await userEvent.click(screen.getByRole("button", { name: /Scan for scam signals/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith("/api/scan", expect.objectContaining({ body: JSON.stringify({ text: "typed by me", url: null }) })),
    );
  });

  it("shows the server's rate-limit message", async () => {
    mockApi(() => new Response("{}", { status: 429 }));
    render(<App />);
    await userEvent.type(screen.getByLabelText(/Offer letter, email or message text/), "hello");
    await userEvent.click(screen.getByRole("button", { name: /Scan for scam signals/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Too many scans/);
  });

  it("toggles signal evidence with aria-expanded", async () => {
    mockApi(({ text }) => Response.json(report(text)));
    render(<App />);
    await userEvent.type(screen.getByLabelText(/Offer letter, email or message text/), "x");
    await userEvent.click(screen.getByRole("button", { name: /Scan for scam signals/ }));
    const toggle = await screen.findByRole("button", { name: /Hide evidence/ });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(toggle);
    expect(screen.getByRole("button", { name: /Show evidence \(1\)/ })).toHaveAttribute("aria-expanded", "false");
  });
});
