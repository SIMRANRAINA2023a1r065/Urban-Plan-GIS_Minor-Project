"""Pipeline pieces shared by run.py (one area) and run_tiled.py (district in tiles)."""
import logging
import shutil
from pathlib import Path

import geopandas as gpd

from collectors.open_buildings import OpenBuildingsCollector
from collectors.osm import OSMCollector
from collectors.rasters import RasterCollector
from processing.clean import add_metrics, clean, merge_buildings
from processing.enrich import (add_landcover, add_landuse, add_terrain,
                               landcover_summary, slope_raster)
from processing.quality import coverage, plot_coverage, write_summary
from processing.standardize import (standardize_boundaries, standardize_landuse,
                                    standardize_open_buildings, standardize_osm_buildings,
                                    standardize_osm_roads, standardize_pois)
from storage.writer import write_dictionary, write_outputs

log = logging.getLogger("pipeline")


def safe(label, fn, status):
    """Run one source/step; a failure is recorded in the report, never fatal."""
    try:
        out = fn()
        status[label] = "ok"
        return out
    except Exception as exc:  # noqa: BLE001
        log.exception("%s failed", label)
        status[label] = f"FAILED: {exc}"
        return None


def pick(new, old):
    """Use the enriched layer if the step worked, otherwise keep the original."""
    return old if new is None else new


def collect_osm(ocfg, raw, refresh, fetch_poly, status, tag=""):
    """Download + standardize all OSM layers for one polygon. Returns {layer: gdf or None}."""
    osm = OSMCollector(ocfg, raw, refresh)
    parts = {
        "buildings": safe(f"osm_buildings{tag}", lambda: standardize_osm_buildings(osm.fetch_buildings(fetch_poly)), status),
        "roads": safe(f"osm_roads{tag}", lambda: standardize_osm_roads(osm.fetch_roads(fetch_poly)), status),
    }
    if ocfg.get("fetch_pois", True):
        parts["pois"] = safe(f"osm_pois{tag}", lambda: standardize_pois(osm.fetch_pois(fetch_poly)), status)
    if ocfg.get("fetch_landuse", True):
        parts["landuse"] = safe(f"osm_landuse{tag}", lambda: standardize_landuse(osm.fetch_landuse(fetch_poly)), status)
    if ocfg.get("fetch_boundaries", True) and not tag:   # never per tile: admin boundaries are huge and time out
        parts["boundaries"] = safe(f"osm_boundaries{tag}", lambda: standardize_boundaries(osm.fetch_boundaries(fetch_poly)), status)
    return parts


def finalize(cfg, flags, aoi, metric, raw, out, parts, status):
    """Clean, merge with Open Buildings, enrich, quality-check and write everything."""
    raw, out = Path(raw), Path(out)
    p = cfg["processing"]
    out.mkdir(parents=True, exist_ok=True)

    ob_b = None
    if cfg["open_buildings"]["enabled"] and not flags.get("no_open_buildings"):
        ob = OpenBuildingsCollector(cfg["open_buildings"], raw, flags.get("refresh", False))
        ob_b = safe("open_buildings", lambda: standardize_open_buildings(ob.fetch_buildings(aoi)), status)
    else:
        status["open_buildings"] = "skipped"

    osm_b = clean(parts.get("buildings"), aoi, metric, "buildings", p["min_building_area_m2"])
    ob_b = clean(ob_b, aoi, metric, "buildings", p["min_building_area_m2"])
    buildings = merge_buildings(osm_b, ob_b, metric, p["overlap_threshold"])
    roads = clean(parts.get("roads"), aoi, metric, "roads")
    pois = clean(parts.get("pois"), aoi, metric, "points")
    landuse = clean(parts.get("landuse"), aoi, metric, "polygons")
    bounds = clean(parts.get("boundaries"), aoi, metric, "polygons")

    buildings = add_landuse(buildings, landuse)
    rcfg = cfg.get("rasters", {})
    tifs = {}
    if rcfg.get("enabled", True) and not flags.get("no_rasters"):
        rc = RasterCollector(rcfg, raw, flags.get("refresh", False))
        dem = safe("dem", lambda: rc.fetch_dem(aoi), status)
        if dem:
            slope = safe("slope", lambda: slope_raster(dem, raw / "raster_slope.tif"), status)
            if slope:
                buildings = pick(safe("terrain_buildings", lambda: add_terrain(buildings, dem, slope), status), buildings)
                roads = pick(safe("terrain_roads", lambda: add_terrain(roads, dem, slope), status), roads)
                tifs.update({"dem.tif": dem, "slope.tif": slope})
        lc = safe("landcover", lambda: rc.fetch_landcover(aoi), status)
        if lc:
            buildings = pick(safe("landcover_buildings", lambda: add_landcover(buildings, lc), status), buildings)
            tifs["landcover.tif"] = lc
    else:
        status["rasters"] = "skipped"

    buildings = add_metrics(buildings, metric, "buildings")
    roads = add_metrics(roads, metric, "roads")

    layers = {"buildings": buildings, "roads": roads, "pois": pois, "landuse": landuse, "boundaries": bounds}
    for item in cfg.get("external_layers") or []:
        def load(item=item):
            g = gpd.read_file(item["path"]).to_crs("EPSG:4326")
            return g[g.intersects(aoi)].reset_index(drop=True)
        g = safe(f"external:{item['name']}", load, status)
        if g is not None:
            layers[item["name"]] = g

    grid, summary = coverage(buildings, roads, aoi, metric, p["grid_size_m"])
    summary.update({"pois": 0 if pois is None else int(len(pois)),
                    "landuse_polygons": 0 if landuse is None else int(len(landuse)),
                    "boundaries": 0 if bounds is None else int(len(bounds))})
    if "landcover.tif" in tifs:
        summary["landcover_pct"] = safe("landcover_summary", lambda: landcover_summary(tifs["landcover.tif"], aoi), status)
    layers["coverage_grid"] = grid

    plot_coverage(grid, out / "coverage_map.png")
    write_summary(summary, status, out / "coverage_summary.json")
    gpkg = write_outputs(layers, out, cfg["output"]["gpkg_name"], cfg["output"]["write_geojson"])
    for name, path in tifs.items():
        shutil.copy(path, out / name)
    graph = raw / "osm_roads_graph.graphml"
    if graph.exists():
        shutil.copy(graph, out / "roads_graph.graphml")
    write_dictionary(out)

    log.info("DONE -> %s", gpkg)
    log.info("summary: %s", summary)
    failed = [k for k, v in status.items() if str(v).startswith("FAILED")]
    if failed:
        log.warning("%d step(s) FAILED: %s", len(failed), failed)
        log.warning("Run the same command again WITHOUT --refresh: finished tiles are cached, only failures are retried.")
    return gpkg
