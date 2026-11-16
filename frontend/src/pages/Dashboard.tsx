import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Briefcase, FileCheck2, FileText, FileWarning, FileUp, Trophy, Layers } from "lucide-react";
import { api, errMsg } from "../api";
import { useApp } from "../ctx";
import { useAsync } from "../hooks";
import { ErrorBox, Spinner, Stat } from "../components/ui";
import { Job, Paged, UploadResponse } from "../types";

export default function Dashboard() {
  const { jobId, setJobId } = useApp();
  const stats = useAsync(() => api.get("/resumes/stats").then((r) => r.data), []);
  const jobs = useAsync(() => api.get<Paged<Job>>("/jobs?page_size=100").then((r) => r.data), []);
  if (stats.loading || jobs.loading) return <Spinner />;
  const empty = (stats.data?.total ?? 0) === 0;
  const steps = [
    { n: 1, to: "/jobs/new", icon: Briefcase, title: "Create a job", text: "Paste or upload a job description. Requirements are extracted and editable." },
    { n: 2, to: "/upload", icon: FileUp, title: "Upload resumes", text: "PDF or DOCX, single files or whole batches. Bad files never stop the batch." },
    { n: 3, to: "/ranking", icon: Trophy, title: "Rank with evidence", text: "Run matching and inspect the exact resume text behind every score." },
  ];
  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-900 via-brand-700 to-brand-500 p-8 text-white shadow-lift md:p-10">
        <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 animate-float rounded-full bg-accent-400/30 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-20 left-1/3 h-64 w-64 rounded-full bg-fuchsia-400/20 blur-3xl" aria-hidden />
        <div className="relative max-w-2xl">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold ring-1 ring-white/25 backdrop-blur"><Layers className="h-3.5 w-3.5" />Evidence-driven recruitment intelligence</span>
          <h1 className="mt-4 text-3xl font-extrabold leading-tight tracking-tight md:text-4xl">Find the right people, and see exactly why.</h1>
          <p className="mt-3 text-sm leading-relaxed text-indigo-100 md:text-base">Upload resumes, define a job, and get a ranked shortlist where every score points back to the resume text that justifies it. Decision support only: a recruiter makes every decision.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/ranking" className="btn bg-white text-brand-800 shadow-lg hover:bg-indigo-50">Open ranking <ArrowRight className="h-4 w-4" /></Link>
            <Link to="/upload" className="btn border border-white/40 bg-white/10 text-white backdrop-blur hover:bg-white/20">Upload resumes</Link>
          </div>
        </div>
      </section>

      {(stats.error || jobs.error) && <ErrorBox message={(stats.error || jobs.error)!} onRetry={() => { stats.reload(); jobs.reload(); }} />}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Resumes uploaded" value={stats.data?.total ?? 0} icon={<FileText className="h-5 w-5" />} />
        <Stat label="Parsed" value={stats.data?.parsed ?? 0} icon={<FileCheck2 className="h-5 w-5" />} />
        <Stat label="Failed" value={stats.data?.failed ?? 0} hint="Safe, classified failures" icon={<FileWarning className="h-5 w-5" />} />
        <Stat label="Jobs" value={jobs.data?.total ?? 0} icon={<Briefcase className="h-5 w-5" />} />
      </div>

      <section>
        <h2 className="mb-3 text-lg font-bold text-slate-900">Get started</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {steps.map(({ n, to, icon: Icon, title, text }) => (
            <Link key={n} to={to} className="card card-hover group relative p-5">
              <span className="icon-chip"><Icon className="h-5 w-5" /></span>
              <span className="absolute right-5 top-4 text-4xl font-black text-brand-100 transition group-hover:text-brand-200">{n}</span>
              <h3 className="mt-4 font-bold text-slate-900">{title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">{text}</p>
              <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand-600">Go <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
            </Link>
          ))}
        </div>
        {empty && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm">
            No resumes yet. Create a job, then <Link to="/upload" className="font-semibold underline">upload resumes</Link> (PDF or DOCX).
          </div>
        )}
      </section>

      {jobs.data && jobs.data.items.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-bold text-slate-900">Jobs</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {jobs.data.items.map((j) => (
              <div key={j.id} className={`card card-hover flex flex-col justify-between gap-4 p-5 ${jobId === j.id ? "ring-2 ring-brand-400" : ""}`}>
                <div className="flex items-start gap-3">
                  <span className="icon-chip shrink-0"><Briefcase className="h-5 w-5" /></span>
                  <div className="min-w-0">
                    <div className="truncate font-bold text-slate-900">{j.title}</div>
                    <div className="text-xs text-slate-500">{j.requirements.filter((r) => r.importance === "must").length} must-have · {j.requirements.filter((r) => r.importance === "preferred").length} preferred{j.is_template && <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">template</span>}</div>
                  </div>
                </div>
                <Link to="/ranking" onClick={() => setJobId(j.id)} className="btn-ghost w-full">Rank candidates <ArrowRight className="h-4 w-4" /></Link>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
