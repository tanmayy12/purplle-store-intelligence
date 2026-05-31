import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FunnelResponse, MetricsResponse } from "../api/client";

const COLORS = ["#9333ea", "#7c3aed", "#6366f1", "#3b82f6", "#22c55e"];

interface Props {
  metrics: MetricsResponse | null;
  funnel: FunnelResponse | null;
}

export default function Dashboard({ metrics, funnel }: Props) {
  if (!metrics || !funnel) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-400">
        Loading store intelligence data…
      </div>
    );
  }

  const kpiCards = [
    { label: "Footfall", value: metrics.footfall.total_entries, sub: `${metrics.footfall.unique_sessions} sessions` },
    { label: "Conversion Rate", value: `${(metrics.conversion.conversion_rate * 100).toFixed(1)}%`, sub: `${metrics.conversion.matched_conversions} matched` },
    { label: "POS Transactions", value: metrics.conversion.pos_transactions, sub: `₹${metrics.revenue.total_nmv.toLocaleString()} NMV` },
    { label: "Avg Basket", value: `₹${metrics.revenue.avg_basket_nmv.toFixed(0)}`, sub: `${metrics.revenue.avg_items_per_transaction.toFixed(1)} items/txn` },
    { label: "Engagement Rate", value: `${(metrics.engagement.engagement_rate * 100).toFixed(1)}%`, sub: `${Math.round(metrics.engagement.avg_dwell_sec / 60)} min avg dwell` },
    { label: "Revenue / Visitor", value: `₹${metrics.revenue.revenue_per_visitor.toFixed(0)}`, sub: `${metrics.footfall.staff_excluded} staff excluded` },
  ];

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {kpiCards.map((card) => (
          <div key={card.label} className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-400">{card.label}</p>
            <p className="mt-1 text-2xl font-bold text-white">{card.value}</p>
            <p className="mt-1 text-xs text-slate-500">{card.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6">
          <h2 className="mb-4 text-lg font-semibold">Conversion Funnel</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={funnel.stages} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis dataKey="stage" type="category" width={120} stroke="#94a3b8" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155" }}
                formatter={(value: number, _name, props) => [
                  `${value} (${props.payload.pct_of_top}%)`,
                  "Count",
                ]}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {funnel.stages.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6">
          <h2 className="mb-4 text-lg font-semibold">Hourly Performance</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={metrics.hourly}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="hour" stroke="#94a3b8" label={{ value: "Hour", position: "insideBottom", offset: -5 }} />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155" }} />
              <Legend />
              <Line type="monotone" dataKey="entries" stroke="#9333ea" name="Entries" strokeWidth={2} />
              <Line type="monotone" dataKey="transactions" stroke="#22c55e" name="Transactions" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6">
          <h2 className="mb-4 text-lg font-semibold">Top Zones by Visits</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={metrics.top_zones.slice(0, 8)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="zone_name" stroke="#94a3b8" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={70} />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155" }} />
              <Bar dataKey="visits" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6">
          <h2 className="mb-4 text-lg font-semibold">Department Mix (NMV)</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={metrics.department_mix}
                dataKey="nmv"
                nameKey="department"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={({ department, share }) => `${department} ${(share * 100).toFixed(0)}%`}
              >
                {metrics.department_mix.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155" }} formatter={(v: number) => [`₹${v.toLocaleString()}`, "NMV"]} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
