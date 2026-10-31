import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltip } from "./charts";

const LABELS: Record<string, string> = {
  amount: "Amount", log_amount: "Amount (log)", txn_count_1h: "Txns past 1h", txn_count_24h: "Txns past 24h", txn_count_7d: "Txns past 7d",
  hours_since_prev: "Hours since prev", cust_avg_amount: "Customer avg", amount_to_avg_ratio: "Amount ÷ avg", amount_zscore: "Amount z-score",
  merchant_risk_score: "Merchant risk", merchant_high_risk_category: "High-risk category", is_p2p_transfer: "P2P transfer",
  device_distinct_customers: "Accounts on device", device_new_for_customer: "New device", customer_distinct_devices_30d: "Devices (30d)",
  geo_distance_prev_km: "Km from prev", geo_velocity_kmh: "Travel speed", distance_from_home_km: "Km from home", failed_count_24h: "Failed 24h",
  failed_count_7d: "Failed 7d", destination_distinct_customers: "Payers to dest.", destination_flagged: "Flagged dest.",
  customer_flagged_dest_interactions: "Prior flagged-dest pays", hour_of_day: "Hour (UTC)", is_night: "Night", is_first_txn: "First txn",
};

export const featureLabel = (f: string) => LABELS[f] ?? f;

export default function ShapChart({ values, features, top = 8, height = 230 }: {
  values: Record<string, number>; features?: Record<string, number | null>; top?: number; height?: number;
}) {
  const data = Object.entries(values)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, top)
    .map(([f, v]) => ({ feature: featureLabel(f), shap: Number(v.toFixed(4)), value: features?.[f] }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 4, right: 12, top: 4, bottom: 4 }}>
        <XAxis type="number" hide domain={["dataMin", "dataMax"]} />
        <YAxis type="category" dataKey="feature" width={118} tick={{ fill: "#9aa6ba", fontSize: 11 }} axisLine={false} tickLine={false} />
        <ReferenceLine x={0} stroke="#3a4559" />
        <Tooltip cursor={{ fill: "rgba(255,255,255,.03)" }} content={<ChartTooltip fmt={(v) => (v > 0 ? "+" : "") + v.toFixed(4)} />} />
        <Bar dataKey="shap" name="SHAP contribution" radius={[2, 2, 2, 2]} barSize={12}>
          {data.map((d) => <Cell key={d.feature} fill={d.shap > 0 ? "#f43f5e" : "#34d399"} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
