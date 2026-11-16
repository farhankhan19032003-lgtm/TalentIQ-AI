import { COMP_LABEL, fmt, weightsValid } from "../utils";
import { Weights } from "../types";

/** Five sliders (percent). Shows live sum; the parent must only submit when the sum is exactly 100%. */
export default function WeightsPanel({ value, onChange, defaults }: { value: Weights; onChange: (w: Weights) => void; defaults: Weights }) {
  const sum = Object.values(value).reduce((a, b) => a + b, 0);
  const ok = weightsValid(value);
  return (
    <div className="space-y-2">
      {Object.keys(COMP_LABEL).map((k) => (
        <div key={k} className="flex items-center gap-3 text-sm">
          <label className="w-44" htmlFor={`w_${k}`}>{COMP_LABEL[k]}</label>
          <input id={`w_${k}`} type="range" min={0} max={100} step={5} className="flex-1" value={Math.round((value[k] ?? 0) * 100)}
            onChange={(e) => onChange({ ...value, [k]: Number(e.target.value) / 100 })} />
          <span className="w-12 text-right tabular-nums">{Math.round((value[k] ?? 0) * 100)}%</span>
        </div>
      ))}
      <div className="flex items-center justify-between text-xs">
        <span className={ok ? "text-emerald-700" : "text-red-600"}>Total {fmt(sum * 100, 0)}% {ok ? "" : "— must equal 100%"}</span>
        <button className="text-brand-600 underline" onClick={() => onChange({ ...defaults })}>Reset to default</button>
      </div>
    </div>
  );
}
