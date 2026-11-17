import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, Point, box

from collectors.rasters import dem_urls, worldcover_urls
from processing.enrich import (add_landcover, add_landuse, add_terrain, landcover_summary, slope_raster)
from processing.standardize import (standardize_boundaries, standardize_landuse, standardize_pois)


def _tif(path, arr, dtype="float32", nodata=None):
    h, w = arr.shape
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1, dtype=dtype, crs="EPSG:4326",
                       transform=from_origin(74.85, 32.71, 0.0005, 0.0005), nodata=nodata) as d:
        d.write(arr.astype(dtype), 1)


def test_standardize_pois_picks_first_category():
    g = gpd.GeoDataFrame({"osm_id": ["node/1", "node/2"], "amenity": ["school", None],
                          "highway": [None, "bus_stop"], "name": ["A", None]},
                         geometry=[Point(74.85, 32.70), Point(74.86, 32.70)], crs="EPSG:4326")
    out = standardize_pois(g)
    assert list(out["category"]) == ["amenity", "highway"] and list(out["type"]) == ["school", "bus_stop"]


def test_standardize_landuse_and_boundaries():
    g = gpd.GeoDataFrame({"landuse": ["residential", None], "natural": [None, "water"]},
                         geometry=[box(0, 0, 1, 1), box(2, 2, 3, 3)], crs="EPSG:4326")
    out = standardize_landuse(g)
    assert list(out["class"]) == ["residential", "water"]
    b = standardize_boundaries(gpd.GeoDataFrame({"admin_level": ["8"], "name": ["Jammu"]},
                                                geometry=[box(0, 0, 1, 1)], crs="EPSG:4326"))
    assert b.loc[0, "admin_level"] == 8


def test_slope_and_sampling(tmp_path):
    ramp = np.tile(np.arange(40, dtype="float32") * 5.0, (40, 1))   # rises east, 5 m per pixel
    dem, slope = tmp_path / "dem.tif", tmp_path / "slope.tif"
    _tif(dem, ramp)
    slope_raster(dem, slope)
    pts = gpd.GeoDataFrame(geometry=[Point(74.86, 32.70)], crs="EPSG:4326")
    out = add_terrain(pts, dem, slope)
    assert out.loc[0, "elevation_m"] > 0 and 5 < out.loc[0, "slope_deg"] < 20


def test_landcover_and_landuse_join(tmp_path):
    lc = tmp_path / "lc.tif"
    _tif(lc, np.full((40, 40), 50), dtype="uint8", nodata=0)
    b = gpd.GeoDataFrame(geometry=[box(74.86, 32.70, 74.8605, 32.7005)], crs="EPSG:4326")
    assert add_landcover(b, lc).loc[0, "landcover"] == "built_up"
    area = box(74.855, 32.695, 74.87, 32.71)
    assert landcover_summary(lc, area) == {"built_up": 100.0}
    lu = gpd.GeoDataFrame({"class": ["residential"]}, geometry=[box(74.85, 32.69, 74.88, 32.72)], crs="EPSG:4326")
    assert add_landuse(b, lu).loc[0, "landuse"] == "residential"


def test_tile_urls():
    assert dem_urls((74.85, 32.70, 74.90, 32.75))[0].endswith("Copernicus_DSM_COG_10_N32_00_E074_00_DEM.tif")
    assert worldcover_urls((74.85, 32.70, 74.90, 32.75))[0].endswith("v200_N30E072_Map.tif")
    assert len(dem_urls((74.5, 32.5, 75.5, 33.5))) == 4
