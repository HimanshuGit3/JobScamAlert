/** Domain age via RDAP from the browser (rdap.org and registries send CORS headers). Mirrors app/checks/rdap.py. */

import type { SkippedCheck } from "../types";

const RDAP_BASE_URL = "https://rdap.org/domain/";
const RDAP_TIMEOUT_MS = 8000;
export const MAX_RDAP_LOOKUPS = 5;
const DOMAIN_RE = /^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$/;
const DAY_MS = 86_400_000;

class RdapError extends Error {}

function normalizeDomain(domain: string): string {
  let ascii: string;
  try {
    ascii = new URL(`http://${domain.trim().replace(/\.+$/, "")}`).hostname.toLowerCase(); // IDNA-encodes
  } catch {
    throw new RdapError(`invalid domain '${domain}'`);
  }
  if (!DOMAIN_RE.test(ascii)) throw new RdapError(`invalid domain '${domain}'`);
  return ascii;
}

interface RdapEvent {
  eventAction?: string;
  eventDate?: string;
}

async function fetchDomainAge(domain: string, now: number): Promise<number> {
  const safeDomain = normalizeDomain(domain);
  let response: Response;
  try {
    response = await fetch(RDAP_BASE_URL + safeDomain, {
      headers: { Accept: "application/rdap+json" },
      signal: AbortSignal.timeout(RDAP_TIMEOUT_MS),
      referrerPolicy: "no-referrer",
    });
  } catch (error) {
    throw new RdapError(`network error: ${error instanceof Error ? error.name : "unknown"}`);
  }
  if (response.status === 404) throw new RdapError("no RDAP record (domain unregistered or TLD has no RDAP service)");
  if (!response.ok) throw new RdapError(`RDAP returned HTTP ${response.status}`);
  let events: RdapEvent[];
  try {
    events = ((await response.json()) as { events?: RdapEvent[] }).events ?? [];
  } catch {
    throw new RdapError("unparseable RDAP response");
  }
  const registration = events.find((e) => e.eventAction === "registration" && e.eventDate);
  if (!registration?.eventDate) throw new RdapError("no registration event in RDAP response");
  const registered = Date.parse(registration.eventDate);
  if (Number.isNaN(registered)) throw new RdapError("unparseable RDAP response");
  return Math.max(Math.floor((now - registered) / DAY_MS), 0);
}

/** Look up several domains concurrently; failures become skipped checks. */
export async function checkDomainAges(
  domains: string[],
  now: number = Date.now(),
): Promise<[Record<string, number>, SkippedCheck[]]> {
  const targets = domains.slice(0, MAX_RDAP_LOOKUPS);
  const results = await Promise.allSettled(targets.map((d) => fetchDomainAge(d, now)));
  const ages: Record<string, number> = {};
  const skipped: SkippedCheck[] = [];
  results.forEach((result, i) => {
    if (result.status === "fulfilled") ages[targets[i]] = result.value;
    else
      skipped.push({
        check: `Domain age (${targets[i]})`,
        reason: result.reason instanceof RdapError ? result.reason.message : "unexpected error",
      });
  });
  return [ages, skipped];
}
