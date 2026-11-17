import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import Sidebar from "./components/Sidebar";
import MapView from "./components/MapView";
import Legend from "./components/Legend";

export default function App() {
  const [layers, setLayers] = useState({}); // name -> GeoJSON
  const [visible, setVisible] = useState({}); // name -> boolean
  const [stats, setStats] = useState({});
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState(null); // { type: "error" | "success", text }
  const [refreshId, setRefreshId] = useState(0);
  const [fitSignal, setFitSignal] = useState(0);
  const hadData = useRef(false);

  const notify = useCallback((type, text) => {
    setNotice({ type, text });
    if (type === "success") setTimeout(() => setNotice(null), 4000);
  }, []);

  // Reload every layer + the statistics from the backend
  const refresh = useCallback(async () => {
    const names = await api.getLayers();
    const entries = await Promise.all(names.map(async (n) => [n, await api.getLayer(n)]));
    setLayers(Object.fromEntries(entries));
    setVisible((prev) => {
      const next = {};
      names.forEach((n) => (next[n] = prev[n] ?? true));
      // when the connectivity layer first appears, hide the plain buildings layer under it
      if (prev.buildings_connectivity === undefined && names.includes("buildings_connectivity")) {
        next.buildings = false;
      }
      return next;
    });
    setStats(await api.getStats());
    setRefreshId((id) => id + 1);
    if (!hadData.current && names.length > 0) {
      hadData.current = true;
      setFitSignal((s) => s + 1); // zoom to the data the first time it appears
    }
  }, []);

  useEffect(() => {
    refresh().catch((e) => notify("error", e.message));
  }, [refresh, notify]);

  // Run a backend action, then reload layers and stats
  const run = useCallback(
    async (label, fn, successText) => {
      setBusy(label);
      setNotice(null);
      try {
        await fn();
        await refresh();
        if (successText) notify("success", successText);
      } catch (e) {
        notify("error", e.message);
      } finally {
        setBusy("");
      }
    },
    [refresh, notify]
  );

  const toggle = (name) => setVisible((v) => ({ ...v, [name]: !v[name] }));

  return (
    <div className="app">
      <Sidebar
        layerNames={Object.keys(layers)}
        visible={visible}
        onToggle={toggle}
        stats={stats}
        busy={busy}
        run={run}
        onFit={() => setFitSignal((s) => s + 1)}
      />
      <main className="map-wrap">
        <MapView layers={layers} visible={visible} refreshId={refreshId} fitSignal={fitSignal} />
        <Legend />
        {busy && (
          <div className="busy">
            <span className="spinner" /> {busy}
          </div>
        )}
        {notice && (
          <div className={`notice ${notice.type}`} role="alert">
            <span>{notice.text}</span>
            <button onClick={() => setNotice(null)} aria-label="Dismiss">
              ×
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
