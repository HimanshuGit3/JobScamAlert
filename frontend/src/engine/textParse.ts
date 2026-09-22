/** Regex parsing of offer text. Mirrors app/checks/text_parse.py. */

import { BARE_DOMAIN_TLDS } from "./data";

export const MAX_ITEMS = 20;
const MAX_EVIDENCE_CHARS = 300;

const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}/g;
const URL_RE = /\bhttps?:\/\/[^\s<>"'`{}|\\^]+/gi;
const BARE_DOMAIN_RE =
  /(?<![@\w.-])(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z]{2,24})(?:\/[^\s<>"'`]*)?(?![\w@-])/gi;
const TRAILING_PUNCT_RE = /[.,;:!?)\]}'"]+$/;
const SENTENCE_SPLIT_RE = /(?<=[.!?])\s+(?=[A-Z"'(])|\s*\n\s*/;

const PAYMENT_FEE_RE = new RegExp(
  "\\b(?:registration|processing|training|verification|onboarding|joining|" +
    "application|documentation|kit|uniform|laptop|equipment|interview|" +
    "background[- ]check|security|caution|refundable)\\s+" +
    "(?:fee|fees|charges?|deposit|amount|money)\\b" +
    "|\\bsecurity\\s+deposit\\b|\\bcaution\\s+money\\b|\\brefundable\\b",
  "i",
);
const PAYMENT_ACTION_RE = new RegExp(
  "\\b(?:pay|deposit|transfer|remit|send)\\s+(?:[\\w,.'-]+\\s+){0,4}?" +
    "(?:amount|sum|fees?|charges?|deposit|advance|₹\\s*\\d|rs\\.?\\s*\\d|inr\\s*\\d|rupees)",
  "i",
);
const UPI_ID_RE = new RegExp(
  "\\b[a-z0-9._-]{2,64}@(?:ybl|okaxis|oksbi|okhdfcbank|okicici|paytm|upi|apl|" +
    "ibl|axl|ptyes|ptsbi|ptaxis|pthdfc|icici|sbi|hdfcbank|axisbank|kotak|" +
    "yesbank|ikwik|fbl|freecharge|jio|airtel|axisb)(?![\\w.-]*\\.[a-z])\\b",
  "i",
);
const UNTRACEABLE_METHOD_RE = new RegExp(
  "\\bgift\\s*cards?\\b|\\b(?:google\\s+play|amazon\\s+pay|itunes)\\s+(?:gift\\s+)?(?:card|voucher)s?\\b" +
    "|\\b(?:bitcoin|btc|usdt|ethereum|crypto(?:currency)?)\\b" +
    "|\\b(?:via|through|using|on|to)\\s+(?:upi|phonepe|gpay|google\\s+pay|paytm)\\b",
  "i",
);
const SENSITIVE_DOC_RE = new RegExp(
  "\\b(?:aadh?aar|pan\\s+(?:card|number|no\\.?)|bank\\s+(?:account|details|statement)|" +
    "account\\s+number|ifsc|passbook|cancell?ed\\s+cheque|debit\\s+card|credit\\s+card|" +
    "passport)\\b",
  "i",
);
const ALWAYS_SENSITIVE_RE = /\b(?:otp|cvv|atm\s+pin|upi\s+pin|net\s*banking\s+password)\b/i;
const REQUEST_VERB_RE = /\b(?:send|share|submit|provide|upload|forward|whatsapp|e-?mail)\b/i;
const AT_JOINING_RE =
  /\b(?:on|at the time of|during|upon)\s+(?:the\s+)?(?:day\s+of\s+)?(?:your\s+)?(?:joining|first day|induction)\b/i;
const URGENCY_RE = new RegExp(
  "\\bwithin\\s+(?:\\d{1,2}|twenty[- ]four|forty[- ]eight)\\s*(?:hours?|hrs?)\\b" +
    "|\\b(?:urgent(?:ly)?|asap|today\\s+itself|act\\s+now|immediate\\s+(?:payment|action))\\b" +
    "|\\blimited\\s+(?:seats|slots|positions|vacancies)\\b" +
    "|\\bonly\\s+\\d+\\s+(?:seats|slots|positions)\\s+(?:left|remaining)\\b" +
    "|\\b(?:offer|seat|selection)\\s+(?:will|shall)\\s+be\\s+(?:cancell?ed|withdrawn|revoked|forfeited)\\b" +
    "|\\bfailing\\s+which\\b",
  "gi",
);

/** Remove duplicates, keep order, cap length. */
export function dedupe<T>(items: T[], limit: number = MAX_ITEMS): T[] {
  return [...new Set(items)].slice(0, limit);
}

const stripTrailing = (value: string): string => value.replace(TRAILING_PUNCT_RE, "");

let cachedText: string | null = null;
let cachedSentences: string[] = [];

/** Split text into sentences; every item is a substring of `text`. Memoised for the
 *  last text, since three detectors read the same text in one scan. */
export function splitSentences(text: string): string[] {
  if (text !== cachedText) {
    cachedSentences = text
      .split(SENTENCE_SPLIT_RE)
      .map((s) => s.trim())
      .filter(Boolean);
    cachedText = text;
  }
  return cachedSentences;
}

export function extractEmails(text: string): string[] {
  return dedupe([...text.matchAll(EMAIL_RE)].map((m) => m[0].toLowerCase()));
}

/** URLs plus bare domains with a known TLD (so "offer.pdf" is not a site). */
export function extractUrls(text: string): string[] {
  const urls = [...text.matchAll(URL_RE)].map((m) => stripTrailing(m[0]));
  const remainder = text.replace(EMAIL_RE, " ").replace(URL_RE, " ");
  for (const match of remainder.matchAll(BARE_DOMAIN_RE)) {
    if (BARE_DOMAIN_TLDS.has(match[1].toLowerCase())) urls.push(stripTrailing(match[0]));
  }
  return dedupe(urls);
}

function matchingSentences(text: string, ...patterns: RegExp[]): string[] {
  return dedupe(
    splitSentences(text)
      .filter((s) => patterns.some((p) => p.test(s)))
      .map((s) => s.slice(0, MAX_EVIDENCE_CHARS)),
  );
}

export const detectPaymentDemands = (text: string): string[] =>
  matchingSentences(text, PAYMENT_FEE_RE, PAYMENT_ACTION_RE);

export const detectUntraceablePayment = (text: string): string[] =>
  matchingSentences(text, UPI_ID_RE, UNTRACEABLE_METHOD_RE);

/** Identity/bank document requests before joining; OTP/CVV/PIN always count. */
export function detectSensitiveDocumentRequests(text: string): string[] {
  return dedupe(
    splitSentences(text)
      .filter(
        (s) =>
          ALWAYS_SENSITIVE_RE.test(s) ||
          (SENSITIVE_DOC_RE.test(s) && REQUEST_VERB_RE.test(s) && !AT_JOINING_RE.test(s)),
      )
      .map((s) => s.slice(0, MAX_EVIDENCE_CHARS)),
  );
}

export function detectUrgency(text: string): string[] {
  return dedupe([...text.matchAll(URGENCY_RE)].map((m) => m[0]));
}
