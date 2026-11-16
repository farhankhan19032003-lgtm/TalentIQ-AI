import { createContext, ReactNode, useContext, useState } from "react";
import { useSelectedJob } from "./hooks";

interface Ctx { jobId: number | null; setJobId: (n: number | null) => void; blind: boolean; setBlind: (b: boolean) => void }
const C = createContext<Ctx>({ jobId: null, setJobId: () => {}, blind: false, setBlind: () => {} });
export const useApp = () => useContext(C);
export function AppProvider({ children }: { children: ReactNode }) {
  const [jobId, setJobId] = useSelectedJob();
  const [blind, setBlind] = useState(false);
  return <C.Provider value={{ jobId, setJobId, blind, setBlind }}>{children}</C.Provider>;
}
