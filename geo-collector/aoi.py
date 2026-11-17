"""Build the area of interest (AOI) from config: a bbox or a place name."""
import logging
import geopandas as gpd
from shapely.geometry import box

log = logging.getLogger(__name__)


def union(gs):
    return gs.union_all() if hasattr(gs, "union_all") else gs.unary_union


def build_aoi(aoi_cfg):
    """Return a one-row GeoDataFrame (EPSG:4326) describing the AOI."""
    bbox = aoi_cfg.get("bbox")
    place = aoi_cfg.get("place")
    if bbox:
        west, south, east, north = bbox
        geom = box(west, south, east, north)
        log.info("AOI from bbox %s", bbox)
        return gpd.GeoDataFrame({"name": ["bbox"]}, geometry=[geom], crs="EPSG:4326")
    if place:
        import osmnx as ox
        gdf = ox.geocode_to_gdf(place).to_crs("EPSG:4326")
        log.info("AOI from place '%s'", place)
        return gpd.GeoDataFrame({"name": [place]}, geometry=[union(gdf.geometry)], crs="EPSG:4326")
    raise ValueError("Set aoi.bbox or aoi.place in config.yaml")
