import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { GripVertical, MessageSquareText, Search, Star } from "lucide-react";
import { api, errMsg } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import { useToast } from "../components/Toast";
import { Chip, Empty, ErrorBox, PageTitle, ScoreBadge, Spinner } from "../components/ui";
import { ResultRow, ResultsResponse, RunInfo } from "../types";
import { InterviewBrief, PIPELINE_STAGES, STATUS_LABEL, fmt, groupByStatus, interviewLabel, interviewTitle, normStatus } from "../utils";

export default function Pipeline() {
  const { jobId, blind } = useApp();
  const { toast } = useToast();
  const res = useAsync(async () => {
    if (!jobId) return null;
    const runs = (await api.get<RunInfo[]>(`/matching/runs/${jobId}`)).data;
    if (!runs.length) return null;
    return (await api.get<ResultsResponse>(`/matching/results/${jobId}`, { params: { page_size: 100, blind } })).data;
  }, [jobId, blind]);
  const [rows, setRows] = useState<ResultRow[]>([]);
  const rowsRef = useRef<ResultRow[]>([]);
  rowsRef.current = rows;
  const [q, setQ] = useState("");
  const [dragId, setDragId] = useState<number | null>(null);
  const [over, setOver] = useState<string | null>(null);
  useEffect(() => { setRows(res.data?.items ?? []); }, [res.data]);
  // Interview count and average rating for every card, fetched in a single request. Cards without interviews are simply absent.
  const idKey = (res.data?.items ?? []).map((r) => r.candidate_id).join(",");
  const iv = useAsync(() => (idKey ? api.get<{ summaries: Record<string, InterviewBrief> }>("/candidates/interviews/summary", { params: { ids: idKey } }).then((r) => r.data.summaries) : Promise.resolve({} as Record<string, InterviewBrief>)), [idKey]);

  const move = async (id: number, to: string, undo = false) => {
    const row = rowsRef.current.find((r) => r.candidate_id === id);
    if (!row || normStatus(row.review_status) === to) return;
    const from = row.review_status;
    setRows((rs) => rs.map((r) => (r.candidate_id === id ? { ...r, review_status: to } : r)));
    try {
      await api.patch(`/candidates/${id}/status`, { review_status: to });
      toast(`${row.name} moved to ${STATUS_LABEL[to] ?? to}`, undo ? {} : { action: { label: "Undo", onClick: () => move(id, from, true) } });
    } catch (e) {
      setRows((rs) => rs.map((r) => (r.candidate_id === id ? { ...r, review_status: from } : r)));
      toast(errMsg(e), { kind: "error" });
    }
  };

  const visible = useMemo(() => {
    const t = q.trim().toLowerCase();
    return t ? rows.filter((r) => `${r.name} ${r.latest_role ?? ""}`.toLowerCase().includes(t)) : rows;
  }, [rows, q]);
  const groups = useMemo(() => groupByStatus(visible), [visible]);

  if (!jobId) return <div><PageTitle title="Pipeline board" /><div className="card"><Empty>Select an active job in the top bar to see its candidate pipeline.</Empty></div></div>;
  if (res.loading) return <Spinner />;
  return (
    <div>
      <PageTitle title="Pipeline board" sub={`Drag candidates between stages. Scores are for “${res.data?.job.title ?? "this job"}”; the stage belongs to the candidate. Nobody is moved automatically.`}>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input aria-label="Filter candidates" className="input w-60 pl-9" placeholder="Filter by name or role" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </PageTitle>
      {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
      {!res.data && !res.error && <div className="card"><Empty>No ranking run for this job yet. Run matching on the Ranking page first.</Empty></div>}
      {res.data && (
        <div className="flex gap-4 overflow-x-auto pb-4" data-testid="board">
          {PIPELINE_STAGES.map((st) => {
            const cards = groups[st.id] ?? [];
            const active = over === st.id;
            return (
              <section key={st.id} aria-label={`${st.label} stage`}
                onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; if (over !== st.id) setOver(st.id); }}
                onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(null); }}
                onDrop={(e) => { e.preventDefault(); const id = Number(e.dataTransfer.getData("text/plain") || dragId); setOver(null); setDragId(null); if (id) move(id, st.id); }}
                className={`flex w-72 shrink-0 flex-col rounded-2xl border bg-slate-100/60 p-2.5 transition ${active ? "border-brand-400 bg-brand-50 ring-4 ring-brand-100" : "border-slate-200/70"}`}>
                <header className="mb-2 flex items-center gap-2 px-1.5 pt-1">
                  <span className={`h-2.5 w-2.5 rounded-full ${st.dot}`} />
                  <h2 className="text-sm font-bold text-slate-800">{st.label}</h2>
                  <span className="ml-auto rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-slate-600 shadow-sm" data-testid={`count-${st.id}`}>{cards.length}</span>
                </header>
                <div className="flex max-h-[68vh] min-h-[5rem] flex-col gap-2 overflow-y-auto p-0.5">
                  {cards.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-xs text-slate-400">Drop candidates here</p>}
                  {cards.map((c) => (
                    <article key={c.candidate_id} draggable data-testid={`card-${c.candidate_id}`}
                      onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(c.candidate_id)); e.dataTransfer.effectAllowed = "move"; setDragId(c.candidate_id); }}
                      onDragEnd={() => { setDragId(null); setOver(null); }}
                      className={`cursor-grab rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lift active:cursor-grabbing ${dragId === c.candidate_id ? "opacity-40" : ""}`}>
                      <div className="flex items-start gap-1.5">
                        <GripVertical className="mt-0.5 h-4 w-4 shrink-0 text-slate-300" aria-hidden />
                        <div className="min-w-0 flex-1">
                          <Link to={`/candidates/${c.candidate_id}`} className="block truncate text-sm font-semibold text-brand-700 hover:underline">{c.name}</Link>
                          <div className="truncate text-xs text-slate-500">{c.latest_role ?? "No role extracted"}</div>
                        </div>
                        <ScoreBadge score={c.overall} low={c.score_low} high={c.score_high} />
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <Chip tone={c.must_have_coverage >= 75 ? "green" : c.must_have_coverage >= 40 ? "amber" : "red"}>must-have {fmt(c.must_have_coverage, 0)}%</Chip>
                        {c.needs_review && <Chip tone="amber">needs review</Chip>}
                        {iv.data?.[String(c.candidate_id)] && (() => {
                          const b = iv.data![String(c.candidate_id)];
                          return (
                            <Link to={`/candidates/${c.candidate_id}`} title={interviewTitle(b)} aria-label={`${c.name}: ${interviewTitle(b)}`} data-testid={`interviews-${c.candidate_id}`}
                              className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2.5 py-0.5 text-xs font-medium text-sky-800 ring-1 ring-inset ring-sky-200 hover:bg-sky-100">
                              <MessageSquareText className="h-3 w-3" aria-hidden />{interviewLabel(b.count)}
                              {b.avg_rating !== null && <><span aria-hidden>·</span><Star className="h-3 w-3 fill-amber-400 text-amber-500" aria-hidden /><span className="tabular-nums">{b.avg_rating.toFixed(1)}</span></>}
                            </Link>
                          );
                        })()}
                        <select aria-label={`Move ${c.name} to stage`} className="ml-auto rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-xs text-slate-600" value={normStatus(c.review_status)} onChange={(e) => move(c.candidate_id, e.target.value)}>
                          {PIPELINE_STAGES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                        </select>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
