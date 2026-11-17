"""Shared plumbing for every collector: retries, raw-data cache, logging."""
import functools
import logging
import time
from pathlib import Path

import geopandas as gpd

log = logging.getLogger(__name__)


def retry(times=3, delay=5, backoff=2):
    """Retry a flaky network call with exponential backoff."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    if attempt == times:
                        raise
                    log.warning("%s failed (%s). Retry %d/%d in %ss",
                                fn.__name__, exc, attempt, times - 1, wait)
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return deco


def _flatten(v):
    if isinstance(v, (list, tuple, set)):
        return ";".join(map(str, v))
    if isinstance(v, dict):
        return str(v)
    return v


def make_storable(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """GeoPackage cannot store list/dict cells; flatten them to strings."""
    gdf = gdf.copy()
    for col in gdf.columns:
        if col == gdf.geometry.name:
            continue
        if gdf[col].dtype == object:
            gdf[col] = gdf[col].map(_flatten)
    return gdf


class BaseCollector:
    name = "base"

    def __init__(self, cfg, raw_dir, refresh=False):
        self.cfg = cfg or {}
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh

    def cache_path(self, label, ext="gpkg"):
        return self.raw_dir / f"{self.name}_{label}.{ext}"

    def load_cache(self, label):
        path = self.cache_path(label)
        if path.exists() and not self.refresh:
            log.info("[%s] using cached %s", self.name, path.name)
            return gpd.read_file(path)
        return None

    def save_cache(self, gdf, label):
        if gdf is None or gdf.empty:
            return
        make_storable(gdf).to_file(self.cache_path(label), driver="GPKG")

    @staticmethod
    def empty(crs="EPSG:4326"):
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=crs)
