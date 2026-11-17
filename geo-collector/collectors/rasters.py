"""Terrain + land-cover rasters, clipped to the AOI.

DEM        : Copernicus GLO-30 (30 m) from the public AWS bucket
Land cover : ESA WorldCover 2021 v200 (10 m) from the public AWS bucket
Both can instead be read from a local file you download yourself (config rasters.*_path).
Remote URL patterns are the public bucket layouts as I know them - if a download fails,
download the tile manually and set the local path in config.yaml.
"""
import logging
import math
from pathlib import Path

import rasterio
from rasterio.merge import merge

from .base import BaseCollector

log = logging.getLogger(__name__)
BUFFER = 0.002  # degrees of margin around the AOI


def _ns(v):
    return f"{'N' if v >= 0 else 'S'}{abs(v):02d}"


def _ew(v):
    return f"{'E' if v >= 0 else 'W'}{abs(v):03d}"


def dem_urls(bounds):
    w, s, e, n = bounds
    urls = []
    for lat in range(math.floor(s), math.floor(n - 1e-9) + 1):
        for lon in range(math.floor(w), math.floor(e - 1e-9) + 1):
            tile = f"Copernicus_DSM_COG_10_{_ns(lat)}_00_{_ew(lon)}_00_DEM"
            urls.append(f"https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif")
    return urls


def worldcover_urls(bounds):
    w, s, e, n = bounds
    urls = []
    for lat in range(math.floor(s / 3) * 3, math.floor((n - 1e-9) / 3) * 3 + 1, 3):
        for lon in range(math.floor(w / 3) * 3, math.floor((e - 1e-9) / 3) * 3 + 1, 3):
            urls.append("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
                        f"ESA_WorldCover_10m_2021_v200_{_ns(lat)}{_ew(lon)}_Map.tif")
    return urls


class RasterCollector(BaseCollector):
    name = "raster"

    def _mosaic(self, sources, bounds, out_path):
        srcs = []
        try:
            for s in sources:
                srcs.append(rasterio.open(s))
            arr, transform = merge(srcs, bounds=bounds)
            profile = dict(driver="GTiff", height=arr.shape[1], width=arr.shape[2], count=arr.shape[0],
                           dtype=arr.dtype, crs=srcs[0].crs, transform=transform,
                           nodata=srcs[0].nodata, compress="deflate")
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(arr)
        finally:
            for s in srcs:
                s.close()
        return out_path

    def _get(self, label, local_path, urls, aoi_bounds):
        out = self.cache_path(label, "tif")
        if out.exists() and not self.refresh:
            log.info("[raster] using cached %s", out.name)
            return out
        w, s, e, n = aoi_bounds
        bounds = (w - BUFFER, s - BUFFER, e + BUFFER, n + BUFFER)
        if local_path and Path(local_path).exists():
            log.info("[raster] reading %s from local file %s", label, local_path)
            return self._mosaic([str(local_path)], bounds, out)
        log.info("[raster] downloading %s from %d remote tile(s) ...", label, len(urls))
        return self._mosaic(urls, bounds, out)

    def fetch_dem(self, aoi_poly):
        b = aoi_poly.bounds
        return self._get("dem", self.cfg.get("dem_path"), dem_urls((b[0] - BUFFER, b[1] - BUFFER, b[2] + BUFFER, b[3] + BUFFER)), b)

    def fetch_landcover(self, aoi_poly):
        b = aoi_poly.bounds
        return self._get("landcover", self.cfg.get("landcover_path"),
                         worldcover_urls((b[0] - BUFFER, b[1] - BUFFER, b[2] + BUFFER, b[3] + BUFFER)), b)
