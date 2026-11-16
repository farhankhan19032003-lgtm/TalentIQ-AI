import { useSearchParams, Link } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import { Empty, ErrorBox, MatchTag, PageTitle, ScoreBadge, Spinner } from "../components/ui";
import { ResultRow, Requirement, RunInfo } from "../types";
import { COMP_LABEL, fmt } from "../utils";

export default function Compare() {
  const { jobId, blind } = useApp();
  const [sp] = useSearchParams();
  const ids = sp.get("ids") ?? "";
  const { data, error, loading } = useAsync(() => (jobId && ids ? api.get<{ run: RunInfo; requirements: Requirement[]; candidates: ResultRow[] }>("/matching/compare", { params: { job_id: jobId, ids, blind } }).then((r) => r.data) : Promise.resolve(null)), [jobId, ids, blind]);
  if (!jobId || !ids) return <div><PageTitle title="Compare" /><div className="card"><Empty>Select 2–5 candidates on the <Link className="font-semibold text-brand-600 underline underline-offset-2" to="/ranking">ranking page</Link>.</Empty></div></div>;
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} />;
  if (!data) return null;
  return (
    <div>
      <PageTitle title="Compare candidates" sub="Side-by-side scores and requirement evidence." />
      <div className="card overflow-x-auto"><table className="w-full">
        <thead className="border-b border-slate-200"><tr><th className="th">&nbsp;</th>{data.candidates.map((c) => <th key={c.candidate_id} className="th"><Link className="text-brand-700 normal-case" to={`/candidates/${c.candidate_id}`}>#{c.rank} {c.name}</Link></th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">
          <tr><td className="td font-medium">Overall</td>{data.candidates.map((c) => <td key={c.candidate_id} className="td"><ScoreBadge score={c.overall} low={c.score_low} high={c.score_high} /></td>)}</tr>
          {Object.keys(COMP_LABEL).map((k) => <tr key={k}><td className="td">{COMP_LABEL[k]}</td>{data.candidates.map((c) => <td key={c.candidate_id} className="td tabular-nums">{c.components[k]?.score == null ? "n/v" : fmt(c.components[k].score)}</td>)}</tr>)}
          <tr><td className="td">Relevant / total experience</td>{data.candidates.map((c) => <td key={c.candidate_id} className="td">{fmt(c.relevant_years)} / {fmt(c.total_years)} y</td>)}</tr>
          <tr><td className="td">Confidence</td>{data.candidates.map((c) => <td key={c.candidate_id} className="td">{fmt(c.confidence, 0)}%</td>)}</tr>
          <tr className="bg-slate-50"><td className="td font-semibold" colSpan={data.candidates.length + 1}>Requirements</td></tr>
          {data.requirements.filter((r) => r.importance !== "ignored").map((rq) => (
            <tr key={rq.id}><td className="td">{rq.name}<span className="ml-1 text-xs text-slate-400">{rq.importance}</span></td>
              {data.candidates.map((c) => { const m = c.requirements.find((x) => (x.requirement_id ? x.requirement_id === rq.id : x.name === rq.name)); return <td key={c.candidate_id} className="td">{m ? <MatchTag type={m.match_type} /> : "—"}</td>; })}</tr>))}
        </tbody></table></div>
    </div>
  );
}
