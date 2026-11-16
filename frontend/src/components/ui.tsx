import { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { MATCH_CLASS, MATCH_LABEL, TONE_CLASS, fmt, scoreTone } from "../utils";

export const Spinner = ({ label = "Loading…" }: { label?: string }) => (
  <div role="status" className="flex items-center gap-2 p-6 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin text-brand-500" />{label}</div>
);
export const ErrorBox = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50/80 p-3 text-sm text-red-800">
    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><div className="flex-1">{message}</div>
    {onRetry && <button className="btn-ghost" onClick={onRetry}>Retry</button>}
  </div>
);
export const Empty = ({ children }: { children: ReactNode }) => (
  <div className="flex flex-col items-center gap-3 p-10 text-center text-sm text-slate-500">
    <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-500"><Inbox className="h-6 w-6" /></span><div>{children}</div>
  </div>
);
export const PageTitle = ({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) => (
  <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 className="bg-gradient-to-r from-brand-900 via-brand-700 to-brand-500 bg-clip-text pb-1 text-3xl font-extrabold leading-tight tracking-tight text-transparent">{title}</h1>
      {sub && <p className="mt-1 text-sm text-slate-500">{sub}</p>}
    </div>
    <div className="flex flex-wrap gap-2">{children}</div>
  </div>
);
export const Stat = ({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode }) => (
  <div className="card card-hover relative overflow-hidden p-5">
    <div className="absolute -right-6 -top-6 h-20 w-20 rounded-full bg-brand-100/60" aria-hidden />
    <div className="relative flex items-start justify-between gap-3">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</div>
        <div className="mt-1.5 text-3xl font-extrabold tracking-tight text-slate-900">{value}</div>
        {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
      </div>
      {icon && <span className="icon-chip shrink-0">{icon}</span>}
    </div>
  </div>
);

export function ScoreBadge({ score, low, high }: { score: number; low?: number; high?: number }) {
  const range = low !== undefined && high !== undefined && high - low > 0.05;
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-sm font-bold ${TONE_CLASS[scoreTone(score)]}`}
      title={range ? `Score ${fmt(score)} — could reach ${fmt(high)} if missing evidence were provided (shown as a range, not a penalty)` : undefined}>
      {fmt(score)}{range && <span className="ml-1 text-xs font-normal opacity-70">–{fmt(high, 0)}</span>}
    </span>
  );
}
export const MatchTag = ({ type }: { type: string }) => (
  <span className={`rounded-md px-1.5 py-0.5 text-xs font-semibold ${MATCH_CLASS[type] ?? "bg-slate-100"}`}>{MATCH_LABEL[type] ?? type}</span>
);
export const Chip = ({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "green" | "red" | "amber" | "blue" }) => {
  const c = {
    slate: "bg-slate-100 text-slate-700 ring-slate-200", green: "bg-emerald-50 text-emerald-700 ring-emerald-200", red: "bg-red-50 text-red-700 ring-red-200",
    amber: "bg-amber-50 text-amber-800 ring-amber-200", blue: "bg-sky-50 text-sky-700 ring-sky-200",
  }[tone];
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${c}`}>{children}</span>;
};
export const Disclaimer = ({ text }: { text?: string }) => (
  <p className="rounded-xl border border-slate-200/70 bg-slate-50 p-3 text-xs text-slate-600">{text ?? "Decision-support only. Scores are not hiring probabilities; a recruiter makes every decision."}</p>
);
export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-600">
      <span>{total} result{total === 1 ? "" : "s"}</span>
      <div className="flex items-center gap-2">
        <button className="btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Prev</button>
        <span>Page {page} / {pages}</span>
        <button className="btn-ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}
