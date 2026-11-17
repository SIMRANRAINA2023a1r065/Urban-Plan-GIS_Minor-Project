"""One-area pipeline (city / bbox):
   python run.py [--config config.yaml] [--refresh] [--no-open-buildings] [--no-rasters]
For a whole district use run_tiled.py instead."""
import argparse
import logging
from pathlib import Path

import yaml

from aoi import build_aoi, union
from pipeline import collect_osm, finalize

log = logging.getLogger("run")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--refresh", action="store_true", help="ignore cached downloads")
    ap.add_argument("--no-open-buildings", action="store_true")
    ap.add_argument("--no-rasters", action="store_true", help="skip DEM / land cover")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = yaml.safe_load(open(args.config))
    raw, out = Path(cfg["paths"]["raw_dir"]), Path(cfg["paths"]["processed_dir"])
    aoi_gdf = build_aoi(cfg["aoi"])
    aoi = union(aoi_gdf.geometry)
    metric = aoi_gdf.estimate_utm_crs()
    log.info("AOI bounds %s | metric CRS %s", [round(x, 4) for x in aoi.bounds], metric)

    status = {}
    parts = collect_osm(cfg["osm"], raw, args.refresh, aoi, status)
    flags = {"refresh": args.refresh, "no_open_buildings": args.no_open_buildings, "no_rasters": args.no_rasters}
    finalize(cfg, flags, aoi, metric, raw, out, parts, status)
    log.info("source status: %s", status)


if __name__ == "__main__":
    main()
