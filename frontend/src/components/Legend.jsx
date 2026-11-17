import { COLORS } from "../layerStyles";

const ITEMS = [
  { label: "Buildings", color: COLORS.building, type: "fill" },
  { label: "Roads", color: COLORS.road, type: "line" },
  { label: "Well-connected buildings", color: COLORS.good, type: "fill" },
  { label: "Poorly connected buildings", color: COLORS.poor, type: "fill" },
  { label: "Poorly connected settlement", color: COLORS.settlementPoor, type: "outline" },
  { label: "Other settlement", color: COLORS.settlementOk, type: "outline" },
  { label: "Vegetation loss", color: COLORS.vegLoss, type: "fill" },
  { label: "Vegetation gain", color: COLORS.vegGain, type: "fill" },
];

export default function Legend() {
  return (
    <div className="legend">
      <div className="legend-title">Legend</div>
      {ITEMS.map(({ label, color, type }) => (
        <div className="legend-row" key={label}>
          <span
            className={`swatch ${type}`}
            style={type === "outline" ? { borderColor: color } : { background: color }}
          />
          {label}
        </div>
      ))}
    </div>
  );
}
