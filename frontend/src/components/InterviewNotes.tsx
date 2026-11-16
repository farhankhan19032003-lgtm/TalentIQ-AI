import { useState } from "react";
import { MessageSquarePlus, Pencil, Star, Trash2, X } from "lucide-react";
import { api, errMsg } from "../api";
import { useAsync } from "../hooks";
import { Job, Interview, InterviewsResponse, Paged } from "../types";
import { INTERVIEW_ROUNDS, RATING_CRITERIA, RECOMMENDATIONS, cleanRatings, fmt, recommendationOf, roundLabel, tallyText, todayLocal } from "../utils";
import { useToast } from "./Toast";
import { Chip, Empty, ErrorBox, Spinner } from "./ui";

/** 1-5 star input. Clicking the selected star again clears it. */
export function StarRating({ label, value, onChange }: { label: string; value: number | undefined; onChange?: (v: number | undefined) => void }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} of 5`} disabled={!onChange}
          onClick={() => onChange?.(value === n ? undefined : n)} className="rounded p-0.5 disabled:cursor-default">
          <Star className={`h-5 w-5 transition ${value !== undefined && n <= value ? "fill-amber-400 text-amber-500" : "text-slate-300"}`} />
        </button>
      ))}
    </div>
  );
}

interface Form { round: string; interviewed_on: string; interviewer: string; recommendation: string; ratings: Record<string, number | undefined>; strengths: string; concerns: string; notes: string; link_job: boolean }
const blank = (): Form => ({ round: "technical", interviewed_on: todayLocal(), interviewer: "", recommendation: "undecided", ratings: {}, strengths: "", concerns: "", notes: "", link_job: true });
const fromNote = (n: Interview): Form => ({ round: n.round, interviewed_on: n.interviewed_on ?? todayLocal(), interviewer: n.interviewer, recommendation: n.recommendation, ratings: { ...n.ratings }, strengths: n.strengths, concerns: n.concerns, notes: n.notes, link_job: n.job_id !== null });

export default function InterviewNotes({ candidateId, activeJobId }: { candidateId: number; activeJobId: number | null }) {
  const { toast } = useToast();
  const list = useAsync(() => api.get<InterviewsResponse>(`/candidates/${candidateId}/interviews`).then((r) => r.data), [candidateId]);
  const jobs = useAsync(() => api.get<Paged<Job>>("/jobs?page_size=100").then((r) => r.data.items), []);
  const [form, setForm] = useState<Form | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => (f ? { ...f, [k]: v } : f));
  // Functional update: rapid clicks on different criteria must never overwrite each other.
  const setRating = (id: string, v: number | undefined) => setForm((f) => (f ? { ...f, ratings: { ...f.ratings, [id]: v } } : f));
  const jobTitle = (id: number | null) => (id === null ? null : jobs.data?.find((j) => j.id === id)?.title ?? `Job ${id}`);
  const close = () => { setForm(null); setEditingId(null); setErr(null); };

  const ratings = form ? cleanRatings(form.ratings) : {};
  const empty = !form || !(Object.keys(ratings).length || form.strengths.trim() || form.concerns.trim() || form.notes.trim() || form.recommendation !== "undecided");

  const save = async () => {
    if (!form || empty) return;
    setSaving(true); setErr(null);
    const body = { round: form.round, interviewed_on: form.interviewed_on || undefined, interviewer: form.interviewer, recommendation: form.recommendation, ratings,
      strengths: form.strengths, concerns: form.concerns, notes: form.notes, job_id: form.link_job ? activeJobId : null };
    try {
      if (editingId === null) await api.post(`/candidates/${candidateId}/interviews`, body);
      else await api.patch(`/candidates/${candidateId}/interviews/${editingId}`, body);
      toast(editingId === null ? "Interview note saved." : "Interview note updated.");
      close(); list.reload();
    } catch (e) { setErr(errMsg(e)); } finally { setSaving(false); }
  };
  const remove = async (n: Interview) => {
    if (!confirm(`Delete this ${roundLabel(n.round).toLowerCase()} interview note? This cannot be undone.`)) return;
    try { await api.delete(`/candidates/${candidateId}/interviews/${n.id}`); toast("Interview note deleted.", { kind: "info" }); list.reload(); }
    catch (e) { toast(errMsg(e), { kind: "error" }); }
  };

  const items = list.data?.items ?? [];
  const sum = list.data?.summary;
  return (
    <section className="card mt-5 p-5" aria-label="Interview notes">
      <div className="mb-1 flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-bold text-slate-900">Interview notes</h2>
        {sum && sum.count > 0 && <Chip>{sum.count} interview{sum.count === 1 ? "" : "s"}</Chip>}
        {!form && <button className="btn-primary ml-auto" onClick={() => { setForm(blank()); setEditingId(null); }}><MessageSquarePlus className="h-4 w-4" />Add interview</button>}
      </div>
      <p className="mb-4 text-xs text-slate-500">Structured scorecards written by interviewers. They are human opinions: they never change the match score or rank, and nothing is decided automatically.</p>
      {(err || list.error) && <div className="mb-3"><ErrorBox message={(err || list.error)!} onRetry={list.reload} /></div>}

      {sum && sum.count > 0 && (
        <div className="mb-4 grid gap-4 rounded-2xl bg-slate-50 p-4 md:grid-cols-[auto_1fr_auto] md:items-center">
          <div><div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Average rating</div>
            <div className="flex items-center gap-2"><span className="text-3xl font-extrabold text-slate-900">{sum.avg_rating === null ? "—" : fmt(sum.avg_rating, 1)}</span><span className="text-sm text-slate-500">/ 5</span></div></div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1">{RATING_CRITERIA.map((c) => {
            const v = sum.avg_by_criterion[c.id];
            return <div key={c.id} className="flex items-center gap-2 text-xs text-slate-600"><span className="w-28 shrink-0">{c.label}</span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200"><span className="block h-full rounded-full bg-amber-400" style={{ width: `${((v ?? 0) / 5) * 100}%` }} /></span><span className="w-6 text-right tabular-nums">{v === null ? "—" : fmt(v, 1)}</span></div>;
          })}</div>
          <div className="text-sm"><div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Interviewers said</div><div className="font-medium text-slate-800">{tallyText(sum.recommendations) || "No recommendations yet"}</div></div>
        </div>
      )}

      {form && (
        <div className="mb-5 rounded-2xl border border-brand-200 bg-brand-50/50 p-4" role="form" aria-label={editingId === null ? "New interview note" : "Edit interview note"}>
          <div className="grid gap-3 md:grid-cols-3">
            <div><label className="label" htmlFor="iv-round">Round</label><select id="iv-round" className="input" value={form.round} onChange={(e) => set("round", e.target.value)}>{INTERVIEW_ROUNDS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></div>
            <div><label className="label" htmlFor="iv-date">Interview date</label><input id="iv-date" type="date" className="input" value={form.interviewed_on} onChange={(e) => set("interviewed_on", e.target.value)} /></div>
            <div><label className="label" htmlFor="iv-who">Interviewer</label><input id="iv-who" className="input" maxLength={100} placeholder="Name or initials" value={form.interviewer} onChange={(e) => set("interviewer", e.target.value)} /></div>
          </div>
          <div className="mt-4 grid gap-x-8 gap-y-2 md:grid-cols-2">{RATING_CRITERIA.map((c) => (
            <div key={c.id} className="flex items-center justify-between gap-3"><span className="text-sm text-slate-700">{c.label}</span>
              <StarRating label={`${c.label} rating`} value={form.ratings[c.id]} onChange={(v) => setRating(c.id, v)} /></div>
          ))}</div>
          <div className="mt-4"><div className="label">Recommendation</div>
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Recommendation">{RECOMMENDATIONS.map((r) => (
              <button key={r.id} type="button" role="radio" aria-checked={form.recommendation === r.id} onClick={() => set("recommendation", r.id)}
                className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold transition ${form.recommendation === r.id ? "border-brand-500 bg-brand-600 text-white shadow-glow" : "border-slate-200 bg-white text-slate-700 hover:border-brand-300"}`}>{r.label}</button>
            ))}</div></div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div><label className="label" htmlFor="iv-str">Strengths</label><textarea id="iv-str" className="input h-20" maxLength={2000} value={form.strengths} onChange={(e) => set("strengths", e.target.value)} /></div>
            <div><label className="label" htmlFor="iv-con">Concerns</label><textarea id="iv-con" className="input h-20" maxLength={2000} value={form.concerns} onChange={(e) => set("concerns", e.target.value)} /></div>
          </div>
          <div className="mt-3"><label className="label" htmlFor="iv-notes">Notes</label><textarea id="iv-notes" className="input h-24" maxLength={4000} placeholder="What was discussed, evidence for your ratings…" value={form.notes} onChange={(e) => set("notes", e.target.value)} /></div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {activeJobId !== null && <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={form.link_job} onChange={(e) => set("link_job", e.target.checked)} />Link to “{jobTitle(activeJobId)}”</label>}
            <button className="btn-primary ml-auto" disabled={saving || empty} onClick={save}>{saving ? "Saving…" : editingId === null ? "Save interview" : "Save changes"}</button>
            <button className="btn-ghost" onClick={close}><X className="h-4 w-4" />Cancel</button>
          </div>
          {empty && <p className="mt-2 text-xs text-slate-500">Add at least a rating, a recommendation or some notes to save.</p>}
        </div>
      )}

      {list.loading && !list.data ? <Spinner /> : items.length === 0 && !form ? <Empty>No interviews recorded yet. Add one after each interview round.</Empty> : (
        <ul className="space-y-3">{items.map((n) => {
          const rec = recommendationOf(n.recommendation);
          return (
            <li key={n.id} className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone="blue">{roundLabel(n.round)}</Chip>
                <span className="text-sm font-medium text-slate-800">{n.interviewed_on ?? "no date"}</span>
                {n.interviewer && <span className="text-sm text-slate-500">· {n.interviewer}</span>}
                {n.job_id !== null && <Chip>{jobTitle(n.job_id)}</Chip>}
                <span className="ml-auto flex items-center gap-2">
                  <Chip tone={rec.tone}>{rec.label}</Chip>
                  <button className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-brand-700" aria-label={`Edit ${roundLabel(n.round)} interview note`} onClick={() => { setForm(fromNote(n)); setEditingId(n.id); setErr(null); }}><Pencil className="h-4 w-4" /></button>
                  <button className="rounded-lg p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-600" aria-label={`Delete ${roundLabel(n.round)} interview note`} onClick={() => remove(n)}><Trash2 className="h-4 w-4" /></button>
                </span>
              </div>
              {Object.keys(n.ratings).length > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-1">
                  {RATING_CRITERIA.filter((c) => n.ratings[c.id]).map((c) => <div key={c.id} className="flex items-center gap-2 text-xs text-slate-600"><span>{c.label}</span><StarRating label={`${c.label} rating`} value={n.ratings[c.id]} /></div>)}
                  {n.rating_avg !== null && <span className="ml-auto rounded-full bg-amber-50 px-2.5 py-0.5 text-sm font-bold text-amber-800 ring-1 ring-inset ring-amber-200">{fmt(n.rating_avg, 1)} / 5</span>}
                </div>
              )}
              {(n.strengths || n.concerns) && (
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {n.strengths && <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900"><div className="mb-0.5 text-[11px] font-bold uppercase tracking-wider text-emerald-700">Strengths</div>{n.strengths}</div>}
                  {n.concerns && <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><div className="mb-0.5 text-[11px] font-bold uppercase tracking-wider text-amber-700">Concerns</div>{n.concerns}</div>}
                </div>
              )}
              {n.notes && <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{n.notes}</p>}
            </li>
          );
        })}</ul>
      )}
    </section>
  );
}
