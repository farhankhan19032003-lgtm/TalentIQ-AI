import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { useSelectedJob } from "./hooks";

interface Ctx { jobId: number | null; setJobId: (n: number | null) => void; blind: boolean; setBlind: (b: boolean) => void }
const C = createContext<Ctx>({ jobId: null, setJobId: () => {}, blind: false, setBlind: () => {} });
export const useApp = () => useContext(C);
export function AppProvider({ children }: { children: ReactNode }) {
  const [jobId, setJobId] = useSelectedJob();
  const [blind, setBlind] = useState(false);
  // First visit in this browser session with no job chosen: pre-select the most recent job so Ranking / Candidate pages are not empty.
  // Done once per session, so choosing "- select a job -" afterwards is respected.
  useEffect(() => {
    let done = false;
    try { done = sessionStorage.getItem("job_autoselect") === "1"; } catch { /* ignore */ }
    if (jobId !== null || done) return;
    try { sessionStorage.setItem("job_autoselect", "1"); } catch { /* ignore */ }
    api.get("/jobs", { params: { page_size: 1 } }).then((r) => { const j = r.data?.items?.[0]; if (j) setJobId(j.id); }).catch(() => { /* not logged in or backend down: leave empty */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <C.Provider value={{ jobId, setJobId, blind, setBlind }}>{children}</C.Provider>;
}
