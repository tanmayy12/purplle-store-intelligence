import { useCallback, useEffect, useState } from "react";
import { api, type AnomaliesResponse, type FunnelResponse, type MetricsResponse } from "./api/client";
import AnomalyFeed from "./components/AnomalyFeed";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [funnel, setFunnel] = useState<FunnelResponse | null>(null);
  const [anomalies, setAnomalies] = useState<AnomaliesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, f, a] = await Promise.all([api.metrics(), api.funnel(), api.anomalies()]);
      setMetrics(m);
      setFunnel(f);
      setAnomalies(a);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-bold text-white">
              Purplle <span className="text-purplle-500">Store Intelligence</span>
            </h1>
            <p className="text-sm text-slate-400">
              {metrics ? `${metrics.store_name} · ${metrics.date}` : "Brigade Bangalore · ST1008"}
            </p>
          </div>
          <div className="text-right text-xs text-slate-500">
            {lastUpdated && <p>Updated {lastUpdated.toLocaleTimeString()}</p>}
            <button onClick={load} className="mt-1 rounded bg-purplle-700 px-3 py-1 text-white hover:bg-purplle-500">
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {error && (
          <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400">
            {error}
          </div>
        )}

        <Dashboard metrics={metrics} funnel={funnel} />

        <div className="mt-8">
          <AnomalyFeed items={anomalies?.items ?? []} total={anomalies?.total ?? 0} />
        </div>
      </main>
    </div>
  );
}
