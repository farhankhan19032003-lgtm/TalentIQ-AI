import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase, CornerDownLeft, EyeOff, Search, User } from "lucide-react";
import { api } from "../api";
import { useApp } from "../ctx";
import { NAV } from "../nav";
import { Job, Paged, ResultRow, ResultsResponse } from "../types";
import { fmt, fuzzyScore } from "../utils";

export const OPEN_PALETTE_EVENT = "talentiq:open-palette";
type Group = "Pages" | "Jobs" | "Candidates" | "Actions";
interface Item { key: string; group: Group; label: string; hint?: string; icon: ReactNode; run: () => void }
const ORDER: Group[] = ["Pages", "Jobs", "Actions", "Candidates"];

/** Ctrl/Cmd+K: jump to any page, job or candidate, or toggle blind screening, from the keyboard. */
export default function CommandPalette() {
  const nav = useNavigate();
  const { jobId, setJobId, blind, setBlind } = useApp();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [cands, setCands] = useState<ResultRow[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
      else if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_PALETTE_EVENT, onOpen);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener(OPEN_PALETTE_EVENT, onOpen); };
  }, []);

  useEffect(() => {
    if (!open) return;
    setQ(""); setIdx(0);
    const t = setTimeout(() => input.current?.focus(), 0);
    let alive = true;
    api.get<Paged<Job>>("/jobs?page_size=100").then((r) => alive && setJobs(r.data.items)).catch(() => {});
    if (jobId) api.get<ResultsResponse>(`/matching/results/${jobId}`, { params: { page_size: 100, blind } }).then((r) => alive && setCands(r.data.items)).catch(() => alive && setCands([]));
    else setCands([]);
    return () => { alive = false; clearTimeout(t); };
  }, [open, jobId, blind]);

  const close = () => setOpen(false);
  const all: Item[] = useMemo(() => [
    ...NAV.map((n) => ({ key: "p" + n.to, group: "Pages" as Group, label: n.label, icon: <n.icon className="h-4 w-4" />, run: () => nav(n.to) })),
    ...jobs.map((j) => ({ key: "j" + j.id, group: "Jobs" as Group, label: j.title, hint: jobId === j.id ? "active job" : "set active and rank", icon: <Briefcase className="h-4 w-4" />, run: () => { setJobId(j.id); nav("/ranking"); } })),
    { key: "a-blind", group: "Actions" as Group, label: blind ? "Turn blind screening off" : "Turn blind screening on", hint: "hide names and contact details", icon: <EyeOff className="h-4 w-4" />, run: () => setBlind(!blind) },
    ...cands.map((c) => ({ key: "c" + c.candidate_id, group: "Candidates" as Group, label: c.name, hint: `${c.latest_role ?? "no role"} · ${fmt(c.overall)}`, icon: <User className="h-4 w-4" />, run: () => nav(`/candidates/${c.candidate_id}`) })),
  ], [jobs, cands, jobId, blind, nav, setJobId, setBlind]);

  const shown = useMemo(() => {
    if (!q.trim()) {
      const by = (g: Group) => all.filter((i) => i.group === g);
      return [...by("Pages"), ...by("Jobs"), ...by("Actions"), ...by("Candidates").slice(0, 5)];
    }
    return all.map((i) => ({ i, s: fuzzyScore(q, `${i.label} ${i.hint ?? ""}`) })).filter((x) => x.s >= 0)
      .sort((a, b) => b.s - a.s || ORDER.indexOf(a.i.group) - ORDER.indexOf(b.i.group)).slice(0, 30).map((x) => x.i);
  }, [all, q]);

  useEffect(() => { setIdx(0); }, [q]);
  useEffect(() => { list.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" }); }, [idx, shown]);
  if (!open) return null;

  const choose = (i?: Item) => { if (!i) return; close(); i.run(); };
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, shown.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); choose(shown[idx]); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 p-4 pt-[12vh] backdrop-blur-sm" onMouseDown={close}>
      <div role="dialog" aria-modal="true" aria-label="Command palette" className="page-enter w-full max-w-xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
          <Search className="h-5 w-5 text-slate-400" />
          <input ref={input} aria-label="Search pages, jobs and candidates" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKeyDown}
            placeholder={jobId ? "Search pages, jobs, candidates…" : "Search pages and jobs (select a job to search candidates)…"}
            className="w-full bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none" />
          <kbd className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">Esc</kbd>
        </div>
        <ul ref={list} role="listbox" aria-label="Results" className="max-h-80 overflow-y-auto p-2">
          {shown.length === 0 && <li className="p-6 text-center text-sm text-slate-500">No matches for “{q}”.</li>}
          {shown.map((it, n) => (
            <li key={it.key} role="option" aria-selected={n === idx} onMouseEnter={() => setIdx(n)} onClick={() => choose(it)}
              className={`flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm ${n === idx ? "bg-brand-50 text-brand-900" : "text-slate-700"}`}>
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${n === idx ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-500"}`}>{it.icon}</span>
              <span className="min-w-0 flex-1"><span className="block truncate font-medium">{it.label}</span>{it.hint && <span className="block truncate text-xs text-slate-500">{it.hint}</span>}</span>
              <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-400">{it.group}</span>
              {n === idx && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-brand-500" />}
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-4 border-t border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-500">
          <span><kbd className="font-semibold">↑↓</kbd> navigate</span><span><kbd className="font-semibold">↵</kbd> open</span><span><kbd className="font-semibold">Esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
