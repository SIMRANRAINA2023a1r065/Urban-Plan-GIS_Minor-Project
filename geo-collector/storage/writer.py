"""Write final outputs: one GeoPackage (+ optional GeoJSON copies)."""
import logging
from pathlib import Path

from collectors.base import make_storable

log = logging.getLogger(__name__)


def write_outputs(layers, out_dir, gpkg_name, write_geojson=True):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gpkg = out_dir / gpkg_name
    if gpkg.exists():
        gpkg.unlink()
    for name, gdf in layers.items():
        if gdf is None or gdf.empty:
            log.warning("layer '%s' is empty, skipped", name)
            continue
        gdf = make_storable(gdf)
        gdf.to_file(gpkg, layer=name, driver="GPKG")
        if write_geojson:
            gdf.to_file(out_dir / f"{name}.geojson", driver="GeoJSON")
        log.info("wrote layer '%s' (%d rows)", name, len(gdf))
    return gpkg


DATA_DICTIONARY = """# Data dictionary - Phase 1 dataset

All vector layers are EPSG:4326 (lon/lat). Areas/lengths were computed in a local UTM CRS (metres).

| Layer | Geometry | Columns |
|---|---|---|
| buildings | Polygon | id, source (osm / open_buildings), source_id, class, levels, height_m, confidence, area_m2, elevation_m, slope_deg, landcover, landuse |
| roads | LineString | id, source, source_id, class (OSM highway type), name, lanes, maxspeed_kmh, oneway, length_m, elevation_m, slope_deg |
| pois | Point | source, source_id, category (OSM key), type (OSM value), name |
| landuse | Polygon | source, source_id, class_key, class, name |
| boundaries | Polygon | source, source_id, admin_level, name |
| coverage_grid | Polygon (500 m cells) | cell_id, n_buildings_*, n_buildings, road_km, no_buildings, no_roads, empty_cell |

Other files: roads_graph.graphml (routable road graph), dem.tif (elevation, m), slope.tif (degrees),
landcover.tif (ESA WorldCover classes), coverage_map.png, coverage_summary.json (counts, gaps, source status).

Sources: (c) OpenStreetMap contributors (ODbL); Open Buildings / other footprint file (check its licence);
Copernicus GLO-30 DEM; ESA WorldCover 2021. Cite them in your report.
"""


def write_dictionary(out_dir):
    (Path(out_dir) / "DATA_DICTIONARY.md").write_text(DATA_DICTIONARY, encoding="utf-8")
