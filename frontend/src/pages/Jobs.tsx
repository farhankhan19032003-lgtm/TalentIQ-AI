import { Link, useNavigate } from "react-router-dom";
import { api, errMsg } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import { Chip, Empty, ErrorBox, PageTitle, Spinner } from "../components/ui";
import { Job, Paged } from "../types";
import { useState } from "react";

export default function Jobs() {
  const nav = useNavigate();
  const { setJobId } = useApp();
  const { data, error, loading, reload } = useAsync(() => api.get<Paged<Job>>("/jobs?page_size=100").then((r) => r.data), []);
  const [err, setErr] = useState<string | null>(null);
  const del = async (j: Job) => {
    if (!confirm(`Delete job "${j.title}" and its ranking runs? Candidates are kept.`)) return;
    try { await api.delete(`/jobs/${j.id}`); reload(); } catch (e) { setErr(errMsg(e)); }
  };
  return (
    <div>
      <PageTitle title="Jobs" sub="Job descriptions are analysed into editable requirements.">
        <Link className="btn-primary" to="/jobs/new">New job</Link>
      </PageTitle>
      {(error || err) && <ErrorBox message={(error || err)!} onRetry={reload} />}
      {loading ? <Spinner /> : !data?.items.length ? <Empty>No jobs yet. Create one by pasting or uploading a job description.</Empty> : (
        <div className="card overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-slate-200"><tr><th className="th">Title</th><th className="th">Must-have</th><th className="th">Preferred</th><th className="th">Min. exp.</th><th className="th" /></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((j) => (
                <tr key={j.id}>
                  <td className="td font-medium">{j.title}{j.is_template && <span className="ml-2"><Chip>template</Chip></span>}</td>
                  <td className="td">{j.requirements.filter((r) => r.importance === "must").length}</td>
                  <td className="td">{j.requirements.filter((r) => r.importance === "preferred").length}</td>
                  <td className="td">{j.min_experience_years ? `${j.min_experience_years}+ y` : "—"}</td>
                  <td className="td flex justify-end gap-2">
                    <button className="btn-primary" onClick={() => { setJobId(j.id); nav("/ranking"); }}>Rank</button>
                    <Link className="btn-ghost" to={`/jobs/${j.id}`}>Edit</Link>
                    <button className="btn-danger" onClick={() => del(j)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
