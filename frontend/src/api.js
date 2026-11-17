// All backend calls live here. Change VITE_API_URL in .env if the backend is elsewhere.
export const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new Error(`Cannot reach the backend at ${BASE}. Is it running?`);
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) {
        msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* response had no JSON body */
    }
    throw new Error(msg);
  }
  return res.json();
}

const form = (fields) => {
  const f = new FormData();
  Object.entries(fields).forEach(([k, v]) => f.append(k, v));
  return f;
};

export const getLayers = () => request("/layers");
export const getLayer = (name) => request(`/layers/${name}`);
export const getStats = () => request("/stats");

// Module 1: Urban planning (JDA) and road connectivity (PWD)
export const extractBuildings = (image) =>
  request("/buildings/extract", { method: "POST", body: form({ image }) });
export const extractRoads = (image) =>
  request("/roads/extract", { method: "POST", body: form({ image }) });
export const uploadLayer = (name, file) =>
  request(`/layers/upload/${name}`, { method: "POST", body: form({ file }) });

// Module 2: connectivity analysis
export const analyseConnectivity = (maxDist) =>
  request("/connectivity", { method: "POST", body: form({ max_dist: maxDist }) });

// Module 3: sustainable development (NDVI)
export const analyseVegetation = (before, after, red, nir) =>
  request("/vegetation/change", {
    method: "POST",
    body: form({ before, after, red, nir }),
  });
