import type { IntegrationStatus, Sample, ScanReport } from "./types";

/** An API failure with a message that is safe and friendly to show users. */
export class ApiError extends Error {}

async function errorMessage(response: Response): Promise<string> {
  if (response.status === 429) return "Too many scans from your network. Please wait a minute and try again.";
  if (response.status === 413) return "That text is too long to scan.";
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (Array.isArray(detail) && typeof detail[0]?.msg === "string") {
        return detail[0].msg.replace(/^Value error, /, "");
      }
      if (typeof detail === "string") return detail;
    }
  } catch {
    /* fall through to the generic message */
  }
  return "The scan failed. Please try again.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("Network error. Check your connection and try again.");
  }
  if (!response.ok) throw new ApiError(await errorMessage(response));
  return (await response.json()) as T;
}

/**
 * Static build (GitHub Pages, `VITE_STATIC_MODE=true`): there is no backend, so the
 * deterministic engine runs in the browser. It is loaded lazily, so the server
 * build never downloads it.
 */
const STATIC_MODE = import.meta.env.VITE_STATIC_MODE === "true";

/** POST /api/scan */
export async function scan(text: string, url: string | null): Promise<ScanReport> {
  if (STATIC_MODE) {
    const { scanInBrowser } = await import("./engine/scan");
    try {
      return await scanInBrowser(text, url);
    } catch (error) {
      throw new ApiError(error instanceof Error ? error.message : "The scan failed. Please try again.");
    }
  }
  return request<ScanReport>("/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, url }),
  });
}

/** GET /api/samples */
export async function getSamples(): Promise<Sample[]> {
  if (STATIC_MODE) return (await import("./engine/samples")).SAMPLES;
  return request<Sample[]>("/api/samples");
}

/** GET /api/status */
export async function getStatus(): Promise<IntegrationStatus> {
  if (STATIC_MODE) return { gemini: false, safe_browsing: false, model: "", fetch_linked_pages: false };
  return request<IntegrationStatus>("/api/status");
}
