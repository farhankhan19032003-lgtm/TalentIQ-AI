import axios, { AxiosError } from "axios";

export const api = axios.create({ baseURL: "/api", timeout: 120000 });

const KEY = "talentiq_api_key";
export const getKey = () => { try { return sessionStorage.getItem(KEY) ?? ""; } catch { return ""; } };
export const setKey = (k: string) => { try { k ? sessionStorage.setItem(KEY, k) : sessionStorage.removeItem(KEY); } catch { /* storage unavailable */ } };

api.interceptors.request.use((c) => { const k = getKey(); if (k) c.headers["X-API-Key"] = k; return c; });
api.interceptors.response.use((r) => r, (e: AxiosError<any>) => {
  if (e.response?.status === 401 && !location.pathname.startsWith("/login")) location.assign("/login");
  return Promise.reject(e);
});

/** Human-readable message from the backend's uniform error envelope. */
export function errMsg(e: unknown): string {
  const ax = e as AxiosError<any>;
  const d = ax?.response?.data?.error;
  if (d?.message) return d.message;
  if (ax?.code === "ECONNABORTED") return "The request timed out.";
  if (ax?.message === "Network Error") return "Cannot reach the backend. Is it running on port 8000?";
  return (e as Error)?.message ?? "Unexpected error";
}

export const dl = (path: string) => `/api${path}`;
export async function download(path: string, filename: string) {
  const r = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}
