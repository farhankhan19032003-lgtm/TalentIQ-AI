import { FileText } from "lucide-react";
import { MatchTag } from "./ui";
import { ReqResult } from "../types";

/** Shows the verbatim resume snippet that justifies a requirement's score, with the matched term highlighted. */
export function highlight(text: string, terms: string[]) {
  const ts = terms.filter(Boolean).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!ts.length) return [text];
  const re = new RegExp(`(${ts.join("|")})`, "ig");
  return text.split(re).map((part, i) => (i % 2 === 1 ? <mark key={i} className="rounded bg-yellow-200 px-0.5">{part}</mark> : part));
}
export default function EvidenceViewer({ req }: { req: ReqResult }) {
  const terms = [req.satisfied_by ?? req.name, ...(req.related_found ?? []), ...(req.any_of ?? [])].filter(Boolean) as string[];
  return (
    <div className="space-y-1.5 rounded-lg bg-slate-50 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2"><MatchTag type={req.match_type} />
        <span className="text-xs text-slate-500">credit {Math.round(req.credit * 100)}%{req.similarity != null && ` · cosine ${req.similarity.toFixed(2)}`} · verification: {req.verification.replace("_", " ")}</span></div>
      {req.evidence_text ? (
        <blockquote className="border-l-4 border-brand-500 bg-white p-2 text-slate-700">
          <FileText className="mr-1 inline h-3.5 w-3.5 text-slate-400" />{highlight(req.evidence_text, terms)}
          <div className="mt-1 text-xs text-slate-400">Source: page {req.page ?? "?"}{req.section ? `, ${req.section} section` : ""} — verbatim from the resume</div>
        </blockquote>
      ) : <p className="text-slate-500">No supporting text found in the resume.</p>}
      <p className="text-xs text-slate-600">{req.note}</p>
    </div>
  );
}
