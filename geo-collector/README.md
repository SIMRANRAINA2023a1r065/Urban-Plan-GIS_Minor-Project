# Geo data collector - Phase 1 (Jammu)

Builds the Phase 1 dataset for the Urban Planning and Connectivity modules from open sources and
reports where the data is incomplete.

## What it collects
| Layer / file | Source | Used for |
|---|---|---|
| `buildings` (footprint, class, levels, height, area, elevation, slope, land cover, land use) | OSM + Open Buildings | Urban Planning |
| `roads` (class, name, lanes, speed, one-way, length, elevation, slope) + `roads_graph.graphml` | OSM | Connectivity |
| `pois` (schools, hospitals, markets, bus stops, stations ...) | OSM | Both |
| `landuse` (residential, commercial, forest, water, parks ...) | OSM | Urban Planning |
| `boundaries` (administrative) | OSM | Both |
| any extra layers (e.g. ward boundaries) | your local files in `data/external/` | Both |
| `dem.tif`, `slope.tif` | Copernicus GLO-30 | Connectivity (hilly terrain) |
| `landcover.tif` | ESA WorldCover 2021 | Urban Planning |
| `coverage_map.png`, `coverage_summary.json`, `DATA_DICTIONARY.md` | computed | Report |

Everything lands in `data/processed/` (one `jammu_phase1.gpkg` plus GeoJSON/GeoTIFF copies).

## Setup (once)
```
cd C:\projects\geo-collector
conda env create -f environment.yml
conda activate geo
pytest            # 16 tests should pass
```

## Run
```
python run.py                      # everything
python run.py --no-open-buildings  # OSM only
python run.py --no-rasters         # skip terrain / land cover
python run.py --refresh            # re-download instead of using cache
```
Edit `config.yaml` for the area (`bbox` = west, south, east, north). Start small, then widen.

## Whole district (tile by tile)
```
python run_tiled.py --config config_district.yaml --list-tiles                      # preview area and tiles, no download
python run_tiled.py --config config_district.yaml --no-open-buildings --no-rasters   # run
python run_tiled.py --config config_district.yaml --no-open-buildings --no-rasters   # run AGAIN (no --refresh) to retry failed tiles
```
Each tile has its own cache (`data/raw_district/tiles/`), every feature is kept by exactly one tile (no duplicates, nothing cut at tile edges), and all tiles are merged into `data/processed_district/jammu_district.gpkg`. The city data in `data/processed/` is untouched.

## Week plan
- **Day 1:** setup, small bbox, run with `--no-open-buildings --no-rasters`, view in QGIS.
- **Day 2:** check roads/buildings/POIs against satellite view in QGIS; run the road-graph check; write findings.
- **Day 3:** download the Open Buildings tile (check licence) to `data/external/open_buildings_jammu.csv.gz`; run `python run.py`.
- **Day 4:** run with rasters on. If the remote DEM / land-cover download fails, download the GeoTIFF manually and set `rasters.dem_path` / `landcover_path`. Tune `overlap_threshold`, `min_building_area_m2`.
- **Day 5:** add external layers (ward boundaries from Jammu University / municipal data) in `external_layers`; widen `bbox` to the full city.
- **Day 6:** validate a sample against imagery, record error rates, run `pytest`, check `source_status` in `coverage_summary.json`.
- **Day 7:** write summary, back up `data/processed/` and `config.yaml` (Drive + external drive), demo.

## Notes
- A failed source never stops the run: it is recorded under `source_status` in `coverage_summary.json`.
- Remote raster URLs follow the public Copernicus / ESA AWS bucket layouts; verify them on first run.
- Licences: OSM (ODbL, attribute "(c) OpenStreetMap contributors"), Open Buildings, Copernicus DEM, ESA WorldCover - cite all.
- Not covered by code: drone/orthophoto imagery for the AI model, and official municipal data. These need a separate source / formal request.
