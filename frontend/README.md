# Urban Planning Intelligence: Frontend

React + Vite + Leaflet interface for **Automated Urban Planning Intelligence from GIS Data**.

## Run

```bash
cd frontend
npm install
npm run dev          # opens at http://localhost:5173
```

The backend (FastAPI) must be running at `http://localhost:8000`.
If it runs somewhere else, copy `.env.example` to `.env` and change `VITE_API_URL`.

## What it does

| Sidebar section | Backend call |
|---|---|
| 1. Extract buildings / roads (GeoTIFF) | `POST /api/buildings/extract`, `POST /api/roads/extract` (form field `image`) |
| 1. Demo mode: upload GeoJSON | `POST /api/layers/upload/{buildings or roads}` (form field `file`) |
| 2. Find poorly connected areas | `POST /api/connectivity` (form field `max_dist`) |
| 3. Analyse green cover | `POST /api/vegetation/change` (form fields `before`, `after`, `red`, `nir`) |
| Layers, map, statistics | `GET /api/layers`, `GET /api/layers/{name}`, `GET /api/stats` |

After every action the app reloads all layers and statistics.

## Structure

```
frontend/
├── package.json
├── vite.config.js
├── index.html
├── .env.example
└── src/
    ├── main.jsx            entry
    ├── App.jsx             state, actions, layout
    ├── api.js              all backend calls
    ├── layerStyles.js      colours, layer styles, popups
    ├── styles.css
    └── components/
        ├── Sidebar.jsx     uploads, buttons, layer toggles
        ├── MapView.jsx     Leaflet map
        ├── StatsPanel.jsx  statistic cards
        └── Legend.jsx
```
