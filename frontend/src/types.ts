export type Weights = Record<string, number>;
export interface Requirement { id: string; name: string; category: string; importance: "must" | "preferred" | "ignored"; weight: number; custom?: boolean; any_of?: string[] }
export interface Job {
  id: number; title: string; role: string | null; category: string; description: string; min_experience_years: number;
  preferred_experience_years: number | null; education_level: number; preferred_education_level: number | null;
  requirements: Requirement[]; analysis: any; is_template: boolean; created_at: string; updated_at: string;
}
export interface Paged<T> { total: number; page: number; page_size: number; items: T[] }
export interface RunInfo {
  run_id: number; job_id: number; created_at: string; algorithm_version: string; similarity_method: string; model_name: string;
  fallback_reason: string | null; weights: Weights; as_of: string; n_candidates: number; duration_ms: number; default_weights?: Weights;
}
export interface Component { score: number | null; status: string; weight_configured: number; weight_effective: number; contribution: number }
export interface ReqResult {
  requirement_id: string; name: string; category: string; importance: string; weight: number; match_type: "exact" | "synonym" | "partial" | "semantic" | "none";
  credit: number; similarity: number | null; evidence_text: string | null; page: number | null; section: string | null; verification: string;
  note: string; related_found: string[] | null; any_of?: string[] | null; satisfied_by?: string | null;
}
export interface ResultRow {
  candidate_id: number; result_id: number; rank: number; name: string; email: string | null; latest_role: string | null;
  overall: number; score_low: number; score_high: number; skill_coverage: number; must_have_coverage: number;
  components: Record<string, Component>; relevant_years: number; total_years: number; confidence: number; completeness: number;
  review_status: string; parse_status: string; requirements: ReqResult[]; matched_skills: string[]; related_skills: string[];
  semantic_skills: string[]; missing_skills: string[]; candidate_skills: string[]; sensitivity: { rank_min: number; rank_max: number; stable: boolean; scenarios: number };
  override: any; needs_review: boolean;
  role_source: "job" | "headline" | "none"; employment_count: number; claimed_years: number | null;
  parse_review: { needs_review: boolean; codes?: string[]; reasons: string[] };
}
export interface ResultsResponse {
  job: { id: number; title: string }; run: RunInfo; total: number; page: number; page_size: number; items: ResultRow[];
  summary: { total_ranked: number; average_score: number; high_matching: number; needs_review: number; high_threshold: number };
  pool: Pool;
}
export interface Pool {
  files_received: number; stored: number; parsed: number; failed: number; duplicates_skipped: number;
  ranked_in_run: number; not_in_run: number; run_is_stale: boolean;
}
export interface Accounting extends Pool { duplicates: { skipped_at: string; identical_to_resume_id: number; identical_to_filename: string | null }[] }
export interface Evidence { requirement_id: string; requirement: string; category: string; match_type: string; text: string | null; page: number | null; similarity: number | null; verification: string }
export interface Field { value: string | null; page: number | null; evidence: string | null; method: string; confidence: number; status: string }
export interface CandidateDetail {
  candidate: {
    id: number; name: string; fields: Record<string, Field>; review_status: string; employment: any[]; education: any[]; projects: any[];
    certifications: any[]; skills: any[]; parse_confidence: number; protected_lines_removed: number; injection_flags: any[];
    diagnostics: any; file: { filename: string; pages: number }; notes: { id: number; text: string; created_at: string }[];
  };
  result: ResultRow & { run: RunInfo; experience: any; education: any; projects: any; semantic: any; evidence: Evidence[]; overrides: any[];
    explanation: { headline: string; summary: string; why_matched: string[]; why_not_matched: string[]; missing_information: string[]; component_effects: any[]; evidence_supporting_score: { requirement: string; text: string; page: number | null }[]; disclaimer: string } };
}
export interface UploadItem { filename: string; status: string; needs_review?: boolean; review_reasons?: string[]; error_code?: string; error_message?: string; resume_id?: number; candidate_id?: number; possible_duplicate_of?: number; warnings?: string[] }
export interface UploadResponse { batch_id: string; total: number; summary: Record<string, number>; results: UploadItem[] }
export interface ResumeRow { id: number; batch_id: string; filename: string; file_type: string; file_size: number; status: string; error_code: string | null; error_message: string | null; page_count: number | null; candidate_id: number | null; processing_ms: number | null; created_at: string; diagnostics: any }
export interface WhatIfResponse { original_run_id: number; weights: Weights; persisted: boolean; note: string; rows: { candidate_id: number; name: string; original_rank: number; simulated_rank: number; rank_change: number; original_score: number; simulated_score: number; score_change: number }[] }
export interface Settings { algorithm_version: string; default_weights: Weights; component_labels: Record<string, string>; components: string[]; max_upload_mb: number; max_batch_files: number; retention_days: number; store_original_files: boolean; embedding_backend: string; ontology: { version: string; skills: number }; formula: string }

export interface Interview {
  id: number; candidate_id: number; job_id: number | null; round: string; interviewer: string; interviewed_on: string | null;
  recommendation: string; ratings: Record<string, number>; rating_avg: number | null; strengths: string; concerns: string; notes: string;
  created_at: string; updated_at: string;
}
export interface InterviewSummary {
  count: number; avg_rating: number | null; avg_by_criterion: Record<string, number | null>; recommendations: Record<string, number>;
}
export interface InterviewsResponse { items: Interview[]; summary: InterviewSummary }
