"""Add terrain, land-cover and land-use attributes to buildings/roads; raster summaries."""
import logging
import math

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.mask

log = logging.getLogger(__name__)

WORLDCOVER = {10: "tree_cover", 20: "shrubland", 30: "grassland", 40: "cropland", 50: "built_up",
              60: "bare_sparse", 70: "snow_ice", 80: "water", 90: "wetland", 95: "mangroves", 100: "moss_lichen"}


def slope_raster(dem_path, out_path):
    """Slope in degrees from a DEM (handles geographic or projected CRS)."""
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype("float32")
        if src.nodata is not None:
            dem[dem == src.nodata] = np.nan
        a, e = abs(src.transform.a), abs(src.transform.e)
        if src.crs and src.crs.is_geographic:
            lat = (src.bounds.top + src.bounds.bottom) / 2
            dx, dy = a * 111320 * math.cos(math.radians(lat)), e * 110540
        else:
            dx, dy = a, e
        gy, gx = np.gradient(dem, dy, dx)
        slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")
        slope[np.isnan(slope)] = -9999
        profile = src.profile.copy()
        profile.update(dtype="float32", nodata=-9999, count=1, compress="deflate")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(slope, 1)
    return out_path


def _points(gdf):
    g = gdf.geometry
    if g.iloc[0].geom_type in ("LineString", "MultiLineString"):
        return g.interpolate(0.5, normalized=True)
    return g.representative_point()


def sample_raster(path, gdf):
    """Sample band 1 at a representative point of each feature (NaN where no data)."""
    with rasterio.open(path) as src:
        pts = _points(gdf).to_crs(src.crs)
        vals = np.array([v[0] for v in src.sample(zip(pts.x, pts.y))], dtype="float64")
        if src.nodata is not None:
            vals[vals == src.nodata] = np.nan
    return vals


def add_terrain(gdf, dem_path, slope_path):
    if gdf is None or gdf.empty:
        return gdf
    gdf = gdf.copy()
    gdf["elevation_m"] = np.round(sample_raster(dem_path, gdf), 1)
    gdf["slope_deg"] = np.round(sample_raster(slope_path, gdf), 1)
    return gdf


def add_landcover(gdf, lc_path):
    if gdf is None or gdf.empty:
        return gdf
    gdf = gdf.copy()
    codes = sample_raster(lc_path, gdf)
    gdf["landcover"] = [WORLDCOVER.get(int(c)) if c == c else None for c in codes]
    return gdf


def add_landuse(buildings, landuse):
    """Tag each building with the OSM land-use polygon its centre falls in."""
    if buildings is None or buildings.empty:
        return buildings
    buildings = buildings.copy()
    buildings["landuse"] = None
    if landuse is None or landuse.empty or "class" not in landuse:
        return buildings
    pts = gpd.GeoDataFrame(geometry=buildings.geometry.representative_point(), crs=buildings.crs)
    j = gpd.sjoin(pts, landuse[["class", "geometry"]].to_crs(buildings.crs), predicate="within", how="left")
    j = j[~j.index.duplicated(keep="first")]
    buildings["landuse"] = j["class"].reindex(buildings.index).values
    return buildings


def landcover_summary(lc_path, aoi_poly):
    with rasterio.open(lc_path) as src:
        arr, _ = rasterio.mask.mask(src, [aoi_poly.__geo_interface__], crop=True, nodata=0, all_touched=True)
    vals, counts = np.unique(arr[arr > 0], return_counts=True)
    total = max(int(counts.sum()), 1)
    return {WORLDCOVER.get(int(v), str(int(v))): round(100 * int(c) / total, 1) for v, c in zip(vals, counts)}
