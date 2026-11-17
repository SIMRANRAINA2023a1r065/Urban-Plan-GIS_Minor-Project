"""Open Buildings (Google) / any building-footprint file collector.

The big tile files are downloaded manually once (see README, Day 3) and placed in
data/external/. This collector reads only the part inside the AOI.
Works with Google Open Buildings CSV/CSV.GZ (WKT geometry column) and any vector
file geopandas can read (GeoJSON, GeoPackage, GeoParquet, Shapefile).
"""
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from .base import BaseCollector

log = logging.getLogger(__name__)
WANTED = {"latitude", "longitude", "area_in_meters", "confidence", "geometry"}


class OpenBuildingsCollector(BaseCollector):
    name = "open_buildings"

    def fetch_buildings(self, aoi_poly):
        cached = self.load_cache("buildings")
        if cached is not None:
            return cached
        gdf = self._read(aoi_poly)
        self.save_cache(gdf, "buildings")
        return gdf

    def _read(self, aoi_poly):
        path = Path(self.cfg.get("path", ""))
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Download the footprint tile covering your AOI and place it "
                "there (README Day 3), or set open_buildings.enabled: false to run OSM-only.")
        west, south, east, north = aoi_poly.bounds
        name = path.name.lower()
        if name.endswith((".csv", ".csv.gz")):
            parts = []
            for chunk in pd.read_csv(path, chunksize=200_000, usecols=lambda c: c in WANTED):
                inside = chunk[chunk.longitude.between(west, east) & chunk.latitude.between(south, north)]
                if not inside.empty:
                    parts.append(inside)
            if not parts:
                log.warning("[open_buildings] no rows inside the AOI bbox")
                return self.empty()
            df = pd.concat(parts, ignore_index=True)
            geoms = shapely.from_wkt(df["geometry"].values)
            gdf = gpd.GeoDataFrame(df.drop(columns=["geometry"]), geometry=geoms, crs="EPSG:4326")
        else:
            gdf = gpd.read_file(path, bbox=(west, south, east, north)).to_crs("EPSG:4326")

        if "confidence" in gdf.columns:
            gdf = gdf[gdf["confidence"] >= self.cfg.get("min_confidence", 0.0)]
        gdf = gdf[gdf.intersects(aoi_poly)].reset_index(drop=True)
        log.info("[open_buildings] %d footprints in AOI", len(gdf))
        return gdf
