import type { AnomalyItem } from "../api/client";

const severityColors: Record<string, string> = {
  high: "bg-red-500/20 text-red-400 border-red-500/30",
  medium: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  low: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

interface Props {
  items: AnomalyItem[];
  total: number;
}

export default function AnomalyFeed({ items, total }: Props) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Anomaly Feed</h2>
        <span className="rounded-full bg-purplle-500/20 px-3 py-1 text-xs text-purplle-500">{total} total</span>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">No anomalies detected.</p>
      ) : (
        <ul className="max-h-80 space-y-3 overflow-y-auto">
          {items.map((item) => (
            <li key={item.anomaly_id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
              <div className="flex items-start justify-between gap-2">
                <span className={`rounded border px-2 py-0.5 text-xs ${severityColors[item.severity] || severityColors.low}`}>
                  {item.severity}
                </span>
                <time className="text-xs text-slate-500">
                  {new Date(item.detected_at).toLocaleTimeString()}
                </time>
              </div>
              <p className="mt-2 text-sm font-medium text-slate-200">{item.anomaly_type.replace(/_/g, " ")}</p>
              <p className="mt-1 text-xs text-slate-400">{item.description}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
