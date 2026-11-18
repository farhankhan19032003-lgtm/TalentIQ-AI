import { Fragment, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChevronDown, ChevronRight, Download, Trash2 } from "lucide-react";
import { api, download, errMsg } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import EvidenceViewer from "../components/EvidenceViewer";
import InterviewNotes from "../components/InterviewNotes";
import { Chip, Disclaimer, ErrorBox, MatchTag, PageTitle, ScoreBadge, SkillChips, SkillLegend, Spinner } from "../components/ui";
import { CandidateDetail } from "../types";
import { COMP_LABEL, EDU_LABEL, STATUSES, STATUS_LABEL, educationVerdict, experienceVerdict, fmt, warningText } from "../utils";

export default function Candidate() {
  const { id } = useParams();
  const nav = useNavigate();
  const { jobId, blind } = useApp();
  const { data, error, loading, reload } = useAsync(() => (jobId ? api.get<CandidateDetail>(`/matching/candidate/${id}`, { params: { job_id: jobId, blind } }).then((r) => r.data) : Promise.resolve(null)), [id, jobId, blind]);
  const [open, setOpen] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [ov, setOv] = useState({ score: "", reason: "" });
  const [err, setErr] = useState<string | null>(null);
  const act = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); reload(); } catch (e) { setErr(errMsg(e)); } };

  if (!jobId) return <p className="text-sm">Select an active job first (top bar) to see this candidate's match.</p>;
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;
  const { candidate: c, result: r } = data;
  const chart = Object.keys(COMP_LABEL).map((k) => ({ name: COMP_LABEL[k], score: r.components[k]?.score ?? 0, contribution: r.components[k]?.contribution ?? 0, nv: r.components[k]?.status === "unverified" || r.components[k]?.score == null }));
  const gap = { matched: r.matched_skills, related: r.related_skills, missing: r.missing_skills };
  const ex = r.explanation;
  const xv = experienceVerdict({ ...r.experience, claimed_years: r.experience.claimed_years });
  const ev = educationVerdict(r.education.required_level, r.education.candidate_level);
  const need = r.experience.required_min_years as number | null;
  const pct = need ? Math.min(100, Math.round((r.experience.relevant_effective_years / need) * 100)) : null;
  const topEdu = (c.education ?? [])[0];
  const verdictTone = (tone: string) => (tone === "green" ? "bg-emerald-50 text-emerald-800 ring-emerald-200" : tone === "amber" ? "bg-amber-50 text-amber-900 ring-amber-200" : tone === "red" ? "bg-red-50 text-red-700 ring-red-200" : "bg-slate-100 text-slate-700 ring-slate-200");
  const shownWarnings = (c.diagnostics.warnings as string[]).map(warningText).filter((w): w is string => !!w);
  return (
    <div>
      <PageTitle title={c.name} sub={`${r.latest_role ?? "Role not stated"} · rank #${r.rank} for this job`}>
        <button className="btn-ghost" onClick={() => download(`/reports/${jobId}/candidate/${c.id}/pdf?blind=${blind}`, `candidate_${c.id}.pdf`).catch((e) => setErr(errMsg(e)))}><Download className="h-4 w-4" />PDF report</button>
        <button className="btn-danger" onClick={() => { if (confirm("Permanently delete this candidate, their resume file and all extracted data?")) act(async () => { await api.delete(`/candidates/${c.id}`); nav("/ranking"); }); }}><Trash2 className="h-4 w-4" />Delete data</button>
      </PageTitle>
      {err && <div className="mb-3"><ErrorBox message={err} /></div>}
      {r.parse_review?.needs_review && (
        <div role="alert" className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <strong>Needs review.</strong> {r.parse_review.reasons.join(" ")} The score below was calculated from the text that could be read; check it against the original file before relying on it.
        </div>)}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <section className="card p-5">
            <div className="flex flex-wrap items-center gap-4">
              <div><div className="label">Overall match</div><div className="text-4xl font-bold">{fmt(r.overall)}<span className="text-lg text-slate-400"> / 100</span></div>
                {r.score_high - r.score_low > 0.05 && <div className="text-xs text-slate-500">Range {fmt(r.score_low)}–{fmt(r.score_high)} if missing evidence were supplied</div>}</div>
              <div className="text-sm text-slate-600"><div>Confidence <strong>{fmt(r.confidence, 0)}%</strong></div><div>Completeness <strong>{fmt(r.completeness, 0)}%</strong></div><div>Rank stability: {r.sensitivity.stable ? "stable" : `${r.sensitivity.rank_min}–${r.sensitivity.rank_max}`}</div></div>
              <ScoreBadge score={r.overall} low={r.score_low} high={r.score_high} />
            </div>
            <p className="mt-4 rounded-lg bg-slate-50 p-3 text-base font-medium text-slate-800" data-testid="headline">{ex.headline}</p>
            <p className="mt-2 text-xs text-slate-500">{ex.summary}</p>
            <div className="mt-4 h-56" aria-label="Score breakdown chart">
              <ResponsiveContainer><BarChart data={chart} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" domain={[0, 100]} /><YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number, _n, p: any) => [p.payload.nv ? "not verifiable (see score range)" : `${v.toFixed(1)}/100`, "Component score"]} />
                <Bar dataKey="score">{chart.map((d, i) => <Cell key={i} fill={d.nv ? "#cbd5e1" : "#4f46e5"} />)}</Bar></BarChart></ResponsiveContainer>
            </div>
            <table className="mt-2 w-full text-sm"><thead><tr><th className="th">Component</th><th className="th">Score</th><th className="th">Effective weight</th><th className="th">Points</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{ex.component_effects.map((e) => <tr key={e.component}><td className="td">{e.label}</td><td className="td">{e.status === "not_required" || e.score == null ? "n/a" : fmt(e.score)}</td><td className="td">{e.score == null && e.status !== "not_required" ? "left out (no evidence)" : `${fmt(e.weight)}%`}</td><td className="td">{fmt(e.contribution, 2)}</td></tr>)}
                <tr className="font-semibold"><td className="td">Total</td><td className="td" /><td className="td">100%</td><td className="td">{fmt(r.overall, 2)}</td></tr></tbody></table>
          </section>

          <section className="card p-5" data-testid="skills-glance">
            <h2 className="mb-2 font-semibold">Skills vs the job</h2>
            <p className="mb-2 text-sm text-slate-600">{r.matched_skills.length} exact · {r.related_skills.length} related (partial credit) · {r.missing_skills.length} missing, out of {r.requirements.length} requirements.</p>
            <SkillChips matched={r.matched_skills} related={r.related_skills} missing={r.missing_skills} />
            <div className="mt-2"><SkillLegend /></div>
          </section>

          <section className="card p-5" data-testid="profile">
            <h2 className="mb-3 font-semibold">Candidate profile (extracted)</h2>
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              <div><dt className="label">Name</dt><dd>{c.name}</dd></div>
              <div><dt className="label">Email</dt><dd>{c.fields.email?.value ?? "not found"}</dd></div>
              <div><dt className="label">Phone</dt><dd>{c.fields.phone?.value ?? "not found"}</dd></div>
              <div><dt className="label">Current / latest role</dt><dd>{r.latest_role ? (r.role_source === "headline" ? <em title="No dated job title; this is how the resume describes itself">{r.latest_role} (profile)</em> : r.latest_role) : "not stated"}</dd></div>
              <div><dt className="label">Education</dt><dd>{topEdu ? `${topEdu.degree}${topEdu.institution ? `, ${topEdu.institution}` : ""}${topEdu.year ? ` (${topEdu.year})` : ""}` : "not found"}</dd></div>
              <div><dt className="label">Experience</dt><dd>{r.experience.roles.length === 0 ? (r.experience.claimed_years ? `claims ${r.experience.claimed_years} y (no dated roles)` : "no dated roles found") : `${fmt(r.experience.total_effective_years)} y total · ${fmt(r.experience.relevant_effective_years)} y relevant`}</dd></div>
            </dl>
            <div className="mt-3"><div className="label">Skills found in the resume ({c.skills.length})</div>
              <div className="mt-1 flex flex-wrap gap-1">{c.skills.length ? c.skills.map((s: any) => <Chip key={s.name}>{s.name}</Chip>) : <span className="text-sm text-slate-500">none extracted</span>}</div></div>
          </section>

          <section className="card p-5">
            <h2 className="mb-3 font-semibold">Why this score</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div><h3 className="mb-1 text-sm font-semibold text-emerald-700">Supports the match</h3><ul className="list-disc space-y-1 pl-5 text-sm">{ex.why_matched.map((t, i) => <li key={i}>{t}</li>)}</ul></div>
              <div><h3 className="mb-1 text-sm font-semibold text-red-700">Reduces the match</h3><ul className="list-disc space-y-1 pl-5 text-sm">{ex.why_not_matched.length ? ex.why_not_matched.map((t, i) => <li key={i}>{t}</li>) : <li>Nothing significant.</li>}</ul></div>
            </div>
            {ex.missing_information.length > 0 && <div className="mt-3 rounded-lg bg-amber-50 p-3 text-sm"><strong>Missing information</strong> (not treated as a mismatch)<ul className="list-disc pl-5">{ex.missing_information.map((t, i) => <li key={i}>{t}</li>)}</ul></div>}
          </section>

          <section className="card p-5">
            <h2 className="mb-3 font-semibold">Requirement evidence <span className="text-sm font-normal text-slate-500">(click a row to inspect the resume text)</span></h2>
            <div className="mb-3"><SkillChips matched={gap.matched} related={gap.related} missing={gap.missing} /></div>
            <table className="w-full"><thead><tr><th className="th" /><th className="th">Requirement</th><th className="th">Importance</th><th className="th">Match</th><th className="th">Credit</th></tr></thead>
              <tbody>{r.requirements.filter((q) => q.importance !== "ignored").map((q) => (
                <Fragment key={q.requirement_id}>
                  <tr className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={() => setOpen(open === q.requirement_id ? null : q.requirement_id)}>
                    <td className="td w-6">{open === q.requirement_id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</td>
                    <td className="td font-medium">{q.name}</td><td className="td">{q.importance}</td><td className="td"><MatchTag type={q.match_type} /></td><td className="td tabular-nums">{Math.round(q.credit * 100)}%</td></tr>
                  {open === q.requirement_id && <tr><td /><td colSpan={4} className="pb-3"><EvidenceViewer req={q} /></td></tr>}
                </Fragment>))}</tbody></table>
          </section>

          <section className="card p-5">
            <h2 className="mb-3 font-semibold">Experience comparison</h2>
            <div className="grid gap-3 text-sm sm:grid-cols-4" data-testid="experience-comparison">
              <div className="rounded-lg border border-slate-200 p-3"><div className="label">Job requires</div><div className="text-lg font-semibold">{need ? `${need}+ y` : "not stated"}</div>{r.experience.preferred_years && <div className="text-xs text-slate-500">preferred {r.experience.preferred_years} y</div>}</div>
              <div className="rounded-lg border border-slate-200 p-3"><div className="label">Candidate, relevant</div><div className="text-lg font-semibold">{fmt(r.experience.relevant_effective_years)} y</div></div>
              <div className="rounded-lg border border-slate-200 p-3"><div className="label">Candidate, total</div><div className="text-lg font-semibold">{fmt(r.experience.total_effective_years)} y</div></div>
              <div className={`rounded-lg p-3 ring-1 ring-inset ${verdictTone(xv.tone)}`}><div className="label">Verdict</div><div className="font-semibold" data-testid="experience-verdict">{xv.label}</div></div>
            </div>
            {pct !== null && <div className="mt-3" aria-label={`Relevant experience is ${pct}% of the requirement`}><div className="h-2 w-full overflow-hidden rounded-full bg-slate-100"><div className={`h-2 ${xv.tone === "green" ? "bg-emerald-500" : xv.tone === "amber" ? "bg-amber-500" : "bg-red-400"}`} style={{ width: `${pct}%` }} /></div><div className="mt-1 text-xs text-slate-500">{pct}% of the required experience is relevant to this job</div></div>}
            <p className="mt-3 text-xs text-slate-500">{r.experience.methodology}</p>
            <ul className="mt-3 space-y-2">{r.experience.roles.map((x: any, i: number) => (
              <li key={i} className="rounded-lg border border-slate-200 p-3 text-sm"><div className="flex flex-wrap items-center gap-2"><strong>{x.title}</strong>{x.fit != null && <span className="text-xs text-slate-500" title="Share of the job's weighted requirements this role demonstrates">fit {Math.round(x.fit * 100)}%</span>}<span className="text-slate-500">{x.company}</span><Chip>{x.type.replace("_", " ")}</Chip>{x.relevant ? <Chip tone="green">relevant</Chip> : <Chip>not relevant</Chip>}{x.date_uncertain && <Chip tone="amber">dates uncertain</Chip>}</div>
                <div className="text-xs text-slate-500">{x.start} → {x.end} · {x.months} months · p.{x.page}</div>{x.matching_skills?.length > 0 && <div className="mt-1 text-xs text-slate-600">Matching skills: {x.matching_skills.join(", ")}</div>}</li>))}</ul>
            {r.experience.notes?.map((n: string, i: number) => <p key={i} className="mt-1 text-xs text-slate-500">• {n}</p>)}
          </section>

          <section className="card p-5">
            <h2 className="mb-2 font-semibold">Education & projects</h2>
            <p className="text-sm"><span className="text-slate-500">Job requires:</span> <strong>{r.education.required_level ? EDU_LABEL[r.education.required_level] ?? "degree" : "not stated"}</strong> · <span className="text-slate-500">Candidate:</span> <strong>{r.education.candidate_level ? EDU_LABEL[r.education.candidate_level] : "not found"}</strong> <span className={`ml-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${verdictTone(ev.tone)}`}>{ev.label}</span></p>
            <p className="mt-1 text-sm text-slate-600">{r.education.note}</p>
            <ul className="mt-2 text-sm">{r.education.entries.map((e: any, i: number) => <li key={i}>• {e.degree} — {e.institution} {e.year ?? ""} <span className="text-xs text-slate-400">p.{e.page}</span></li>)}</ul>
            <p className="mt-3 text-sm text-slate-600">{r.projects.note}</p>
            {r.projects.top_projects?.map((p: any, i: number) => <p key={i} className="text-sm">• {p.name ?? p.title} <span className="text-xs text-slate-400">similarity {fmt(p.similarity, 2)}</span></p>)}
          </section>
        </div>

        <div className="space-y-5">
          <section className="card p-5">
            <h2 className="mb-2 font-semibold">Screening status</h2>
            <label className="label" htmlFor="rs">Status (recruiter-set only)</label>
            <select id="rs" className="input" value={c.review_status} onChange={(e) => act(() => api.patch(`/candidates/${c.id}/status`, { review_status: e.target.value }))}>{STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</select>
            <p className="mt-1 text-xs text-slate-500">The system never auto-rejects. Status changes are audit-logged.</p>
          </section>
          <section className="card p-5">
            <h2 className="mb-2 font-semibold">Manual score override</h2>
            <p className="mb-2 text-xs text-slate-500">Recorded alongside the machine score — the machine score and rank are never rewritten.</p>
            {r.overrides.map((o: any) => <div key={o.id} className="mb-2 rounded bg-amber-50 p-2 text-xs">Override to <strong>{o.new_score}</strong>: {o.reason}</div>)}
            <input aria-label="New score" type="number" min={0} max={100} className="input mb-2" placeholder="New score (0–100)" value={ov.score} onChange={(e) => setOv({ ...ov, score: e.target.value })} />
            <textarea aria-label="Override reason" className="input mb-2 h-16" placeholder="Reason (required)" value={ov.reason} onChange={(e) => setOv({ ...ov, reason: e.target.value })} />
            <button className="btn-ghost" disabled={!ov.score || ov.reason.trim().length < 5} onClick={() => act(async () => { await api.post(`/matching/results/${r.result_id}/override`, { new_score: Number(ov.score), reason: ov.reason }); setOv({ score: "", reason: "" }); })}>Record override</button>
          </section>
          <section className="card p-5">
            <h2 className="mb-2 font-semibold">Recruiter notes</h2>
            <ul className="mb-2 space-y-2">{c.notes.map((n: any) => <li key={n.id} className="rounded bg-slate-50 p-2 text-sm">{n.text}<div className="text-xs text-slate-400">{n.at?.slice(0, 16).replace("T", " ")}</div></li>)}</ul>
            <textarea aria-label="Add note" className="input mb-2 h-16" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note…" />
            <button className="btn-ghost" disabled={!note.trim()} onClick={() => act(async () => { await api.post(`/candidates/${c.id}/notes`, { text: note }); setNote(""); })}>Add note</button>
          </section>
          <section className="card p-5">
            <h2 className="mb-2 font-semibold">Contact (extracted)</h2>
            <dl className="space-y-1 text-sm">{["email", "phone", "location", "linkedin", "github", "portfolio"].map((k) => c.fields[k]?.value ? <div key={k}><dt className="inline text-slate-500">{k}: </dt><dd className="inline" title={c.fields[k].evidence ?? ""}>{c.fields[k].value}</dd></div> : null)}</dl>
            <p className="mt-2 text-xs text-slate-400">Hover a value to see the source line. File: {c.file.filename} ({c.file.pages} page{c.file.pages === 1 ? "" : "s"})</p>
          </section>
          <section className="card p-5">
            <h2 className="mb-2 font-semibold">Parsing quality</h2>
            <p className="text-sm">Parse confidence {fmt(c.parse_confidence * (c.parse_confidence <= 1 ? 100 : 1), 0)}% · sections: {c.diagnostics.sections_found.join(", ")}</p>
            {c.diagnostics.ocr_used && <Chip tone="amber">OCR used</Chip>}
            {c.protected_lines_removed > 0 && <p className="mt-1 text-xs text-slate-500">{c.protected_lines_removed} protected-attribute line(s) were removed before matching.</p>}
            {c.injection_flags.length > 0 && <p className="mt-1 text-xs text-amber-700">Text resembling instructions to an AI was found and ignored (treated as data only).</p>}
            {shownWarnings.map((w, i) => <p key={i} className="text-xs text-amber-700">⚠ {w}</p>)}
          </section>
        </div>
      </div>
      <InterviewNotes candidateId={c.id} activeJobId={jobId} />
      <div className="mt-5"><Disclaimer text={ex.disclaimer} /></div>
      <p className="mt-3 text-sm"><Link className="text-brand-600 underline" to="/ranking">← Back to ranking</Link></p>
    </div>
  );
}
