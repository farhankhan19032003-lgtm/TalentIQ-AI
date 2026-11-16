export const COMP_LABEL: Record<string, string> = {
  technical_skills: "Technical skills", semantic_relevance: "Semantic relevance", relevant_experience: "Relevant experience",
  education: "Education", project_domain: "Projects & domain",
};
export const fmt = (n: number | null | undefined, d = 1) => (n === null || n === undefined ? "—" : n.toFixed(d));

/** Colour band for a 0-100 match score (decision-support, not a verdict). */
export function scoreTone(s: number): "high" | "mid" | "low" { return s >= 70 ? "high" : s >= 50 ? "mid" : "low"; }
export const TONE_CLASS = {
  high: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200",
  mid: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-200",
  low: "bg-slate-100 text-slate-600 ring-1 ring-inset ring-slate-200",
};

export const MATCH_LABEL: Record<string, string> = { exact: "Exact", synonym: "Synonym", partial: "Related (partial)", semantic: "Semantic only", none: "No evidence" };
export const MATCH_CLASS: Record<string, string> = {
  exact: "bg-emerald-100 text-emerald-800", synonym: "bg-emerald-50 text-emerald-700", partial: "bg-amber-100 text-amber-800",
  semantic: "bg-sky-100 text-sky-800", none: "bg-red-50 text-red-700",
};
export const STATUSES = ["new", "reviewed", "shortlisted", "interview", "on_hold", "not_progressing"];
export const STATUS_LABEL: Record<string, string> = { new: "New", reviewed: "Reviewed", in_review: "Reviewed", shortlisted: "Shortlisted", interview: "Interview", on_hold: "On hold", not_progressing: "Not progressing" };

/** Recruiter pipeline stages, in board order. `dot` is the stage colour. */
export const PIPELINE_STAGES = [
  { id: "new", label: "New", dot: "bg-slate-400" },
  { id: "reviewed", label: "Reviewed", dot: "bg-sky-500" },
  { id: "shortlisted", label: "Shortlisted", dot: "bg-emerald-500" },
  { id: "interview", label: "Interview", dot: "bg-violet-500" },
  { id: "on_hold", label: "On hold", dot: "bg-amber-500" },
  { id: "not_progressing", label: "Not progressing", dot: "bg-rose-400" },
] as const;

/** The legacy backend value "in_review" is shown as "reviewed". */
export const normStatus = (s: string) => (s === "in_review" ? "reviewed" : s);

export function groupByStatus<T extends { review_status: string }>(rows: T[]): Record<string, T[]> {
  const out: Record<string, T[]> = Object.fromEntries(PIPELINE_STAGES.map((s) => [s.id, [] as T[]]));
  for (const r of rows) { const k = normStatus(r.review_status); (out[k] ?? out.new).push(r); }
  return out;
}

/** Groups bulk-change records by their previous status so each group can be restored with one request. */
export function groupChangesByPrevious(changes: { candidate_id: number; from: string }[]): Record<string, number[]> {
  const out: Record<string, number[]> = {};
  for (const c of changes) (out[c.from] = out[c.from] ?? []).push(c.candidate_id);
  return out;
}

/** Simple token search: every word must appear. Returns -1 for no match, higher = better (earlier / word-start hits). */
export function fuzzyScore(query: string, text: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 0;
  const t = text.toLowerCase();
  let total = 0;
  for (const tok of q.split(/\s+/)) {
    const i = t.indexOf(tok);
    if (i < 0) return -1;
    total += 100 - Math.min(i, 90) + (i === 0 || t[i - 1] === " " ? 25 : 0);
  }
  return total;
}

/** Heatmap cell colour for a 0-100 score (brand violet, darker = better). */
export function heatStyle(score: number | null | undefined): { backgroundColor: string; color: string } {
  if (score === null || score === undefined) return { backgroundColor: "#f1f5f9", color: "#94a3b8" };
  const t = Math.max(0, Math.min(1, score / 100));
  return { backgroundColor: `rgba(91, 63, 232, ${(0.06 + 0.86 * t).toFixed(2)})`, color: t > 0.5 ? "#ffffff" : "#1e1b4b" };
}

/** [key, score] of the highest score, ignoring missing values. */
export function bestEntry(scores: Record<number, number | null | undefined>): [number, number] | null {
  let best: [number, number] | null = null;
  for (const [k, v] of Object.entries(scores)) { if (v === null || v === undefined) continue; if (!best || v > best[1]) best = [Number(k), v]; }
  return best;
}

export function weightsValid(w: Record<string, number>): boolean { return Math.abs(Object.values(w).reduce((a, b) => a + b, 0) - 1) < 0.001; }

// ---- interview notes ---------------------------------------------------------------------------
export const INTERVIEW_ROUNDS = [
  { id: "phone_screen", label: "Phone screen" }, { id: "technical", label: "Technical" }, { id: "hr", label: "HR" },
  { id: "culture", label: "Culture fit" }, { id: "final", label: "Final" }, { id: "other", label: "Other" },
] as const;
export const RECOMMENDATIONS = [
  { id: "strong_yes", label: "Strong yes", tone: "green" }, { id: "yes", label: "Yes", tone: "green" }, { id: "undecided", label: "Undecided", tone: "slate" },
  { id: "no", label: "No", tone: "amber" }, { id: "strong_no", label: "Strong no", tone: "red" },
] as const;
export const RATING_CRITERIA: { id: string; label: string }[] = [
  { id: "technical", label: "Technical" }, { id: "communication", label: "Communication" },
  { id: "problem_solving", label: "Problem solving" }, { id: "collaboration", label: "Collaboration" },
];
export const roundLabel = (id: string) => INTERVIEW_ROUNDS.find((r) => r.id === id)?.label ?? id;
export const recommendationOf = (id: string) => RECOMMENDATIONS.find((r) => r.id === id) ?? RECOMMENDATIONS[2];

/** Keeps only valid 1-5 whole-number ratings (unset criteria are simply left out). */
export function cleanRatings(r: Record<string, number | undefined>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(r)) if (typeof v === "number" && Number.isInteger(v) && v >= 1 && v <= 5) out[k] = v;
  return out;
}

/** Today's date as YYYY-MM-DD in the user's local timezone (for a date input). */
export function todayLocal(d = new Date()): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** "1 strong yes · 2 yes" - a tally of what interviewers said (no combined verdict). */
export function tallyText(rec: Record<string, number>): string {
  return RECOMMENDATIONS.filter((r) => (rec[r.id] ?? 0) > 0).map((r) => `${rec[r.id]} ${r.label.toLowerCase()}`).join(" · ");
}

/** Per-candidate interview figures used on the pipeline card (from /candidates/interviews/summary). */
export interface InterviewBrief { count: number; avg_rating: number | null; recommendations: Record<string, number> }
export const interviewLabel = (count: number) => `${count} interview${count === 1 ? "" : "s"}`;
/** Tooltip text: how many interviews, the average of the rated ones, and what interviewers said. */
export function interviewTitle(b: InterviewBrief): string {
  const parts = [interviewLabel(b.count)];
  parts.push(b.avg_rating === null ? "no ratings yet" : `average rating ${b.avg_rating.toFixed(1)} / 5`);
  const tally = tallyText(b.recommendations);
  if (tally) parts.push(`interviewers said: ${tally}`);
  return parts.join(" · ");
}
