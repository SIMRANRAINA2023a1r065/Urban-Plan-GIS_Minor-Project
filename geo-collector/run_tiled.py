"""Whole-district pipeline: splits the AOI into tiles, downloads each tile into its own cache,
merges everything (no duplicates at tile edges) into ONE GeoPackage.

   python run_tiled.py --list-tiles            # preview tiles, no download (writes tiles.gpkg)
   python run_tiled.py --no-rasters            # run
   python run_tiled.py --no-rasters            # run AGAIN (no --refresh) to retry failed tiles
"""
import argparse
import logging
from pathlib import Path

import geopandas as gpd
import yaml

from aoi import build_aoi, union
from pipeline import collect_osm, finalize
from tiling import combine, make_tiles, merge_graphs

log = logging.getLogger("run_tiled")


def run_tiled(cfg, flags, list_only=False):
    raw, out = Path(cfg["paths"]["raw_dir"]), Path(cfg["paths"]["processed_dir"])
    tcfg = cfg.get("tiling", {})
    aoi_gdf = build_aoi(cfg["aoi"])
    aoi = union(aoi_gdf.geometry)
    metric = aoi_gdf.estimate_utm_crs()
    tiles = make_tiles(aoi, tcfg.get("tile_km", 10), tcfg.get("overlap_deg", 0.001))

    out.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({"tile": [t["id"] for t in tiles]}, geometry=[t["core"] for t in tiles],
                     crs="EPSG:4326").to_file(out / "tiles.gpkg", driver="GPKG")
    if list_only:
        log.info("%d tiles written to %s (open it in QGIS to preview)", len(tiles), out / "tiles.gpkg")
        return None

    status, results = {}, []
    for k, t in enumerate(tiles, 1):
        log.info("=== tile %d/%d (%s) ===", k, len(tiles), t["id"])
        parts = collect_osm(cfg["osm"], raw / "tiles" / t["id"], flags.get("refresh", False),
                            t["fetch"], status, tag=f"@{t['id']}")
        results.append((t, parts))

    graphs = sorted((raw / "tiles").glob("*/osm_roads_graph.graphml"))
    if graphs:
        status["road_graph_merge"] = "ok" if merge_graphs(graphs, raw / "osm_roads_graph.graphml") else "empty"
    combined = combine(results)
    return finalize(cfg, flags, aoi, metric, raw, out, combined, status)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--refresh", action="store_true", help="re-download everything (do NOT use to retry failures)")
    ap.add_argument("--no-open-buildings", action="store_true")
    ap.add_argument("--no-rasters", action="store_true")
    ap.add_argument("--list-tiles", action="store_true", help="only show the tiles, no download")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load(open(args.config))
    flags = {"refresh": args.refresh, "no_open_buildings": args.no_open_buildings, "no_rasters": args.no_rasters}
    run_tiled(cfg, flags, args.list_tiles)


if __name__ == "__main__":
    main()
