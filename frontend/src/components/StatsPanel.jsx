const SECTIONS = [
  {
    key: "buildings",
    title: "Buildings (JDA)",
    items: [
      ["count", "Buildings"],
      ["built_up_area_m2", "Built-up area (m²)"],
    ],
  },
  {
    key: "roads",
    title: "Roads (PWD)",
    items: [
      ["segments", "Road segments"],
      ["length_km", "Total length (km)"],
    ],
  },
  {
    key: "connectivity",
    title: "Connectivity",
    items: [
      ["buildings", "Buildings analysed"],
      ["poorly_connected_buildings", "Poorly connected buildings", true],
      ["settlements", "Settlements"],
      ["poorly_connected_settlements", "Poorly connected settlements", true],
    ],
  },
  {
    key: "vegetation",
    title: "Green cover (NDVI)",
    items: [
      ["mean_ndvi_t1", "Mean NDVI (before)"],
      ["mean_ndvi_t2", "Mean NDVI (after)"],
      ["green_cover_pct_t1", "Green cover before (%)"],
      ["green_cover_pct_t2", "Green cover after (%)"],
      ["loss_area_ha", "Vegetation loss (ha)", true],
    ],
  },
];

const fmt = (v) =>
  typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v);

export default function StatsPanel({ stats }) {
  const shown = SECTIONS.filter((s) => stats && stats[s.key]);
  if (!shown.length) {
    return <p className="hint">No results yet. Run an action above to see statistics.</p>;
  }
  return (
    <div>
      {shown.map((s) => (
        <div key={s.key} className="stat-group">
          <div className="stat-title">{s.title}</div>
          <div className="stat-grid">
            {s.items
              .filter(([k]) => stats[s.key][k] !== undefined)
              .map(([k, label, warn]) => (
                <div className={`stat-card ${warn ? "warn" : ""}`} key={k}>
                  <div className="stat-value">{fmt(stats[s.key][k])}</div>
                  <div className="stat-label">{label}</div>
                </div>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
