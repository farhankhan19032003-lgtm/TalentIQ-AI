import { useState } from "react";
import { api, errMsg } from "../api";
import { useAsync } from "../hooks";
import { ErrorBox, PageTitle, Pager, Spinner } from "../components/ui";
import { Settings } from "../types";
import { COMP_LABEL } from "../utils";

export default function SettingsPage() {
  const s = useAsync(() => api.get<Settings>("/settings").then((r) => r.data), []);
  const [page, setPage] = useState(1);
  const audit = useAsync(() => api.get("/audit", { params: { page, page_size: 20 } }).then((r) => r.data), [page]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const purge = async () => {
    if (!confirm(`Delete all resumes older than ${s.data?.retention_days} days? This cannot be undone.`)) return;
    try { const r = await api.post(`/admin/retention/run`); setMsg(`Deleted ${r.data.deleted} expired resume(s).`); audit.reload(); } catch (e) { setErr(errMsg(e)); }
  };
  if (s.loading) return <Spinner />;
  return (
    <div>
      <PageTitle title="Settings & audit" sub="Transparent configuration and a PII-free audit trail." />
      {(s.error || err) && <ErrorBox message={(s.error || err)!} />}
      {s.data && (
        <div className="grid gap-5 lg:grid-cols-2">
          <section className="card p-5"><h2 className="mb-2 font-semibold">Scoring</h2><p className="mb-2 rounded bg-slate-50 p-2 font-mono text-xs">{s.data.formula}</p>
            <ul className="text-sm">{Object.entries(s.data.default_weights).map(([k, v]) => <li key={k}>{COMP_LABEL[k]}: <strong>{Math.round(v * 100)}%</strong></li>)}</ul>
            <p className="mt-2 text-xs text-slate-500">Algorithm v{s.data.algorithm_version} · ontology v{s.data.ontology.version} ({s.data.ontology.skills} skills) · embeddings: {s.data.embedding_backend}</p></section>
          <section className="card p-5"><h2 className="mb-2 font-semibold">Privacy & limits</h2>
            <ul className="space-y-1 text-sm"><li>Max upload: {s.data.max_upload_mb} MB · {s.data.max_batch_files} files/batch</li><li>Retention: {s.data.retention_days} days</li><li>Original files stored: {s.data.store_original_files ? "yes" : "no"}</li></ul>
            <button className="btn-danger mt-3" onClick={purge}>Run retention purge</button>{msg && <p className="mt-2 text-sm text-emerald-700">{msg}</p>}</section>
        </div>)}
      <section className="card mt-5">
        <h2 className="p-5 pb-2 font-semibold">Audit log</h2>
        {audit.loading ? <Spinner /> : <><table className="w-full"><thead><tr><th className="th">Time (UTC)</th><th className="th">Actor</th><th className="th">Action</th><th className="th">Entity</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{audit.data?.items.map((a: any) => <tr key={a.id}><td className="td">{a.ts.slice(0, 19).replace("T", " ")}</td><td className="td">{a.actor}</td><td className="td">{a.action}</td><td className="td">{a.entity_type} {a.entity_id ?? ""}</td></tr>)}</tbody></table>
          <Pager page={page} pageSize={20} total={audit.data?.total ?? 0} onPage={setPage} /></>}
      </section>
    </div>
  );
}
