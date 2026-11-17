import { useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import L from "leaflet";
import { JAMMU_CENTER, getLayerStyle, popupHtml, sortLayerNames } from "../layerStyles";

// Zooms the map to all visible layers whenever `signal` changes
function FitToData({ layers, visible, signal }) {
  const map = useMap();
  useEffect(() => {
    if (!signal) return;
    const group = L.featureGroup();
    Object.entries(layers).forEach(([name, data]) => {
      if (visible[name]) group.addLayer(L.geoJSON(data));
    });
    const bounds = group.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [30, 30] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signal]);
  return null;
}

export default function MapView({ layers, visible, refreshId, fitSignal }) {
  const names = sortLayerNames(Object.keys(layers)).filter((n) => visible[n]);

  return (
    <MapContainer center={JAMMU_CENTER} zoom={12} preferCanvas className="map">
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />
      {names.map((name) => (
        <GeoJSON
          key={`${name}-${refreshId}`}
          data={layers[name]}
          style={getLayerStyle(name)}
          onEachFeature={(feature, layer) => {
            const html = popupHtml(feature);
            if (html) layer.bindPopup(html);
          }}
        />
      ))}
      <FitToData layers={layers} visible={visible} signal={fitSignal} />
    </MapContainer>
  );
}
