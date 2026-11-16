import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowUpDown, Crown, Download, Flame, Search, Zap } from "lucide-react";
import { api, download, errMsg } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import { useToast } from "../components/Toast";
import { Empty, ErrorBox, PageTitle, Spinner } from "../components/ui";
import { Job, Paged, ResultRow, ResultsResponse } from "../types";
import { STATUS_LABEL, bestEntry, fmt, heatStyle } from "../utils";

interface Person { id: number; name: string; role: string | null; status: string; scores: Record<number, number>; ranks: Record<number, number>; best: [number, number] | null; strong: number }
type SortKey = "best" | "name" | number;

export default function Matrix() {
  const nav = useNavigate();
  const { blind, setJobId } = useApp();
  const { toast } = useToast();
  const [exporting, setExporting] = useState(false);
  const [q, setQ] = useState("");
  const [minBest, setMinBest] = useState(0);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "best", dir: -1 });

  const data = useAsync(async () => {
    const jobs = (await api.get<Paged<Job>>("/jobs?page_size=100")).data.items;
    const per = await Promise.all(jobs.map(async (job) => {
      try { return { job, items: (await api.get<ResultsResponse>(`/matching/results/${job.id}`, { params: { page_size: 100, blind } })).data.items }; }
      catch { return { job, items: [] as ResultRow[] }; }   // job without a ranking run yet
    }));
    const map = new Map<number, Person>();
    for (const { job, items } of per) {
      for (const r of items) {
        const p = map.get(r.candidate_id) ?? { id: r.candidate_id, name: r.name, role: r.latest_role, status: r.review_status, scores: {}, ranks: {}, best: null, strong: 0 };
        p.scores[job.id] = r.overall; p.ranks[job.id] = r.rank; map.set(r.candidate_id, p);
      }
    }
    const people = [...map.values()].map((p) => ({ ...p, best: bestEntry(p.scores), strong: Object.values(p.scores).filter((s) => s >= 50).length }));
    return { jobs: per.filter((x) => x.items.length > 0).map((x) => x.job), people };
  }, [blind]);

  const jobs = data.data?.jobs ?? [];
  const title = (id: number) => jobs.find((j) => j.id === id)?.title ?? `Job ${id}`;
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    const list = (data.data?.people ?? []).filter((p) => (!t || `${p.name} ${p.role ?? ""}`.toLowerCase().includes(t)) && (p.best?.[1] ?? 0) >= minBest);
    const val = (p: Person) => (sort.key === "best" ? p.best?.[1] ?? -1 : typeof sort.key === "number" ? p.scores[sort.key] ?? -1 : 0);
    return list.sort((a, b) => (sort.key === "name" ? a.name.localeCompare(b.name) * sort.dir : (val(a) - val(b)) * sort.dir));
  }, [data.data, q, minBest, sort]);

  const topPicks = useMemo(() => jobs.map((j) => {
    const top = (data.data?.people ?? []).filter((p) => p.scores[j.id] !== undefined).sort((a, b) => b.scores[j.id] - a.scores[j.id])[0];
    return { job: j, top };
  }), [jobs, data.data]);
  const strongAnywhere = (data.data?.people ?? []).filter((p) => (p.best?.[1] ?? 0) >= 70).length;
  const versatile = [...(data.data?.people ?? [])].sort((a, b) => b.strong - a.strong || (b.best?.[1] ?? 0) - (a.best?.[1] ?? 0))[0];

  const sortBy = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: key === "name" ? 1 : -1 }));
  const open = (p: Person, jobId: number) => { setJobId(jobId); nav(`/candidates/${p.id}`); };
  /** Exports exactly what is on screen: the filtered candidates, in the current sort order. */
  const exportExcel = async () => {
    setExporting(true);
    try {
      await download(`/reports/matrix/excel?blind=${blind}&ids=${rows.map((p) => p.id).join(",")}`, "talentiq_talent_matrix.xlsx");
      toast(`Exported ${rows.length} candidate${rows.length === 1 ? "" : "s"} across ${jobs.length} job${jobs.length === 1 ? "" : "s"} to Excel (current filters and sort).`);
    } catch (e) { toast(errMsg(e), { kind: "error" }); } finally { setExporting(false); }
  };

  if (data.loading) return <Spinner label="Scoring every candidate against every job…" />;
  return (
    <div>
      <PageTitle title="Talent matrix" sub="Every candidate scored against every job at a glance. Spot each person’s best fit and who is versatile. Click a cell to open that candidate for that job.">
        {jobs.length > 0 && <button className="btn-ghost" disabled={exporting || rows.length === 0} onClick={exportExcel} title="Download the candidates currently shown, in the current order, as an Excel workbook"><Download className="h-4 w-4" />{exporting ? "Exporting…" : "Export Excel"}</button>}
      </PageTitle>
      {data.error && <ErrorBox message={data.error} onRetry={data.reload} />}
      {!jobs.length ? <div className="card"><Empty>No job has a ranking run yet. Open the Ranking page and run matching for at least one job.</Empty></div> : (<>
        <div className="mb-5 grid gap-3 md:grid-cols-3">
          <div className="card flex items-center gap-3 p-4"><span className="icon-chip shrink-0"><Flame className="h-5 w-5" /></span><div><div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Strong fit somewhere</div><div className="text-2xl font-extrabold text-slate-900">{strongAnywhere}<span className="ml-1 text-sm font-medium text-slate-500">of {data.data?.people.length} score ≥ 70</span></div></div></div>
          <div className="card flex items-center gap-3 p-4"><span className="icon-chip shrink-0"><Zap className="h-5 w-5" /></span><div className="min-w-0"><div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Most versatile</div>{versatile && <><div className="truncate text-xl font-extrabold text-slate-900">{versatile.name}</div><div className="text-sm font-medium text-slate-500">score ≥ 50 in {versatile.strong} of {jobs.length} jobs</div></>}</div></div>
          <div className="card flex items-center gap-3 p-4"><span className="icon-chip shrink-0"><Crown className="h-5 w-5" /></span><div><div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Jobs covered</div><div className="text-2xl font-extrabold text-slate-900">{jobs.length}<span className="ml-1 text-sm font-medium text-slate-500">with a ranking</span></div></div></div>
        </div>

        <div className="mb-3 flex flex-wrap items-end gap-3">
          <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input aria-label="Filter candidates" className="input w-60 pl-9" placeholder="Filter by name or role" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <div className="w-56"><label className="label" htmlFor="mb">Best score at least: {minBest}</label><input id="mb" type="range" min={0} max={90} step={5} value={minBest} onChange={(e) => setMinBest(Number(e.target.value))} className="w-full" /></div>
          <div className="ml-auto flex items-center gap-2 text-xs text-slate-500"><span>0</span><span className="h-2.5 w-32 rounded-full" style={{ background: "linear-gradient(90deg, rgba(91,63,232,0.06), rgba(91,63,232,0.92))" }} aria-hidden /><span>100</span></div>
        </div>

        <div className="card overflow-x-auto">
          <table className="w-full min-w-[56rem] border-separate border-spacing-0 text-sm">
            <thead><tr>
              <th className="th sticky left-0 z-10 min-w-[12rem] border-b border-slate-200"><button className="inline-flex items-center gap-1 font-bold uppercase" onClick={() => sortBy("name")}>Candidate <ArrowUpDown className="h-3 w-3" /></button></th>
              {jobs.map((j) => <th key={j.id} className="th min-w-[7rem] border-b border-slate-200 text-center normal-case"><button className="inline-flex items-center gap-1 font-bold" title={`Sort by ${j.title}`} onClick={() => sortBy(j.id)}><span className="line-clamp-2 max-w-[6.5rem]">{j.title}</span><ArrowUpDown className="h-3 w-3 shrink-0" /></button></th>)}
              <th className="th min-w-[11rem] border-b border-slate-200"><button className="inline-flex items-center gap-1 font-bold uppercase" onClick={() => sortBy("best")}>Best fit <ArrowUpDown className="h-3 w-3" /></button></th>
            </tr></thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="group">
                  <td className="sticky left-0 z-10 border-b border-slate-100 bg-white px-3 py-2 group-hover:bg-brand-50"><Link to={`/candidates/${p.id}`} onClick={() => p.best && setJobId(p.best[0])} className="block truncate font-semibold text-brand-700 hover:underline">{p.name}</Link><div className="truncate text-xs text-slate-500">{p.role ?? "No role extracted"} · {STATUS_LABEL[p.status] ?? p.status}</div></td>
                  {jobs.map((j) => {
                    const s = p.scores[j.id];
                    const isBest = p.best?.[0] === j.id;
                    return <td key={j.id} className="border-b border-slate-100 p-1 text-center">
                      <button title={s === undefined ? "No score" : `${p.name} · ${j.title}: ${fmt(s)} (rank #${p.ranks[j.id]})`} onClick={() => open(p, j.id)} style={heatStyle(s)}
                        className={`h-9 w-full rounded-lg text-sm font-semibold tabular-nums transition hover:scale-105 hover:shadow-md ${isBest ? "ring-2 ring-amber-400 ring-offset-1" : ""}`}>{s === undefined ? "—" : fmt(s, 0)}</button></td>;
                  })}
                  <td className="border-b border-slate-100 px-3 py-2">{p.best ? <><div className="truncate font-medium text-slate-800">{title(p.best[0])}</div><div className="text-xs text-slate-500">score {fmt(p.best[1])} · rank #{p.ranks[p.best[0]]}</div></> : "—"}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={jobs.length + 2}><Empty>No candidates match these filters.</Empty></td></tr>}
            </tbody>
          </table>
        </div>

        <h2 className="mb-3 mt-8 text-lg font-bold text-slate-900">Top pick per job</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {topPicks.map(({ job, top }) => (
            <button key={job.id} className="card card-hover p-4 text-left" onClick={() => top && open(top, job.id)}>
              <div className="truncate text-xs font-bold uppercase tracking-wider text-slate-500">{job.title}</div>
              {top ? <div className="mt-1 flex items-baseline justify-between gap-2"><span className="truncate text-base font-bold text-slate-900">{top.name}</span><span className="rounded-full px-2.5 py-0.5 text-sm font-bold" style={heatStyle(top.scores[job.id])}>{fmt(top.scores[job.id])}</span></div> : <div className="mt-1 text-sm text-slate-500">No ranking yet</div>}
            </button>
          ))}
        </div>
      </>)}
    </div>
  );
}
