import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { api } from "../api";
import { Accounting, Pool } from "../types";

/** Accounts for every uploaded file next to the ranking, and warns when the ranking is older than the resume pool. */
export default function PoolBanner({ pool, jobId, onRerun }: { pool: Pool; jobId: number | null; onRerun: () => void }) {
  const [acc, setAcc] = useState<Accounting | null>(null);
  const [open, setOpen] = useState(false);
  const toggle = async () => {
    if (!open && !acc) setAcc((await api.get<Accounting>("/resumes/accounting", { params: { job_id: jobId } })).data);
    setOpen(!open);
  };
  return (
    <div className="card mb-4 p-4 text-sm" data-testid="pool-banner">
      {pool.run_is_stale && (
        <div role="alert" className="mb-3 flex flex-wrap items-center gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span><b>{pool.not_in_run} parsed resume{pool.not_in_run === 1 ? "" : "s"}</b> {pool.not_in_run === 1 ? "was" : "were"} uploaded after this ranking and {pool.not_in_run === 1 ? "is" : "are"} <b>not ranked</b>.</span>
          <button className="btn-primary ml-auto" onClick={onRerun}>Re-run matching to include them</button>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-slate-700">
        <span><b>{pool.files_received}</b> files received</span><span>→ <b>{pool.parsed}</b> parsed</span>
        <span>· <b>{pool.failed}</b> failed</span>
        <span>· <b>{pool.duplicates_skipped}</b> identical duplicate{pool.duplicates_skipped === 1 ? "" : "s"} skipped</span>
        <span className="ml-auto">Ranked in this run: <b>{pool.ranked_in_run}</b> of {pool.parsed} parsed</span>
        {pool.duplicates_skipped > 0 && <button className="text-brand-600 underline" onClick={toggle}>{open ? "Hide" : "Show"} duplicates</button>}
        <Link className="text-brand-600 underline" to="/resumes">All files</Link>
      </div>
      {open && acc && (
        <ul className="mt-3 max-h-48 overflow-auto border-t border-slate-100 pt-2 text-xs text-slate-600">
          {acc.duplicates.map((d, i) => <li key={i}>Skipped: byte-identical to <b>{d.identical_to_filename ?? `resume #${d.identical_to_resume_id}`}</b> ({new Date(d.skipped_at).toLocaleString()})</li>)}
        </ul>
      )}
    </div>
  );
}
