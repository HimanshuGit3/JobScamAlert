/** Deterministic Scam Threat Index. Mirrors app/scoring.py (same weights, same order). */

import type { RiskBand, ScoreResult, SignalHit, SkippedCheck } from "../types";

export interface ScanFacts {
  payment_demand_evidence: string[];
  untraceable_payment_evidence: string[];
  sensitive_document_evidence: string[];
  urgency_phrases: string[];
  free_email_senders: string[];
  company_domain_mismatch: string[];
  lookalike_domains: string[];
  suspicious_tld_domains: string[];
  shortener_urls: string[];
  insecure_urls: string[];
  domain_ages: Record<string, number>;
  skipped_checks: SkippedCheck[];
}

type ListField = Exclude<keyof ScanFacts, "domain_ages" | "skipped_checks">;

interface Signal {
  id: string;
  label: string;
  points: number;
  explanation: string;
  evaluate: (facts: ScanFacts) => string[];
  maxPoints?: number;
  suppressedBy?: string;
}

const MAX_SCORE = 100;
const MAX_EVIDENCE_ITEMS = 5;

const field =
  (name: ListField) =>
  (facts: ScanFacts): string[] => [...facts[name]];

const domainsByAge =
  (minDays: number, maxDays: number) =>
  (facts: ScanFacts): string[] =>
    Object.entries(facts.domain_ages)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .filter(([, age]) => age >= minDays && age < maxDays)
      .map(([domain, age]) => `${domain} was registered ${age} days ago`);

const none = (): string[] => []; // Gemini-only signals: never fire without the AI backend.

// Gemini-only signals (safe_browsing, no_interview, unrealistic_salary, poor_grammar)
// keep their place so the order and weights match app/scoring.py.
const SIGNALS: Signal[] = [
  { id: "safe_browsing", label: "Flagged by Google Safe Browsing", points: 40, explanation: "Google lists this URL as phishing, malware or unwanted software.", evaluate: none },
  { id: "payment_demand", label: "Asks you to pay money", points: 30, explanation: "Genuine employers and landlords' agents never charge a fee to hire you; registration, training, equipment or 'refundable' deposits are the core of this scam.", evaluate: field("payment_demand_evidence") },
  { id: "new_domain", label: "Domain registered in the last 30 days", points: 25, explanation: "Scam sites are created days before a campaign; real employers use domains that are years old.", evaluate: domainsByAge(0, 30) },
  { id: "young_domain", label: "Domain registered in the last 6 months", points: 12, explanation: "A recently registered domain is unusual for an established employer.", evaluate: domainsByAge(30, 180), suppressedBy: "new_domain" },
  { id: "lookalike_domain", label: "Imitates a well-known employer's domain", points: 25, explanation: "Typosquatted or hyphenated look-alike domains borrow a real brand's trust.", evaluate: field("lookalike_domains") },
  { id: "free_email", label: "Corporate offer sent from a free email account", points: 15, explanation: "Real companies send offers from their own domain, not Gmail, Yahoo or Outlook.", evaluate: field("free_email_senders") },
  { id: "sensitive_documents", label: "Asks for Aadhaar, PAN or bank details early", points: 15, explanation: "Identity and bank documents requested before joining enable identity theft and fraud.", evaluate: field("sensitive_document_evidence") },
  { id: "untraceable_payment", label: "Untraceable payment method", points: 10, explanation: "UPI to a personal ID, gift cards and crypto are hard to reverse and are favoured by fraudsters.", evaluate: field("untraceable_payment_evidence") },
  { id: "domain_mismatch", label: "Company name does not match sender domain", points: 10, explanation: "The sender's domain does not belong to the company named in the letter.", evaluate: field("company_domain_mismatch"), suppressedBy: "free_email" },
  { id: "no_interview", label: "Offer without any interview", points: 10, explanation: "Legitimate jobs involve a selection process; instant offers are bait.", evaluate: none },
  { id: "unrealistic_salary", label: "Unrealistic salary", points: 10, explanation: "Pay far above market rate for the role is used to lower your guard.", evaluate: none },
  { id: "suspicious_tld", label: "Suspicious top-level domain", points: 10, explanation: "Cheap TLDs such as .xyz or .top are heavily abused for phishing.", evaluate: field("suspicious_tld_domains") },
  { id: "urgency", label: "Pressure to act immediately", points: 5, explanation: "Artificial deadlines stop you from verifying the offer.", evaluate: field("urgency_phrases"), maxPoints: 10 },
  { id: "url_shortener", label: "Link hidden behind a URL shortener", points: 8, explanation: "Shorteners hide the real destination of a link.", evaluate: field("shortener_urls") },
  { id: "insecure_url", label: "Link does not use HTTPS", points: 5, explanation: "Official career portals use HTTPS.", evaluate: field("insecure_urls") },
  { id: "poor_grammar", label: "Poor grammar or formatting", points: 5, explanation: "Official HR letters are proofread; sloppy writing is a weak scam indicator.", evaluate: none },
];

export function riskBand(score: number): RiskBand {
  if (score >= 60) return "High Risk";
  if (score >= 30) return "Suspicious";
  return "Low";
}

export function scoreScan(facts: ScanFacts): ScoreResult {
  const evidenceById = new Map<string, string[]>();
  for (const signal of SIGNALS) {
    const evidence = [...new Set(signal.evaluate(facts).filter(Boolean))];
    if (evidence.length) evidenceById.set(signal.id, evidence);
  }
  const breakdown: SignalHit[] = [];
  for (const signal of SIGNALS) {
    const fired = evidenceById.get(signal.id);
    if (!fired || (signal.suppressedBy && evidenceById.has(signal.suppressedBy))) continue;
    breakdown.push({
      id: signal.id,
      signal: signal.label,
      points: signal.maxPoints === undefined ? signal.points : Math.min(signal.points * fired.length, signal.maxPoints),
      evidence: fired.slice(0, MAX_EVIDENCE_ITEMS),
      explanation: signal.explanation,
    });
  }
  breakdown.sort((a, b) => b.points - a.points); // stable, like Python's sort
  const rawTotal = breakdown.reduce((sum, hit) => sum + hit.points, 0);
  const score = Math.min(rawTotal, MAX_SCORE);
  return { score, band: riskBand(score), raw_total: rawTotal, breakdown, skipped_checks: [...facts.skipped_checks] };
}
