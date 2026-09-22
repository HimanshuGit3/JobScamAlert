/** Offline domain and URL heuristics. Mirrors app/checks/domains.py. */

import {
  COMPANY_STOPWORDS,
  FREE_EMAIL_PROVIDERS,
  KNOWN_BRANDS,
  MULTI_PART_SUFFIXES,
  SUSPICIOUS_TLDS,
  URL_SHORTENERS,
  type Brand,
} from "./data";

const HOMOGLYPHS: Record<string, string> = { "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", $: "s" };
const SHORT_TOKEN_LEN = 5;
const PRODUCT_MENTION_RE =
  /\b(?:google\s+(?:meet|pay|play|forms?|drive|docs|maps|chrome)|gmail|microsoft\s+(?:teams|word|excel|office|forms)|amazon\s+pay|paytm\s+(?:app|wallet)|jio\s*(?:meet|sim))\b/gi;
const IPV4_RE = /^\d{1,3}(?:\.\d{1,3}){3}$/;

/** Lower-case host of a URL; scheme-less input is allowed. */
export function hostOf(url: string): string | null {
  const candidate = url.includes("://") ? url : `http://${url}`;
  try {
    const host = new URL(candidate).hostname;
    return host ? host.replace(/\.+$/, "").toLowerCase() : null;
  } catch {
    return null;
  }
}

/** `a.b.tcs.com` -> `tcs.com`; null for IPs and single-label hosts. */
export function registrableDomain(host: string): string | null {
  const clean = host.replace(/\.+$/, "").toLowerCase();
  if (IPV4_RE.test(clean) || clean.includes(":")) return null;
  const labels = clean.split(".");
  if (labels.length < 2) return null;
  const take = MULTI_PART_SUFFIXES.has(labels.slice(-2).join(".")) && labels.length >= 3 ? 3 : 2;
  return labels.slice(-take).join(".");
}

const tldOf = (domain: string): string => domain.split(".").pop() ?? domain;
export const emailDomain = (email: string): string => (email.split("@").pop() ?? "").toLowerCase();
const labelOf = (domain: string): string => domain.split(".")[0];

export function levenshtein(a: string, b: string): number {
  if (a.length < b.length) [a, b] = [b, a];
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const current = [i];
    for (let j = 1; j <= b.length; j++) {
      current.push(Math.min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)));
    }
    previous = current;
  }
  return previous[previous.length - 1];
}

export const isOfficialDomain = (domain: string, brand: Brand): boolean =>
  brand.domains.some((d) => domain === d || domain.endsWith(`.${d}`));

const isOfficialAnywhere = (domain: string): boolean => KNOWN_BRANDS.some((b) => isOfficialDomain(domain, b));

function imitates(label: string, token: string): boolean {
  if (label.split("-").includes(token)) return true;
  const compact = label.replace(/-/g, "");
  if (token.length > SHORT_TOKEN_LEN && compact.includes(token)) return true;
  const deglyphed = [...compact].map((c) => HOMOGLYPHS[c] ?? c).join("");
  if (deglyphed === token || (token.length > SHORT_TOKEN_LEN && deglyphed.includes(token))) return true;
  if (token.length >= SHORT_TOKEN_LEN) {
    const allowed = token.length >= 8 ? 2 : 1;
    // Edit distance is at least the length gap: skip the O(n*m) DP when it can't match.
    if (Math.abs(compact.length - token.length) > allowed) return false;
    const distance = levenshtein(compact, token);
    return distance > 0 && distance <= allowed;
  }
  return false;
}

export function findLookalikeDomains(domains: string[]): string[] {
  const hits: string[] = [];
  for (const domain of domains) {
    if (isOfficialAnywhere(domain) || FREE_EMAIL_PROVIDERS.has(domain)) continue;
    const label = labelOf(domain);
    const brand = KNOWN_BRANDS.find((b) => b.tokens.some((t) => imitates(label, t)));
    if (brand) hits.push(`${domain} imitates ${brand.name} (official: ${brand.domains.join(", ")})`);
  }
  return hits;
}

export const findFreeEmailSenders = (emails: string[]): string[] =>
  emails
    .filter((e) => FREE_EMAIL_PROVIDERS.has(emailDomain(e)))
    .map((e) => `${e} uses free provider ${emailDomain(e)}`);

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// One whole-word pattern per brand, compiled once at load.
const BRAND_ALIAS_RES: [Brand, RegExp][] = KNOWN_BRANDS.map((b) => [
  b,
  new RegExp(`\\b(?:${b.aliases.map(escapeRegExp).join("|")})\\b`),
]);

function brandsMentioned(text: string): Brand[] {
  const lowered = text.toLowerCase();
  return BRAND_ALIAS_RES.filter(([, re]) => re.test(lowered)).map(([b]) => b);
}

function claimedBrands(companyName: string | null, text: string): Brand[] {
  if (companyName) return brandsMentioned(companyName);
  return brandsMentioned(text.replace(PRODUCT_MENTION_RE, " "));
}

function nameMatchesDomain(company: string, domain: string): boolean {
  const label = labelOf(domain).replace(/-/g, "");
  const allWords = company.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  if (allWords.some((w) => !COMPANY_STOPWORDS.has(w) && w.length >= 3 && label.includes(w))) return true;
  const acronym = allWords
    .filter((w) => !["pvt", "ltd", "private", "limited"].includes(w))
    .map((w) => w[0])
    .join("");
  return acronym.length >= 2 && label.includes(acronym);
}

export function findCompanyDomainMismatch(companyName: string | null, text: string, senderEmails: string[]): string[] {
  const senderDomains = [
    ...new Set(senderEmails.map((e) => registrableDomain(emailDomain(e)) ?? emailDomain(e))),
  ];
  if (senderDomains.length === 0) return [];
  const hits: string[] = [];
  const brands = claimedBrands(companyName, text);
  for (const brand of brands) {
    if (!senderDomains.some((d) => isOfficialDomain(d, brand))) {
      hits.push(`Letter mentions ${brand.name} but emails come from ${senderDomains.join(", ")}`);
    }
  }
  if (companyName && brands.length === 0 && !senderDomains.some((d) => nameMatchesDomain(companyName, d))) {
    hits.push(`Company '${companyName}' does not match sender domain(s) ${senderDomains.join(", ")}`);
  }
  return hits;
}

export const findSuspiciousTlds = (domains: string[]): string[] =>
  domains.filter((d) => SUSPICIOUS_TLDS.has(tldOf(d))).map((d) => `${d} (.${tldOf(d)})`);

export const findShorteners = (urls: string[]): string[] => urls.filter((u) => URL_SHORTENERS.has(hostOf(u) ?? ""));

export const findInsecureUrls = (urls: string[]): string[] => urls.filter((u) => u.toLowerCase().startsWith("http://"));
