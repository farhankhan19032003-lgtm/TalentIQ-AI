import { NavLink, Outlet, useLocation } from "react-router-dom";
import { EyeOff, Search, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import { NAV } from "../nav";
import { Job, Paged } from "../types";
import CommandPalette, { OPEN_PALETTE_EVENT } from "./CommandPalette";

const SHORTCUT = typeof navigator !== "undefined" && /Mac/i.test(navigator.platform) ? "⌘K" : "Ctrl K";

export default function Layout() {
  const { jobId, setJobId, blind, setBlind } = useApp();
  const loc = useLocation();
  // Reloaded on every page change so a job created or deleted on another page shows up in the selector straight away.
  const jobs = useAsync(() => api.get<Paged<Job>>("/jobs?page_size=100").then((r) => r.data), [loc.pathname]);
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col overflow-y-auto bg-gradient-to-b from-brand-950 via-brand-900 to-brand-800 p-5 text-indigo-100 md:flex">
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent-400 to-brand-500 text-white shadow-glow"><Sparkles className="h-5 w-5" /></span>
          <div><div className="text-lg font-extrabold tracking-tight text-white">TalentIQ AI</div><div className="text-[11px] leading-tight text-indigo-300">Evidence-driven recruitment intelligence</div></div>
        </div>
        <nav className="space-y-1" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"}
              className={({ isActive }) => `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${isActive ? "bg-white/15 text-white shadow-inner ring-1 ring-white/20" : "text-indigo-200 hover:bg-white/10 hover:text-white"}`}>
              {({ isActive }) => (<>
                <span className={`flex h-8 w-8 items-center justify-center rounded-lg transition ${isActive ? "bg-gradient-to-br from-accent-400 to-brand-500 text-white" : "bg-white/5 text-indigo-300 group-hover:bg-white/10"}`}><Icon className="h-4 w-4" /></span>
                {label}
              </>)}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto rounded-2xl bg-white/10 p-4 text-xs leading-relaxed text-indigo-200 ring-1 ring-white/10">
          <div className="mb-1 flex items-center gap-1.5 font-semibold text-white"><ShieldCheck className="h-4 w-4 text-accent-400" />Decision support</div>
          Decision support only. Scores explain evidence; recruiters decide.
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex flex-wrap items-center gap-3 border-b border-slate-200/70 bg-white/75 px-4 py-3 backdrop-blur-md md:px-8">
          <span className="flex items-center gap-2 font-extrabold text-brand-800 md:hidden"><Sparkles className="h-4 w-4" />TalentIQ</span>
          <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500" htmlFor="jobsel">Active job</label>
          <select id="jobsel" className="input max-w-xs" value={jobId ?? ""} onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">— select a job —</option>
            {jobs.data?.items.map((j) => <option key={j.id} value={j.id}>{j.title}{j.is_template ? " (template)" : ""}</option>)}
          </select>
          <button className="btn-ghost ml-auto hidden md:inline-flex" onClick={() => window.dispatchEvent(new Event(OPEN_PALETTE_EVENT))} aria-label="Open command palette">
            <Search className="h-4 w-4" />Search<kbd className="ml-1 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">{SHORTCUT}</kbd>
          </button>
          <button className={blind ? "btn-primary" : "btn-ghost"} onClick={() => setBlind(!blind)} aria-pressed={blind} title="Hide names, emails and contact details to reduce bias during screening">
            <EyeOff className="h-4 w-4" />Blind screening {blind ? "ON" : "off"}
          </button>
        </header>
        <main className="mx-auto max-w-7xl p-4 md:p-8"><div key={loc.pathname} className="page-enter"><Outlet /></div></main>
      </div>
      <CommandPalette />
    </div>
  );
}
