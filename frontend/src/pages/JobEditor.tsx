import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Plus, Trash2 } from "lucide-react";
import { api, errMsg } from "../api";
import { useApp } from "../ctx";
import { Chip, ErrorBox, PageTitle, Spinner } from "../components/ui";
import { Job, Requirement } from "../types";

export default function JobEditor() {
  const { id } = useParams();
  const nav = useNavigate();
  const { setJobId } = useApp();
  const editing = !!id;
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [minYears, setMinYears] = useState<string>("");
  const [reqs, setReqs] = useState<Requirement[] | null>(null);
  const [extraMust, setExtraMust] = useState("");
  const [extraOpt, setExtraOpt] = useState("");
  const [analysis, setAnalysis] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(editing);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!editing) return;
    api.get<Job>(`/jobs/${id}`).then((r) => {
      const j = r.data; setTitle(j.title); setDesc(j.description); setReqs(j.requirements); setAnalysis(j.analysis);
      setMinYears(j.min_experience_years ? String(j.min_experience_years) : "");
    }).catch((e) => setErr(errMsg(e))).finally(() => setLoading(false));
  }, [id, editing]);

  const analyse = async () => {
    setErr(null); setBusy(true);
    try { const a = (await api.post("/jobs/analyze", { title: title || undefined, description: desc })).data; setAnalysis(a); setReqs(a.requirements); if (a.experience.min_years) setMinYears(String(a.experience.min_years)); if (!title && a.title) setTitle(a.title); }
    catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };
  const uploadJd = async (f: File) => {
    setErr(null); const fd = new FormData(); fd.append("file", f);
    try {
      const r = (await api.post("/jobs/extract-text", fd)).data;
      setDesc(r.text); setAnalysis(r.analysis); setReqs(r.analysis.requirements);
      if (!title && r.analysis.title) setTitle(r.analysis.title);                               // same as "Analyse": Save stays disabled without a title
      if (r.analysis.experience.min_years) setMinYears(String(r.analysis.experience.min_years));
    } catch (e) { setErr(errMsg(e)); }
  };
  const setImp = (i: number, imp: Requirement["importance"]) => setReqs((rs) => rs!.map((r, k) => (k === i ? { ...r, importance: imp } : r)));
  const addCustom = (name: string, imp: "must" | "preferred") => {
    const n = name.trim(); if (!n) return;
    setReqs((rs) => [...(rs ?? []), { id: `custom_${n.toLowerCase().replace(/\W+/g, "_")}`, name: n, category: "Custom", importance: imp, weight: imp === "must" ? 1 : 0.5, custom: true }]);
  };
  const save = async () => {
    setErr(null); setBusy(true);
    const body: any = { title, description: desc, min_experience_years: minYears ? Number(minYears) : undefined };
    try {
      if (editing) { body.requirements = reqs; await api.put(`/jobs/${id}`, body); nav("/jobs"); }
      else {
        body.required_skills = extraMust.split(",").map((s) => s.trim()).filter(Boolean);
        body.optional_skills = extraOpt.split(",").map((s) => s.trim()).filter(Boolean);
        const j = (await api.post<Job>("/jobs", body)).data;
        if (reqs && reqs.some((r) => r.importance === "ignored")) { await api.put(`/jobs/${j.id}`, { title, description: desc, requirements: reqs }); }
        setJobId(j.id);   // the job just created becomes the active one, so Upload / Ranking work on it right away
        nav("/jobs");
      }
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };
  if (loading) return <Spinner />;
  return (
    <div>
      <PageTitle title={editing ? "Edit job" : "New job"} sub="Paste or upload a JD, review the extracted requirements, and adjust importance before saving." />
      {err && <div className="mb-3"><ErrorBox message={err} /></div>}
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card space-y-3 p-5">
          <div><label className="label" htmlFor="t">Job title</label><input id="t" className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
          <div><label className="label" htmlFor="d">Job description</label>
            <textarea id="d" className="input h-72 font-mono text-xs" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder={"Job Title: …\nRequirements:\n- Python, FastAPI\n- 3+ years of experience\nNice to have:\n- Kubernetes"} /></div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="btn-ghost cursor-pointer">Upload JD (.pdf/.docx/.txt)<input type="file" hidden accept=".pdf,.docx,.txt" onChange={(e) => e.target.files?.[0] && uploadJd(e.target.files[0])} /></label>
            <button className="btn-ghost" disabled={desc.length < 20 || busy} onClick={analyse}>Analyse requirements</button>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><label className="label" htmlFor="my">Min. years</label><input id="my" type="number" min={0} step={0.5} className="input" value={minYears} onChange={(e) => setMinYears(e.target.value)} /></div>
            {!editing && <><div><label className="label" htmlFor="em">Extra must-have</label><input id="em" className="input" placeholder="SQL, Docker" value={extraMust} onChange={(e) => setExtraMust(e.target.value)} /></div>
              <div><label className="label" htmlFor="eo">Extra preferred</label><input id="eo" className="input" placeholder="Redis" value={extraOpt} onChange={(e) => setExtraOpt(e.target.value)} /></div></>}
          </div>
        </div>
        <div className="card p-5">
          <h2 className="mb-2 font-semibold">Extracted requirements {reqs && <span className="text-sm font-normal text-slate-500">({reqs.length})</span>}</h2>
          {!reqs ? <p className="text-sm text-slate-500">Click “Analyse requirements” to preview what the system understood. Nothing is hidden: you can change every importance level.</p> : (
            <>
              <ul className="max-h-[26rem] divide-y divide-slate-100 overflow-auto">
                {reqs.map((r, i) => (
                  <li key={r.id} className="flex items-center gap-2 py-1.5 text-sm">
                    <span className="flex-1">{r.name}<span className="ml-2 text-xs text-slate-400">{r.category}</span>{r.any_of && <span className="ml-1"><Chip tone="blue">any of</Chip></span>}</span>
                    <select aria-label={`Importance of ${r.name}`} className="input w-32" value={r.importance} onChange={(e) => setImp(i, e.target.value as Requirement["importance"])}>
                      <option value="must">Must-have</option><option value="preferred">Preferred</option><option value="ignored">Ignore</option>
                    </select>
                    <button aria-label={`Remove ${r.name}`} className="text-slate-400 hover:text-red-600" onClick={() => setReqs(reqs.filter((_, k) => k !== i))}><Trash2 className="h-4 w-4" /></button>
                  </li>
                ))}
              </ul>
              <CustomAdder onAdd={addCustom} />
              {analysis && <p className="mt-3 text-xs text-slate-500">Experience: {analysis.experience.min_years ? `${analysis.experience.min_years}+ years required` : "no minimum stated"} · Education: {analysis.education.required_label || "not specified"}</p>}
            </>
          )}
        </div>
      </div>
      <div className="mt-5 flex gap-2"><button className="btn-primary" disabled={busy || title.trim().length < 3 || desc.length < 20} onClick={save}>{busy ? "Saving…" : "Save job"}</button><button className="btn-ghost" onClick={() => nav("/jobs")}>Cancel</button></div>
    </div>
  );
}
function CustomAdder({ onAdd }: { onAdd: (n: string, i: "must" | "preferred") => void }) {
  const [n, setN] = useState(""); const [i, setI] = useState<"must" | "preferred">("must");
  return (
    <div className="mt-3 flex gap-2">
      <input className="input" aria-label="Add custom requirement" placeholder="Add a requirement…" value={n} onChange={(e) => setN(e.target.value)} />
      <select className="input w-32" aria-label="Custom importance" value={i} onChange={(e) => setI(e.target.value as "must" | "preferred")}><option value="must">Must-have</option><option value="preferred">Preferred</option></select>
      <button className="btn-ghost" onClick={() => { onAdd(n, i); setN(""); }}><Plus className="h-4 w-4" />Add</button>
    </div>
  );
}
