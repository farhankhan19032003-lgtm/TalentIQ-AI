import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Download, GitCompare, Play, Save, Sparkles, Star, X } from "lucide-react";
import { api, download, errMsg } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import { useToast } from "../components/Toast";
import PoolBanner from "../components/PoolBanner";
import WeightsPanel from "../components/WeightsPanel";
import { Chip, Disclaimer, Empty, ErrorBox, PageTitle, Pager, ScoreBadge, SkillChips, SkillLegend, Spinner, Stat } from "../components/ui";
import { ResultsResponse, RunInfo, Settings } from "../types";
import { COMP_LABEL, STATUSES, STATUS_LABEL, fmt, groupChangesByPrevious, weightsValid } from "../utils";

const PAGE = 15;
interface BulkChange { candidate_id: number; from: string; to: string }
interface BulkResponse { requested: number; updated: number; unchanged: number; changes: BulkChange[] }

export default function Ranking() {
  const nav = useNavigate();
  const { toast } = useToast();
  const { jobId, blind } = useApp();
  const [busyBulk, setBusyBulk] = useState(false);
  const [simple, setSimple] = useState(true);   // M4 "Simple view": Candidate | Experience | Match % | Matched Skills
  const settings = useAsync(() => api.get<Settings>("/settings").then((r) => r.data), []);
  const [page, setPage] = useState(1);
  const [f, setF] = useState({ q: "", min_score: "", min_exp: "", skills: "", review_status: "", sort: "overall", order: "desc" });
  const [sel, setSel] = useState<number[]>([]);
  const [weights, setWeights] = useState<Record<string, number> | null>(null);
  const [showW, setShowW] = useState(false);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState<any[]>([]);

  const res = useAsync(async () => {
    if (!jobId) return null;
    const runs = (await api.get<RunInfo[]>(`/matching/runs/${jobId}`)).data;      // avoid a 404 when no run exists yet
    if (!runs.length) return null;
    try {
      return (await api.get<ResultsResponse>(`/matching/results/${jobId}`, { params: { page, page_size: PAGE, blind, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v !== "")) } })).data;
    } catch (e: any) { if (e?.response?.status === 404) return null; throw e; }
  }, [jobId, page, blind, f.q, f.min_score, f.min_exp, f.skills, f.review_status, f.sort, f.order]);
  useEffect(() => { if (settings.data && !weights) setWeights({ ...settings.data.default_weights }); }, [settings.data, weights]);
  useEffect(() => { if (jobId) api.get(`/searches`, { params: { job_id: jobId } }).then((r) => setSaved(r.data)).catch(() => {}); }, [jobId]);

  const run = async () => {
    if (!jobId || !weights) return;
    if (!weightsValid(weights)) { setErr("Weights must add up to 100%."); return; }
    setRunning(true); setErr(null);
    try { await api.post<RunInfo>(`/matching/run/${jobId}`, { weights }); setPage(1); setSel([]); res.reload(); } catch (e) { setErr(errMsg(e)); } finally { setRunning(false); }
  };
  const toggle = (id: number) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const saveSearch = async () => {
    const name = prompt("Name this search"); if (!name || !jobId) return;
    try { await api.post("/searches", { name, job_id: jobId, filters: f }); const r = await api.get(`/searches`, { params: { job_id: jobId } }); setSaved(r.data); } catch (e) { setErr(errMsg(e)); }
  };
  const set = (k: string, v: string) => { setF((p) => ({ ...p, [k]: v })); setPage(1); };
  const items = res.data?.items ?? [];
  const threshold = res.data?.summary.high_threshold ?? 70;
  const allOnPage = items.length > 0 && items.every((r) => sel.includes(r.candidate_id));
  const toggleAllOnPage = () => setSel((s) => (allOnPage ? s.filter((id) => !items.some((r) => r.candidate_id === id)) : [...new Set([...s, ...items.map((r) => r.candidate_id)])]));
  const selectHighMatches = async () => {
    if (!jobId) return;
    try {
      const r = (await api.get<ResultsResponse>(`/matching/results/${jobId}`, { params: { page_size: 100, min_score: threshold, blind } })).data;
      setSel(r.items.map((i) => i.candidate_id));
      toast(r.items.length ? `Selected ${r.items.length} candidate${r.items.length === 1 ? "" : "s"} scoring ${threshold} or more` : `Nobody scores ${threshold} or more yet`, { kind: "info" });
    } catch (e) { setErr(errMsg(e)); }
  };
  const undoBulk = async (changes: BulkChange[]) => {
    try {
      for (const [prev, ids] of Object.entries(groupChangesByPrevious(changes))) await api.post("/candidates/status/bulk", { candidate_ids: ids, review_status: prev });
      res.reload();
      toast(`Restored ${changes.length} candidate${changes.length === 1 ? "" : "s"} to their previous stage`, { kind: "info" });
    } catch (e) { toast(errMsg(e), { kind: "error" }); }
  };
  const applyBulk = async (to: string) => {
    if (!sel.length) return;
    if (to === "not_progressing" && !confirm(`Mark ${sel.length} candidate(s) as “Not progressing”? This is your decision, nothing is deleted, and you can undo it.`)) return;
    setBusyBulk(true); setErr(null);
    try {
      const r = (await api.post<BulkResponse>("/candidates/status/bulk", { candidate_ids: sel, review_status: to })).data;
      setSel([]); res.reload();
      const label = STATUS_LABEL[to] ?? to;
      toast(r.updated ? `${r.updated} candidate${r.updated === 1 ? "" : "s"} moved to ${label}${r.unchanged ? ` (${r.unchanged} already there)` : ""}` : `No change: all ${r.unchanged} were already ${label}`,
        { kind: r.updated ? "success" : "info", action: r.updated ? { label: "Undo", onClick: () => undoBulk(r.changes) } : undefined });
    } catch (e) { setErr(errMsg(e)); toast(errMsg(e), { kind: "error" }); } finally { setBusyBulk(false); }
  };
  const exp = (kind: string, ext: string) => download(`/reports/${jobId}/${kind}${blind ? "?blind=true" : ""}`, `talentiq_${jobId}.${ext}`).catch((e) => setErr(errMsg(e)));
  const topMissing = useMemo(() => { const m: Record<string, number> = {}; items.forEach((i) => i.missing_skills.forEach((s) => (m[s] = (m[s] ?? 0) + 1))); return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 5); }, [items]);

  if (!jobId) return <div><PageTitle title="Ranking" /><Empty>Select an active job in the top bar (or <Link className="underline" to="/jobs/new">create one</Link>).</Empty></div>;
  return (
    <div>
      <PageTitle title="Candidate ranking" sub={res.data?.job.title}>
        {res.data && <><button className="btn-ghost" onClick={() => exp("csv", "csv")}><Download className="h-4 w-4" />CSV</button>
          <button className="btn-ghost" onClick={() => exp("excel", "xlsx")}><Download className="h-4 w-4" />Excel</button>
          <button className="btn-ghost" onClick={() => exp("pdf", "pdf")}><Download className="h-4 w-4" />PDF</button></>}
      </PageTitle>
      {(res.error || err) && <div className="mb-3"><ErrorBox message={(res.error || err)!} onRetry={res.reload} /></div>}

      <div className="card mb-4 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn-primary" disabled={running} onClick={run}><Play className="h-4 w-4" />{running ? "Matching…" : res.data ? "Re-run matching" : "Run matching"}</button>
          <button className="btn-ghost" onClick={() => setShowW(!showW)}>Scoring weights</button>
          <Link className="btn-ghost" to="/whatif">What-if simulation</Link>
          {res.data && <span className="ml-auto text-xs text-slate-500">Run #{res.data.run.run_id} · algorithm v{res.data.run.algorithm_version} · <span title={res.data.run.model_name}>{res.data.run.similarity_method === "minilm" ? "MiniLM sentence embeddings" : res.data.run.fallback_reason ? "TF-IDF fallback" : "TF-IDF similarity"}</span> · {res.data.run.duration_ms} ms</span>}
        </div>
        {showW && weights && settings.data && <div className="mt-4 max-w-xl"><WeightsPanel value={weights} onChange={setWeights} defaults={settings.data.default_weights} /></div>}
        {res.data?.run.fallback_reason && <p className="mt-2 text-xs text-amber-700">Semantic model fallback: {res.data.run.fallback_reason}</p>}
      </div>

      {res.loading ? <Spinner /> : !res.data ? <Empty>No ranking yet for this job. Upload resumes, then click “Run matching”.</Empty> : (
        <>
          <PoolBanner pool={res.data.pool} jobId={jobId} onRerun={run} />
          <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Candidates ranked" value={res.data.summary.total_ranked} /><Stat label="Average score" value={fmt(res.data.summary.average_score)} />
            <Stat label={`≥ ${res.data.summary.high_threshold} match`} value={res.data.summary.high_matching} /><Stat label="Needs review" value={res.data.summary.needs_review} hint="Low confidence or missing info" />
          </div>
          <div className="card mb-4 grid grid-cols-2 gap-3 p-4 md:grid-cols-6">
            <div className="md:col-span-2"><label className="label" htmlFor="q">Search</label><input id="q" className="input" value={f.q} onChange={(e) => set("q", e.target.value)} placeholder={blind ? "Disabled in blind mode" : "Name / role"} disabled={blind} /></div>
            <div><label className="label" htmlFor="ms">Min score</label><input id="ms" type="number" className="input" value={f.min_score} onChange={(e) => set("min_score", e.target.value)} /></div>
            <div><label className="label" htmlFor="me">Min years</label><input id="me" type="number" className="input" value={f.min_exp} onChange={(e) => set("min_exp", e.target.value)} /></div>
            <div><label className="label" htmlFor="sk">Has skills</label><input id="sk" className="input" value={f.skills} onChange={(e) => set("skills", e.target.value)} placeholder="Python,SQL" /></div>
            <div><label className="label" htmlFor="rs">Review status</label><select id="rs" className="input" value={f.review_status} onChange={(e) => set("review_status", e.target.value)}><option value="">Any</option>{STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</select></div>
            <div><label className="label" htmlFor="so">Sort</label><select id="so" className="input" value={f.sort} onChange={(e) => set("sort", e.target.value)}><option value="overall">Overall score</option><option value="experience">Relevant experience</option><option value="coverage">Skill coverage</option><option value="confidence">Confidence</option><option value="name">Name</option></select></div>
            <div><label className="label" htmlFor="or">Order</label><select id="or" className="input" value={f.order} onChange={(e) => set("order", e.target.value)}><option value="desc">Descending</option><option value="asc">Ascending</option></select></div>
            <div className="flex items-end gap-2 md:col-span-4"><button className="btn-ghost" onClick={saveSearch}><Save className="h-4 w-4" />Save search</button>
              {saved.length > 0 && <select aria-label="Saved searches" className="input w-48" defaultValue="" onChange={(e) => { const s = saved.find((x) => String(x.id) === e.target.value); if (s) { setF({ ...f, ...s.filters }); setPage(1); } }}><option value="">Saved searches…</option>{saved.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>}</div>
          </div>

          <div className="mb-2 flex flex-wrap items-center gap-3 text-sm">
            <label className="mr-2 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 font-medium" title="Simple view shows only Candidate, Experience, Match % and Matched skills">
              <input type="checkbox" role="switch" checked={simple} onChange={(e) => setSimple(e.target.checked)} />Simple view</label>
            <button className="btn-primary" disabled={sel.length < 2 || sel.length > 5} title={sel.length > 5 ? "Compare works with 2 to 5 candidates" : undefined} onClick={() => nav(`/compare?ids=${sel.join(",")}`)}><GitCompare className="h-4 w-4" />Compare ({sel.length}/5)</button>
            <button className="btn-ghost" onClick={selectHighMatches} title="Select every candidate at or above the high-match score, across all pages"><Sparkles className="h-4 w-4" />Select all ≥ {threshold}</button>
            {topMissing.length > 0 && <span className="text-xs text-slate-500">Most missing on this page: {topMissing.map(([s, n]) => `${s} (${n})`).join(", ")}</span>}
          </div>
          {sel.length > 0 && (
            <div role="region" aria-label="Bulk actions" className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-brand-200 bg-brand-50 px-4 py-3">
              <span className="text-sm font-semibold text-brand-900">{sel.length} selected</span>
              <button className="btn-primary" disabled={busyBulk} onClick={() => applyBulk("shortlisted")}><Star className="h-4 w-4" />{busyBulk ? "Updating…" : `Shortlist ${sel.length}`}</button>
              <select aria-label="Move selected candidates to stage" className="input w-44" value="" disabled={busyBulk} onChange={(e) => e.target.value && applyBulk(e.target.value)}>
                <option value="">Move to…</option>{STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
              </select>
              <button className="btn-ghost ml-auto" onClick={() => setSel([])}><X className="h-4 w-4" />Clear</button>
              <p className="w-full text-xs text-brand-800/80">Stage changes are your decisions and are audit-logged. The selection is kept across pages; Compare needs 2–5 selected.</p>
            </div>
          )}
          {!items.length ? <Empty>No candidates match these filters.</Empty> : (
            <div className="card overflow-x-auto"><table className="w-full">
              <thead className="border-b border-slate-200">{simple
                ? <tr><th className="th">Candidate</th><th className="th">Experience</th><th className="th">Match %</th><th className="th">Matched Skills</th></tr>
                : <tr><th className="th"><input type="checkbox" aria-label="Select all on this page" checked={allOnPage} onChange={toggleAllOnPage} /></th><th className="th">#</th><th className="th">Candidate</th><th className="th">Match %</th>
                {Object.keys(COMP_LABEL).slice(0, 4).map((k) => <th key={k} className="th hidden xl:table-cell">{COMP_LABEL[k].split(" ")[0]}</th>)}
                <th className="th">Experience (relevant / total)</th><th className="th">Matched skills (exact / related / missing)</th><th className="th">Confidence</th><th className="th">Status</th></tr>}</thead>
              <tbody className="divide-y divide-slate-100">{items.map((r) => (
                simple ? (
                <tr key={r.result_id} className="hover:bg-slate-50" data-testid="simple-row">
                  <td className="td min-w-[9.5rem]"><Link className="font-medium text-brand-700 hover:underline" to={`/candidates/${r.candidate_id}`}>{r.name}</Link><div className="text-xs text-slate-500">{r.latest_role ? (r.role_source === "headline" ? <em>{r.latest_role} (profile)</em> : r.latest_role) : "Role not found"}</div></td>
                  <td className="td tabular-nums">{r.employment_count === 0 && !r.claimed_years ? <span className="text-xs text-slate-500" title="No dated roles found in the resume">No dated roles</span>
                    : r.employment_count === 0 ? <span className="text-amber-700" title="Stated in the resume text, not verifiable from dated roles">claims {r.claimed_years} years</span>
                    : <>{fmt(r.total_years)} {r.total_years === 1 ? "year" : "years"}</>}</td>
                  <td className="td"><ScoreBadge score={r.overall} low={r.score_low} high={r.score_high} /></td>
                  <td className="td min-w-[15rem]" data-testid={`matched-${r.candidate_id}`}><SkillChips matched={r.matched_skills} related={r.related_skills} missing={r.missing_skills} max={{ matched: 4, related: 2, missing: 2 }} /></td>
                </tr>) : (
                <tr key={r.result_id} className="hover:bg-slate-50">
                  <td className="td"><input type="checkbox" aria-label={`Select ${r.name}`} checked={sel.includes(r.candidate_id)} onChange={() => toggle(r.candidate_id)} /></td>
                  <td className="td font-semibold">{r.rank}{r.sensitivity && !r.sensitivity.stable && <span title={`Rank varies ${r.sensitivity.rank_min}–${r.sensitivity.rank_max} under ±10pp weight changes`} className="ml-1 text-xs text-amber-600">±</span>}</td>
                  <td className="td min-w-[9.5rem]"><Link className="font-medium text-brand-700 hover:underline" to={`/candidates/${r.candidate_id}`}>{r.name}</Link><div className="text-xs text-slate-500" title={r.role_source === "headline" ? "Role as the resume describes itself; no dated job title was found" : undefined}>{r.latest_role ? (r.role_source === "headline" ? <em>{r.latest_role} (profile)</em> : r.latest_role) : "Role not found"}</div></td>
                  <td className="td"><ScoreBadge score={r.overall} low={r.score_low} high={r.score_high} />{r.override && <Chip tone="amber">override</Chip>}</td>
                  {Object.keys(COMP_LABEL).slice(0, 4).map((k) => <td key={k} className="td hidden xl:table-cell tabular-nums">{r.components[k]?.status === "not_required" ? "no req." : r.components[k]?.score == null ? "n/v" : fmt(r.components[k].score, 0)}</td>)}
                  <td className="td tabular-nums">{r.employment_count === 0 && !r.claimed_years
                    ? <span className="text-xs text-slate-500" title="No Experience/Internship section with dates was found (typical for freshers)">No dated roles</span>
                    : r.employment_count === 0 ? <span className="text-xs text-amber-700" title="Years stated in the resume text, not verifiable from dated roles">claims {r.claimed_years} y</span>
                    : <>{fmt(r.relevant_years)} / {fmt(r.total_years)} y</>}</td>
                  <td className="td min-w-[15rem]" data-testid={`matched-${r.candidate_id}`}>
                    <SkillChips matched={r.matched_skills} related={r.related_skills} missing={r.missing_skills} max={{ matched: 3, related: 2, missing: 2 }} />
                    <div className="mt-1 text-xs text-slate-500">{r.matched_skills.length} exact · {r.related_skills.length} related · {r.missing_skills.length} missing</div>
                  </td>
                  <td className="td tabular-nums">{fmt(r.confidence, 0)}%{r.needs_review && <span className="ml-1" title={r.parse_review?.reasons?.length ? r.parse_review.reasons.join(" ") : "Low confidence, incomplete data or a wide score range"}><Chip tone="amber">{r.parse_review?.needs_review ? "needs review" : "review"}</Chip></span>}</td>
                  <td className="td">{STATUS_LABEL[r.review_status] ?? r.review_status}</td></tr>)))}
              </tbody></table>
              <Pager page={page} pageSize={PAGE} total={res.data.total} onPage={setPage} /></div>
          )}
          <div className="mt-2"><SkillLegend /></div>
          <p className="mt-2 text-xs text-slate-500">“n/v” = not verifiable from the resume (not treated as a mismatch). “±” = rank is sensitive to weight changes. Score ranges show what the score could be if missing evidence were supplied.</p>
          <div className="mt-3"><Disclaimer /></div>
        </>
      )}
    </div>
  );
}
