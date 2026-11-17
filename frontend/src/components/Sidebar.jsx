import { useState } from "react";
import * as api from "../api";
import { LAYER_META, sortLayerNames } from "../layerStyles";
import StatsPanel from "./StatsPanel";

function FileInput({ id, label, accept, file, onChange, disabled }) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <label className={`file-pick ${disabled ? "disabled" : ""}`} htmlFor={id}>
        <span className="file-btn">Choose file</span>
        <span className="file-name">{file ? file.name : "No file selected"}</span>
      </label>
      <input
        id={id}
        type="file"
        accept={accept}
        hidden
        disabled={disabled}
        onChange={(e) => onChange(e.target.files[0] || null)}
      />
    </div>
  );
}

export default function Sidebar({ layerNames, visible, onToggle, stats, busy, run, onFit }) {
  const [img, setImg] = useState(null);
  const [bGeo, setBGeo] = useState(null);
  const [rGeo, setRGeo] = useState(null);
  const [dist, setDist] = useState(100);
  const [before, setBefore] = useState(null);
  const [after, setAfter] = useState(null);
  const [red, setRed] = useState(1);
  const [nir, setNir] = useState(4);

  const off = !!busy;
  const canConnect = layerNames.includes("buildings") && layerNames.includes("roads");
  const TIF = ".tif,.tiff";
  const GEO = ".geojson,.json";

  return (
    <aside className="sidebar">
      <header className="brand">
        <h1>Urban Planning Intelligence</h1>
        <p>Automated Urban Planning Intelligence from GIS Data</p>
      </header>

      <section className="panel">
        <h2><span className="step">1</span> Buildings and roads</h2>
        <FileInput id="img" label="Drone image (GeoTIFF)" accept={TIF} file={img} onChange={setImg} disabled={off} />
        <button
          className="btn primary"
          disabled={!img || off}
          onClick={() => run("Extracting buildings…", () => api.extractBuildings(img), "Buildings extracted.")}
        >
          Extract buildings (JDA)
        </button>
        <button
          className="btn primary"
          disabled={!img || off}
          onClick={() => run("Extracting roads…", () => api.extractRoads(img), "Roads extracted.")}
        >
          Extract roads (PWD)
        </button>

        <details className="demo">
          <summary>Demo mode: upload GeoJSON instead</summary>
          <p className="hint">Use this when no trained model is available.</p>
          <FileInput id="bgeo" label="Buildings GeoJSON" accept={GEO} file={bGeo} onChange={setBGeo} disabled={off} />
          <button
            className="btn"
            disabled={!bGeo || off}
            onClick={() => run("Uploading buildings…", () => api.uploadLayer("buildings", bGeo), "Buildings layer uploaded.")}
          >
            Upload buildings
          </button>
          <FileInput id="rgeo" label="Roads GeoJSON" accept={GEO} file={rGeo} onChange={setRGeo} disabled={off} />
          <button
            className="btn"
            disabled={!rGeo || off}
            onClick={() => run("Uploading roads…", () => api.uploadLayer("roads", rGeo), "Roads layer uploaded.")}
          >
            Upload roads
          </button>
        </details>
      </section>

      <section className="panel">
        <h2><span className="step">2</span> Road connectivity</h2>
        <div className="field">
          <label className="field-label" htmlFor="dist">Max distance to road (m)</label>
          <input id="dist" className="input" type="number" min="1" value={dist} onChange={(e) => setDist(e.target.value)} disabled={off} />
        </div>
        <button
          className="btn primary"
          disabled={!canConnect || off}
          onClick={() =>
            run("Analysing connectivity…", () => api.analyseConnectivity(Number(dist) || 100), "Connectivity analysis complete.")
          }
        >
          Find poorly connected areas
        </button>
        {!canConnect && <p className="hint">Needs both a buildings layer and a roads layer.</p>}
      </section>

      <section className="panel">
        <h2><span className="step">3</span> Green cover (NDVI)</h2>
        <FileInput id="before" label="Before (GeoTIFF)" accept={TIF} file={before} onChange={setBefore} disabled={off} />
        <FileInput id="after" label="After (GeoTIFF)" accept={TIF} file={after} onChange={setAfter} disabled={off} />
        <div className="row">
          <div className="field">
            <label className="field-label" htmlFor="red">Red band</label>
            <input id="red" className="input" type="number" min="1" value={red} onChange={(e) => setRed(e.target.value)} disabled={off} />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="nir">NIR band</label>
            <input id="nir" className="input" type="number" min="1" value={nir} onChange={(e) => setNir(e.target.value)} disabled={off} />
          </div>
        </div>
        <p className="hint">Drone RGB+NIR: red 1, NIR 4. Sentinel-2 stacked B4+B8: red 1, NIR 2.</p>
        <button
          className="btn primary"
          disabled={!before || !after || off}
          onClick={() =>
            run(
              "Analysing green cover…",
              () => api.analyseVegetation(before, after, Number(red) || 1, Number(nir) || 4),
              "Green cover analysis complete."
            )
          }
        >
          Analyse green cover
        </button>
      </section>

      <section className="panel">
        <h2>Layers</h2>
        {layerNames.length === 0 && <p className="hint">No layers yet.</p>}
        {sortLayerNames(layerNames).reverse().map((n) => (
          <label key={n} className="layer-row">
            <input type="checkbox" checked={!!visible[n]} onChange={() => onToggle(n)} />
            <span className="dot" style={{ background: LAYER_META[n]?.color || "#64748b" }} />
            {LAYER_META[n]?.label || n}
          </label>
        ))}
        <button className="btn" onClick={onFit} disabled={layerNames.length === 0}>
          Zoom to data
        </button>
      </section>

      <section className="panel">
        <h2>Statistics</h2>
        <StatsPanel stats={stats} />
      </section>
    </aside>
  );
}
