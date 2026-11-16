import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { api, errMsg, setKey } from "../api";
import { ErrorBox } from "../components/ui";

export default function Login() {
  const nav = useNavigate();
  const [key, setK] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    try { await api.post("/auth/login", { api_key: key }); setKey(key); nav("/"); } catch (x) { setErr(errMsg(x)); }
  };
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-brand-950 via-brand-800 to-brand-600 p-4">
      <div className="pointer-events-none absolute -left-24 -top-24 h-96 w-96 animate-float rounded-full bg-accent-400/30 blur-3xl" aria-hidden />
      <div className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-fuchsia-500/25 blur-3xl" aria-hidden />
      <form onSubmit={submit} className="page-enter relative w-full max-w-sm space-y-5 rounded-3xl border border-white/20 bg-white/90 p-8 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <span className="icon-chip"><Sparkles className="h-5 w-5" /></span>
          <div><h1 className="text-xl font-extrabold tracking-tight text-slate-900">TalentIQ AI</h1><p className="text-xs text-slate-500">Evidence-driven recruitment intelligence</p></div>
        </div>
        <div><label className="label" htmlFor="key">Access key</label><input id="key" type="password" className="input" value={key} onChange={(e) => setK(e.target.value)} placeholder="Leave empty if the server has no key" /></div>
        {err && <ErrorBox message={err} />}
        <button className="btn-primary w-full" type="submit">Continue</button>
        <p className="text-xs text-slate-500">Local demo: the backend only requires a key when <code>API_KEY</code> is set.</p>
      </form>
    </div>
  );
}
