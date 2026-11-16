import { ReactNode, createContext, useCallback, useContext, useRef, useState } from "react";
import { CircleCheck, Info, TriangleAlert, X } from "lucide-react";

type Kind = "success" | "error" | "info";
interface ToastOptions { kind?: Kind; ms?: number; action?: { label: string; onClick: () => void } }
interface ToastItem { id: number; message: string; kind: Kind; action?: ToastOptions["action"] }

const Ctx = createContext<{ toast: (message: string, options?: ToastOptions) => void }>({ toast: () => {} });
export const useToast = () => useContext(Ctx);

const STYLE: Record<Kind, { box: string; icon: ReactNode }> = {
  success: { box: "border-emerald-200", icon: <CircleCheck className="h-5 w-5 text-emerald-600" /> },
  error: { box: "border-red-200", icon: <TriangleAlert className="h-5 w-5 text-red-600" /> },
  info: { box: "border-sky-200", icon: <Info className="h-5 w-5 text-sky-600" /> },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);
  const dismiss = useCallback((id: number) => setItems((a) => a.filter((t) => t.id !== id)), []);
  const toast = useCallback((message: string, o: ToastOptions = {}) => {
    const id = next.current++;
    setItems((a) => [...a.slice(-3), { id, message, kind: o.kind ?? "success", action: o.action }]);
    setTimeout(() => dismiss(id), o.ms ?? 6000);
  }, [dismiss]);
  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} role="status" className={`pointer-events-auto flex animate-fade-up items-start gap-3 rounded-2xl border bg-white p-3.5 shadow-lift ${STYLE[t.kind].box}`}>
            <span className="mt-0.5 shrink-0">{STYLE[t.kind].icon}</span>
            <p className="flex-1 text-sm text-slate-800">{t.message}</p>
            {t.action && <button className="text-sm font-semibold text-brand-600 hover:text-brand-800" onClick={() => { t.action!.onClick(); dismiss(t.id); }}>{t.action.label}</button>}
            <button aria-label="Dismiss" className="text-slate-400 hover:text-slate-700" onClick={() => dismiss(t.id)}><X className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
