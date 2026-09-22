/**
 * In-browser scan pipeline for the static (GitHub Pages) build.
 *
 * Runs the same deterministic checks and scoring as app/pipeline.py, plus live
 * RDAP domain age. Gemini, Safe Browsing and linked-page fetching need a server
 * with secret keys, so they are reported as skipped checks, exactly as the
 * backend does when a key is missing.
 */

import type { ScanReport, SkippedCheck } from "../types";
import { FREE_EMAIL_PROVIDERS, KNOWN_BRANDS, URL_SHORTENERS } from "./data";
import * as dom from "./domains";
import { MAX_RDAP_LOOKUPS, checkDomainAges } from "./rdap";
import { scoreScan, type ScanFacts } from "./scoring";
import * as tp from "./textParse";

const MAX_HIGHLIGHTS = 30;
const SERVER_ONLY = "needs the server version (Cloud Run); not available in the static GitHub Pages demo";

interface ParsedInput {
  text: string;
  urls: string[];
  emails: string[];
  domains: string[];
}

function parseInput(text: string, submittedUrl: string | null): ParsedInput {
  const urls = [...(submittedUrl ? [submittedUrl] : []), ...tp.extractUrls(text)];
  const emails = tp.extractEmails(text);
  const hosts = [...urls.map(dom.hostOf), ...emails.map(dom.emailDomain)];
  const domains = hosts
    .filter((h): h is string => Boolean(h))
    .map(dom.registrableDomain)
    .filter((d): d is string => Boolean(d));
  return { text, urls: tp.dedupe(urls), emails: tp.dedupe(emails), domains: tp.dedupe(domains) };
}

function rdapTargets(parsed: ParsedInput): string[] {
  return parsed.domains
    .filter(
      (d) =>
        !FREE_EMAIL_PROVIDERS.has(d) &&
        !URL_SHORTENERS.has(d) &&
        !KNOWN_BRANDS.some((b) => dom.isOfficialDomain(d, b)),
    )
    .slice(0, MAX_RDAP_LOOKUPS);
}

export async function scanInBrowser(rawText: string, rawUrl: string | null): Promise<ScanReport> {
  const text = rawText.trim();
  const url = rawUrl?.trim() || null;
  if (!text && !url) throw new Error("Paste the offer text or enter a URL");
  if (url && (!/^https?:\/\//i.test(url) || /\s/.test(url))) {
    throw new Error("URL must start with http:// or https:// and contain no spaces");
  }

  const parsed = parseInput(text, url);
  const [domainAges, rdapSkipped] = await checkDomainAges(rdapTargets(parsed));

  const skipped: SkippedCheck[] = [];
  if (url) skipped.push({ check: "Linked page content", reason: SERVER_ONLY });
  if (text) skipped.push({ check: "Gemini extraction", reason: SERVER_ONLY });
  skipped.push({ check: "Google Safe Browsing", reason: SERVER_ONLY }, ...rdapSkipped);

  const facts: ScanFacts = {
    payment_demand_evidence: tp.detectPaymentDemands(text),
    untraceable_payment_evidence: tp.detectUntraceablePayment(text),
    sensitive_document_evidence: tp.detectSensitiveDocumentRequests(text),
    urgency_phrases: tp.detectUrgency(text),
    free_email_senders: dom.findFreeEmailSenders(parsed.emails),
    company_domain_mismatch: dom.findCompanyDomainMismatch(null, text, parsed.emails),
    lookalike_domains: dom.findLookalikeDomains(parsed.domains),
    suspicious_tld_domains: dom.findSuspiciousTlds(parsed.domains),
    shortener_urls: dom.findShorteners(parsed.urls),
    insecure_urls: dom.findInsecureUrls(parsed.urls),
    domain_ages: domainAges,
    skipped_checks: skipped,
  };

  const candidates = [
    ...facts.payment_demand_evidence,
    ...facts.untraceable_payment_evidence,
    ...facts.sensitive_document_evidence,
    ...facts.urgency_phrases,
  ];
  return {
    result: scoreScan(facts),
    analyzed_text: text,
    highlights: [...new Set(candidates)].filter((c) => c && text.includes(c)).slice(0, MAX_HIGHLIGHTS),
    company_name: null,
    urls: parsed.urls,
    emails: parsed.emails,
    ai_extraction_used: false,
  };
}
