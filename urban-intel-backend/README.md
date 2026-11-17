# Urban Intel Backend (FastAPI)

Backend for the React/Leaflet frontend (`urban-intel-ui`). Matches the frontend README's API contract.

## Run
```bash
cd urban-intel-backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```
Docs: http://localhost:8000/docs. Then, in another terminal: `cd frontend && npm install && npm run dev`.

If `pip install rasterio` fails on Windows, use conda: `conda install -c conda-forge rasterio shapely pyproj scikit-image scipy` then pip install the rest.

## Endpoints
| Call | Notes |
|---|---|
| POST /api/buildings/extract | form `image` (GeoTIFF, RGB) |
| POST /api/roads/extract | form `image` (GeoTIFF, RGB) |
| POST /api/layers/upload/{buildings\|roads} | form `file` (GeoJSON, EPSG:4326) |
| POST /api/connectivity | form `max_dist` (m): buildings farther than this from any road -> `poorly_connected` |
| POST /api/vegetation/change | forms `before`, `after`, `red`, `nir` (1-based bands); NDVI diff -> `vegetation_loss` / `vegetation_gain` |
| GET /api/layers, /api/layers/{name}, /api/stats | layers: buildings, roads, poorly_connected, vegetation_loss, vegetation_gain |
| DELETE /api/layers | reset everything |

## Notes
- Extraction is a classical image-processing baseline (brightness/greenness thresholds, morphology,
  skeleton tracing), not a trained model. Good for demos on clear imagery; swap `segment_buildings` /
  `segment_roads` for a deep-learning model later.
- Rasters over 2048 px are downsampled; GeoTIFFs must be georeferenced.
- Layers persist in `./data/`.
