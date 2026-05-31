export interface MetricsResponse {
  store_id: string;
  store_name: string;
  date: string;
  footfall: {
    total_entries: number;
    unique_sessions: number;
    staff_excluded: number;
    re_entries: number;
  };
  engagement: {
    engaged_visits: number;
    engagement_rate: number;
    avg_dwell_sec: number;
    avg_zones_per_visit: number;
  };
  conversion: {
    checkout_proximity_visits: number;
    pos_transactions: number;
    matched_conversions: number;
    conversion_rate: number;
    conversion_rate_vs_pos: number;
    unmatched_pos: number;
  };
  revenue: {
    total_nmv: number;
    avg_basket_nmv: number;
    avg_items_per_transaction: number;
    revenue_per_visitor: number;
  };
  hourly: Array<{
    hour: string;
    entries: number;
    transactions: number;
    nmv: number;
    conversion_rate: number;
  }>;
  top_zones: Array<{
    zone_id: string;
    zone_name: string;
    visits: number;
    avg_dwell_sec: number;
  }>;
  department_mix: Array<{
    department: string;
    nmv: number;
    qty: number;
    share: number;
  }>;
  computed_at: string;
}

export interface FunnelResponse {
  store_id: string;
  date: string;
  funnel_type: string;
  stages: Array<{
    stage: string;
    stage_order: number;
    count: number;
    pct_of_top: number;
    drop_off_from_prev: number | null;
    definition: string | null;
  }>;
  notes: string;
}

export interface AnomalyItem {
  anomaly_id: string;
  anomaly_type: string;
  severity: string;
  detected_at: string;
  description: string;
  zone_id: string | null;
}

export interface AnomaliesResponse {
  total: number;
  items: AnomalyItem[];
}

const API_BASE = "/api/v1";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  metrics: () => fetchJson<MetricsResponse>("/metrics"),
  funnel: () => fetchJson<FunnelResponse>("/funnel"),
  anomalies: () => fetchJson<AnomaliesResponse>("/anomalies?limit=20"),
};
