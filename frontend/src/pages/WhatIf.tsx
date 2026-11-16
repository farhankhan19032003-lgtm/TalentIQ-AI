import { useEffect, useState } from "react";
import { api, errMsg } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import WeightsPanel from "../components/WeightsPanel";
import { Empty, ErrorBox, PageTitle } from "../components/ui";
import { Job, Settings, WhatIfResponse } from "../types";
import { fmt, weightsValid } from "../utils";

export default function WhatIf() {
  const { jobId } = useApp();
  const settings = useAsync(() => api.get<Settings>("/settings").then((r) => r.data), []);
  const job = useAsync(() => (jobId ? api.get<Job>(`/jobs/${jobId}`).then((r) => r.data) : Promise.resolve(null)), [jobId]);
  const [w, setW] = useState<Record<string, number> | null>(null);
  const [minYears, setMinYears] = useState("");
  const [extra, setExtra] = useState("");
  const [imp, setImp] = useState<Record<string, string>>({});
  const [out, setOut] = useState<WhatIfResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (settings.data && !w) setW({ ...settings.data.default_weights }); }, [settings.data, w]);

  if (!jobId) return <div><PageTitle title="What-if simulation" /><Empty>Select an active job first.</Empty></div>;
  const simulate = async () => {
    if (!w || !weightsValid(w)) { setErr("Weights must add up to 100%."); return; }
    setBusy(true); setErr(null);
    try {
      const body: any = { weights: w, requirement_changes: Object.entries(imp).map(([id, importance]) => ({ id, importance })) };
      if (minYears) body.min_years = Number(minYears);
      const add = extra.split(",").map((s) => s.trim()).filter(Boolean);
      if (add.length) body.add_requirements = add.map((name) => ({ name, importance: "must" }));
      setOut((await api.post<WhatIfResponse>(`/matching/whatif/${jobId}`, body)).data);
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div>
      <PageTitle title="What-if simulation" sub="Preview how rankings would change. Nothing is saved or altered." />
      {(err || job.error) && <div className="mb-3"><ErrorBox message={(err || job.error)!} /></div>}
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card space-y-4 p-5">
          <h2 className="font-semibold">Scenario</h2>
          {w && settings.data && <WeightsPanel value={w} onChange={setW} defaults={settings.data.default_weights} />}
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label" htmlFor="wy">Minimum years</label><input id="wy" type="number" className="input" value={minYears} onChange={(e) => setMinYears(e.target.value)} placeholder={String(job.data?.min_experience_years ?? "")} /></div>
            <div><label className="label" htmlFor="wa">Add must-have skills</label><input id="wa" className="input" value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Kubernetes, Terraform" /></div>
          </div>
          <div><div className="label">Change requirement importance</div>
            <ul className="max-h-48 divide-y divide-slate-100 overflow-auto">{job.data?.requirements.map((r) => (
              <li key={r.id} className="flex items-center justify-between py-1 text-sm"><span>{r.name}</span>
                <select aria-label={`Importance of ${r.name}`} className="input w-32" value={imp[r.id] ?? r.importance} onChange={(e) => setImp({ ...imp, [r.id]: e.target.value })}><option value="must">Must-have</option><option value="preferred">Preferred</option><option value="ignored">Ignore</option></select></li>))}</ul></div>
          <button className="btn-primary" disabled={busy} onClick={simulate}>{busy ? "Simulating…" : "Run simulation"}</button>
        </div>
        <div className="card p-5">
          <h2 className="mb-2 font-semibold">Result</h2>
          {!out ? <p className="text-sm text-slate-500">Adjust the scenario and run the simulation.</p> : (<>
            <p className="mb-2 text-xs text-slate-500">{out.note} Persisted: {out.persisted ? "yes" : "no"}.</p>
            <div className="max-h-[32rem] overflow-auto"><table className="w-full"><thead><tr><th className="th">Candidate</th><th className="th">Rank</th><th className="th">Score</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{[...out.rows].sort((a, b) => a.simulated_rank - b.simulated_rank).map((r) => (
                <tr key={r.candidate_id}><td className="td">{r.name}</td>
                  <td className="td tabular-nums">{r.simulated_rank} <span className={r.rank_change > 0 ? "text-emerald-600" : r.rank_change < 0 ? "text-red-600" : "text-slate-400"}>{r.rank_change > 0 ? `▲${r.rank_change}` : r.rank_change < 0 ? `▼${-r.rank_change}` : "–"}</span></td>
                  <td className="td tabular-nums">{fmt(r.simulated_score)} <span className="text-xs text-slate-400">({r.score_change >= 0 ? "+" : ""}{fmt(r.score_change)})</span></td></tr>))}</tbody></table></div></>)}
        </div>
      </div>
    </div>
  );
}
