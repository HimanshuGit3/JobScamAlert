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

/** POST /api/scan */
export function scan(text: string, url: string | null): Promise<ScanReport> {
  return request<ScanReport>("/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, url }),
  });
}

/** GET /api/samples */
export function getSamples(): Promise<Sample[]> {
  return request<Sample[]>("/api/samples");
}

/** GET /api/status */
export function getStatus(): Promise<IntegrationStatus> {
  return request<IntegrationStatus>("/api/status");
}
