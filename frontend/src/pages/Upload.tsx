import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, UploadCloud, XCircle } from "lucide-react";
import { api, errMsg } from "../api";
import { Chip, ErrorBox, PageTitle } from "../components/ui";
import { UploadItem, UploadResponse } from "../types";

const TONE: Record<string, "green" | "red" | "amber" | "slate"> = { parsed: "green", failed: "red", rejected: "red", duplicate: "amber" };
export const ALLOWED = [".pdf", ".docx"];
export const isAllowed = (n: string) => ALLOWED.some((e) => n.toLowerCase().endsWith(e));

export default function Upload() {
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<UploadResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);

  const add = (list: FileList | File[]) => setFiles((f) => [...f, ...Array.from(list)]);
  const send = async (fs: File[]) => {
    setBusy(true); setErr(null); setProgress(0);
    const fd = new FormData(); fs.forEach((f) => fd.append("files", f));
    try {
      const r = await api.post<UploadResponse>("/resumes/upload", fd, { onUploadProgress: (e) => setProgress(e.total ? Math.round((e.loaded / e.total) * 100) : 0) });
      setRes(r.data); setFiles([]);
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };
  const retry = async (it: UploadItem) => {
    if (!it.resume_id) return;
    try { await api.post(`/resumes/${it.resume_id}/retry`); setErr(null); } catch (e) { setErr(errMsg(e)); }
  };
  const bad = files.filter((f) => !isAllowed(f.name));
  return (
    <div>
      <PageTitle title="Upload resumes" sub="PDF and DOCX. One bad file never stops the batch." />
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
        className={`card group flex cursor-pointer flex-col items-center gap-3 border-2 border-dashed bg-gradient-to-br p-12 text-center transition duration-200 ${drag ? "scale-[1.01] border-brand-500 from-brand-50 to-brand-100" : "border-brand-200 from-white to-brand-50/60 hover:border-brand-400"}`}
        onClick={() => input.current?.click()} role="button" aria-label="Drop resumes here or click to browse"
      >
        <span className="icon-chip h-14 w-14 rounded-2xl transition group-hover:scale-110"><UploadCloud className="h-7 w-7" /></span><div className="text-lg font-semibold text-slate-900">Drag & drop resumes here, or click to browse</div>
        <div className="text-xs text-slate-500">.pdf / .docx · duplicates, corrupted and password-protected files are detected and reported</div>
        <input ref={input} type="file" multiple hidden accept=".pdf,.docx" onChange={(e) => e.target.files && add(e.target.files)} />
      </div>
      {files.length > 0 && (
        <div className="card mt-4 p-4">
          <div className="mb-2 text-sm font-medium">{files.length} file(s) selected</div>
          <ul className="max-h-40 overflow-auto text-sm">{files.map((f, i) => <li key={i} className={isAllowed(f.name) ? "" : "text-red-600"}>{f.name} <span className="text-xs text-slate-400">{(f.size / 1024).toFixed(0)} KB{!isAllowed(f.name) && " — unsupported type, will be rejected"}</span></li>)}</ul>
          {bad.length > 0 && <p className="mt-2 text-xs text-amber-700">{bad.length} file(s) are not PDF/DOCX. They will be reported as rejected.</p>}
          <div className="mt-3 flex items-center gap-3">
            <button className="btn-primary" disabled={busy} onClick={() => send(files)}>{busy ? `Uploading… ${progress}%` : "Upload & parse"}</button>
            <button className="btn-ghost" disabled={busy} onClick={() => setFiles([])}>Clear</button>
            {busy && <div className="h-2 flex-1 overflow-hidden rounded bg-slate-200"><div className="h-full bg-brand-600" style={{ width: `${progress}%` }} /></div>}
          </div>
        </div>
      )}
      {err && <div className="mt-4"><ErrorBox message={err} /></div>}
      {res && (
        <div className="card mt-4">
          <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 p-4">
            <h2 className="font-semibold">Batch result</h2>
            {Object.entries(res.summary).map(([k, v]) => <Chip key={k} tone={TONE[k] ?? "slate"}>{v} {k}</Chip>)}
            <Link className="btn-primary ml-auto" to="/ranking">Go to ranking</Link>
          </div>
          <table className="w-full"><thead><tr><th className="th">File</th><th className="th">Status</th><th className="th">Details</th><th className="th" /></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {res.results.map((r, i) => (
                <tr key={i}><td className="td">{r.filename}</td>
                  <td className="td"><span className="inline-flex items-center gap-1">{
                    r.status === "parsed" && r.needs_review ? <><AlertTriangle className="h-4 w-4 text-amber-500" /><span className="text-amber-700">parsed: needs review</span></>
                    : r.status === "parsed" ? <><CheckCircle2 className="h-4 w-4 text-emerald-600" />parsed</>
                    : ["scanned_no_ocr", "no_text"].includes(r.error_code ?? "") ? <><AlertTriangle className="h-4 w-4 text-amber-500" /><span className="text-amber-700">needs review: no text</span></>
                    : <><XCircle className="h-4 w-4 text-red-500" />{r.status}</>}</span></td>
                  <td className="td text-slate-600">{r.error_message ?? (r.possible_duplicate_of ? "Possible duplicate person (same email/name)" : r.warnings?.join(" ") ?? "")}</td>
                  <td className="td">{r.status === "failed" && <button className="btn-ghost" onClick={() => retry(r)}>Retry</button>}</td></tr>
              ))}
            </tbody></table>
        </div>
      )}
    </div>
  );
}
