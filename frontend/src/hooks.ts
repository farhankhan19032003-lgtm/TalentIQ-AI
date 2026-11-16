import { useCallback, useEffect, useState } from "react";
import { errMsg } from "./api";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const run = useCallback(() => {
    let alive = true;
    setLoading(true); setError(null);
    fn().then((d) => alive && setData(d)).catch((e) => alive && setError(errMsg(e))).finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => run(), [run]);
  return { data, error, loading, reload: run, setData };
}
export function useSelectedJob() {
  const [id, setId] = useState<number | null>(() => { try { const v = sessionStorage.getItem("job"); return v ? Number(v) : null; } catch { return null; } });
  const set = (n: number | null) => { setId(n); try { n ? sessionStorage.setItem("job", String(n)) : sessionStorage.removeItem("job"); } catch { /* ignore */ } };
  return [id, set] as const;
}
