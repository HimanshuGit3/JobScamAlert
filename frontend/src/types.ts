/** Types mirroring the FastAPI response models (app/models.py, app/pipeline.py). */

export type RiskBand = "Low" | "Suspicious" | "High Risk";

export interface SignalHit {
  id: string;
  signal: string;
  points: number;
  evidence: string[];
  explanation: string;
}

export interface SkippedCheck {
  check: string;
  reason: string;
}

export interface ScoreResult {
  score: number;
  band: RiskBand;
  raw_total: number;
  breakdown: SignalHit[];
  skipped_checks: SkippedCheck[];
}

export interface ScanReport {
  result: ScoreResult;
  analyzed_text: string;
  highlights: string[];
  company_name: string | null;
  urls: string[];
  emails: string[];
  ai_extraction_used: boolean;
}

export interface Sample {
  id: string;
  title: string;
  text: string;
}

export interface IntegrationStatus {
  gemini: boolean;
  safe_browsing: boolean;
  model: string;
  fetch_linked_pages: boolean;
}
