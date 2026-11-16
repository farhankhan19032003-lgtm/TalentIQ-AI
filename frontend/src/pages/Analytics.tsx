import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import { Empty, ErrorBox, PageTitle, Spinner, Stat } from "../components/ui";
import { fmt } from "../utils";

const Panel = ({ title, children, note }: { title: string; children: React.ReactNode; note?: string }) => (
  <section className="card p-5"><h2 className="font-semibold">{title}</h2>{note && <p className="mb-2 text-xs text-slate-500">{note}</p>}<div className="mt-2 h-64">{children}</div></section>
);
const Bars = ({ data, x, y, color = "#4f46e5", layout = "horizontal" }: { data: any[]; x: string; y: string; color?: string; layout?: "horizontal" | "vertical" }) => (
  <ResponsiveContainer><BarChart data={data} layout={layout} margin={{ left: layout === "vertical" ? 40 : 0 }}><CartesianGrid strokeDasharray="3 3" />
    {layout === "vertical" ? <><XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey={x} width={110} tick={{ fontSize: 11 }} interval={0} /></> : <><XAxis dataKey={x} tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /></>}
    <Tooltip /><Bar dataKey={y} fill={color} /></BarChart></ResponsiveContainer>
);

export default function Analytics() {
  const { jobId } = useApp();
  const a = useAsync(() => (jobId ? api.get(`/analytics/${jobId}`).then((r) => r.data) : Promise.resolve(null)), [jobId]);
  const pool = useAsync(() => api.get("/analytics/talent-pool/overview", { params: { job_id: jobId ?? undefined } }).then((r) => r.data), [jobId]);
  if (a.loading || pool.loading) return <Spinner />;
  const err = a.error || pool.error;
  return (
    <div>
      <PageTitle title="Analytics" sub="Computed from stored results only — no estimated numbers." />
      {err && <ErrorBox message={err} />}
      {jobId && a.data?.has_run && (<>
        <div className="mb-5 grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat label="Candidates" value={a.data.summary.total_candidates} /><Stat label="Average score" value={fmt(a.data.summary.average_score)} />
          <Stat label="High matches" value={a.data.summary.high_matching} /><Stat label="Parse success" value={`${a.data.parsing.success_rate}%`} hint={`${a.data.parsing.failed} failed`} />
        </div>
        <div className="grid gap-5 lg:grid-cols-2">
          <Panel title="Score distribution"><Bars data={a.data.score_distribution} x="bucket" y="count" /></Panel>
          <Panel title="Experience distribution (years)"><Bars data={a.data.experience_distribution} x="bucket" y="count" color="#0891b2" /></Panel>
          <Panel title="Most common matched skills"><Bars layout="vertical" data={a.data.top_matching_skills.slice(0, 10)} x="skill" y="count" color="#059669" /></Panel>
          <Panel title="Most missing required skills" note="Counts candidates with no evidence for the skill."><Bars layout="vertical" data={a.data.most_missing_skills.slice(0, 10)} x="skill" y="count" color="#dc2626" /></Panel>
          <section className="card p-5 lg:col-span-2"><h2 className="mb-2 font-semibold">Requirement coverage across candidates</h2>
            <div style={{ height: Math.max(320, a.data.requirement_coverage.length * 34 + 70) }}><ResponsiveContainer><BarChart data={a.data.requirement_coverage} layout="vertical" margin={{ left: 60 }}><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="requirement" width={130} tick={{ fontSize: 11 }} interval={0} /><Tooltip /><Legend />
              <Bar dataKey="exact_or_synonym" name="Exact/synonym" stackId="a" fill="#059669" /><Bar dataKey="related" name="Related" stackId="a" fill="#f59e0b" /><Bar dataKey="semantic" name="Semantic only" stackId="a" fill="#38bdf8" /><Bar dataKey="no_evidence" name="No evidence" stackId="a" fill="#fca5a5" /></BarChart></ResponsiveContainer></div></section>
        </div></>)}
      {jobId && a.data && !a.data.has_run && <Empty>No ranking run for this job yet — analytics appear after you run matching.</Empty>}
      {!jobId && <p className="mb-4 text-sm text-slate-500">Select a job in the top bar for job-specific analytics. Talent-pool analytics are shown below.</p>}
      {pool.data && (
        <section className="mt-8"><h2 className="mb-3 text-lg font-semibold">Talent pool ({pool.data.total_candidates} candidates)</h2>
          {pool.data.total_candidates === 0 ? <Empty>No candidates yet.</Empty> : <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Most common skills in the pool"><Bars layout="vertical" data={pool.data.common_skills.slice(0, 12)} x="skill" y="count" color="#7c3aed" /></Panel>
            <Panel title="Rare skills (appear once)"><div className="h-full overflow-auto text-sm">{pool.data.rare_skills.slice(0, 60).map((s: any) => <span key={s.skill} className="mr-1.5 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs">{s.skill}</span>)}</div></Panel>
            {pool.data.job_coverage?.length > 0 && <section className="card p-5 lg:col-span-2"><h2 className="mb-2 font-semibold">Pool coverage of this job's requirements</h2><ul className="grid gap-1 text-sm md:grid-cols-2">{pool.data.job_coverage.map((c: any) => <li key={c.requirement}>{c.requirement} — <strong>{c.candidates_with_evidence}</strong> of {c.total} candidates have evidence</li>)}</ul></section>}
            <p className="text-xs text-slate-500 lg:col-span-2">{pool.data.availability.note}</p></div>}
        </section>)}
    </div>
  );
}
