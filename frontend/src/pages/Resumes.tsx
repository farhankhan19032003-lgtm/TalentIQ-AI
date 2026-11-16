import { useState } from "react";
import { api, errMsg } from "../api";
import { useAsync } from "../hooks";
import { Chip, Empty, ErrorBox, PageTitle, Pager, Spinner, Stat } from "../components/ui";
import { Paged, ResumeRow } from "../types";

export default function Resumes() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const list = useAsync(() => api.get<Paged<ResumeRow>>("/resumes", { params: { page, page_size: 20, status: status || undefined } }).then((r) => r.data), [page, status]);
  const stats = useAsync(() => api.get("/resumes/stats").then((r) => r.data), []);
  const retry = async (id: number) => { try { await api.post(`/resumes/${id}/retry`); list.reload(); stats.reload(); } catch (e) { setErr(errMsg(e)); } };
  const del = async (r: ResumeRow) => {
    if (!confirm(`Permanently delete ${r.filename} and all extracted data?`)) return;
    try { r.candidate_id ? await api.delete(`/candidates/${r.candidate_id}`) : await api.delete(`/resumes/${r.id}`); list.reload(); stats.reload(); } catch (e) { setErr(errMsg(e)); }
  };
  return (
    <div>
      <PageTitle title="Resume batches" sub="Parsing status, failures and privacy-aware deletion." />
      {stats.data && <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Total" value={stats.data.total} /><Stat label="Parsed" value={stats.data.parsed} /><Stat label="Failed" value={stats.data.failed} />
        <Stat label="Parse success" value={`${stats.data.success_rate ?? 0}%`} hint={Object.entries(stats.data.failures_by_reason ?? {}).map(([k, v]) => `${k}: ${v}`).join(", ")} /></div>}
      {(list.error || err) && <ErrorBox message={(list.error || err)!} onRetry={list.reload} />}
      <div className="mb-3 flex items-center gap-2"><label className="label !mb-0" htmlFor="st">Status</label>
        <select id="st" className="input w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All</option><option value="parsed">Parsed</option><option value="failed">Failed</option><option value="rejected">Rejected</option><option value="duplicate">Duplicate</option></select></div>
      {list.loading ? <Spinner /> : !list.data?.items.length ? <Empty>No resumes found.</Empty> : (
        <div className="card overflow-x-auto"><table className="w-full">
          <thead className="border-b border-slate-200"><tr><th className="th">File</th><th className="th">Type</th><th className="th">Status</th><th className="th">Pages</th><th className="th">Parse ms</th><th className="th">Note</th><th className="th" /></tr></thead>
          <tbody className="divide-y divide-slate-100">{list.data.items.map((r) => (
            <tr key={r.id}><td className="td">{r.filename}</td><td className="td uppercase">{r.file_type}</td>
              <td className="td"><Chip tone={r.status === "parsed" ? "green" : r.status === "duplicate" ? "amber" : "red"}>{r.status}</Chip></td>
              <td className="td">{r.page_count ?? "—"}</td><td className="td">{r.processing_ms ?? "—"}</td><td className="td text-slate-600">{r.error_message ?? ""}</td>
              <td className="td flex justify-end gap-2">{r.status === "failed" && <button className="btn-ghost" onClick={() => retry(r.id)}>Retry</button>}<button className="btn-danger" onClick={() => del(r)}>Delete</button></td></tr>))}
          </tbody></table>
          <Pager page={page} pageSize={20} total={list.data.total} onPage={setPage} /></div>
      )}
    </div>
  );
}
