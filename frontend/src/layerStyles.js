// Map centre (Jammu) and everything that decides how each layer looks.
export const JAMMU_CENTER = [32.7266, 74.857];

export const COLORS = {
  building: "#e11d48",
  road: "#2563eb",
  good: "#16a34a",
  poor: "#7f1d1d", // CHANGED: dark maroon (was orange #f97316)
  poorEdge: "#450a0a", // NEW: near-black outline for poor buildings
  settlementPoor: "#dc2626",
  settlementOk: "#0ea5e9",
  vegLoss: "#7c2d12",
  vegGain: "#15803d",
};

export const LAYER_META = {
  buildings: { label: "Buildings", color: COLORS.building },
  roads: { label: "Roads", color: COLORS.road },
  buildings_connectivity: {
    label: "Buildings (connectivity)",
    color: COLORS.poor,
  },
  settlements: { label: "Settlements", color: COLORS.settlementPoor },
  vegetation_loss: { label: "Vegetation loss", color: COLORS.vegLoss },
  vegetation_gain: { label: "Vegetation gain", color: COLORS.vegGain },
};

// Draw order: first = bottom, last = top
const LAYER_ORDER = [
  "vegetation_gain",
  "vegetation_loss",
  "settlements",
  "buildings",
  "buildings_connectivity",
  "roads",
];

export const sortLayerNames = (names) =>
  [...names].sort((a, b) => LAYER_ORDER.indexOf(a) - LAYER_ORDER.indexOf(b));

export const isTrue = (v) =>
  v === true || v === 1 || v === "1" || String(v).toLowerCase() === "true";

export function getLayerStyle(name) {
  switch (name) {
    case "buildings":
      return () => ({ color: COLORS.building, weight: 1, fillOpacity: 0.4 });
    case "roads":
      return () => ({ color: COLORS.road, weight: 3, opacity: 0.9 });
    case "buildings_connectivity":
      return (f) => {
        const poor = isTrue(f?.properties?.poor);
        return poor
          ? {
              color: COLORS.poorEdge,
              fillColor: COLORS.poor,
              weight: 2,
              fillOpacity: 0.95,
            }
          : {
              color: COLORS.good,
              fillColor: COLORS.good,
              weight: 1,
              fillOpacity: 0.65,
            };
      };
    case "settlements":
      return (f) =>
        isTrue(f?.properties?.poorly_connected)
          ? {
              color: COLORS.settlementPoor,
              fillColor: COLORS.settlementPoor,
              weight: 3,
              fillOpacity: 0.12,
            }
          : {
              color: COLORS.settlementOk,
              fillColor: COLORS.settlementOk,
              weight: 2,
              fillOpacity: 0.08,
            };
    case "vegetation_loss":
      return () => ({
        color: COLORS.vegLoss,
        fillColor: COLORS.vegLoss,
        weight: 1,
        fillOpacity: 0.6,
      });
    case "vegetation_gain":
      return () => ({
        color: COLORS.vegGain,
        fillColor: COLORS.vegGain,
        weight: 1,
        fillOpacity: 0.6,
      });
    default:
      return () => ({ color: "#64748b", weight: 1, fillOpacity: 0.3 });
  }
}

// ---- feature popups ----
const FIELD_LABELS = {
  area_m2: "Area (m²)",
  length_m: "Length (m)",
  dist_to_road: "Distance to road (m)",
  road_comp_len: "Connected road length (m)",
  poor: "Poorly connected",
  buildings: "Buildings in settlement",
  mean_dist_m: "Mean distance to road (m)",
  pct_poor: "Poorly connected (%)",
  poorly_connected: "Poorly connected",
};
const BOOL_FIELDS = ["poor", "poorly_connected"];

const esc = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );

export function popupHtml(feature) {
  const p = feature?.properties || {};
  const rows = Object.keys(FIELD_LABELS)
    .filter((k) => p[k] !== undefined && p[k] !== null)
    .map((k) => {
      const v = BOOL_FIELDS.includes(k) ? (isTrue(p[k]) ? "Yes" : "No") : p[k];
      return `<tr><td style="padding-right:10px;color:#475569">${esc(FIELD_LABELS[k])}</td><td><b>${esc(v)}</b></td></tr>`;
    });
  return rows.length
    ? `<table style="font-size:12px">${rows.join("")}</table>`
    : null;
}
