"""Map every source to ONE schema so the data can be merged and used downstream.

Buildings: source, source_id, class, levels, height_m, confidence, geometry
Roads:     source, source_id, class, name, lanes, maxspeed_kmh, oneway, geometry
All outputs are EPSG:4326.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

BUILDING_COLS = ["source", "source_id", "class", "levels", "height_m", "confidence", "geometry"]
ROAD_COLS = ["source", "source_id", "class", "name", "lanes", "maxspeed_kmh", "oneway", "geometry"]


def _col(gdf, name):
    return gdf[name] if name in gdf.columns else pd.Series(np.nan, index=gdf.index)


def _num(series):
    """First number found in a messy string like '12 m', '30;50', '5.5'."""
    return pd.to_numeric(series.astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")


def _first(series):
    return series.astype(object).where(series.notna(), None).map(
        lambda v: str(v).split(";")[0] if v is not None else None)


def _finish(gdf, cols):
    out = gpd.GeoDataFrame(gdf[[c for c in cols if c != "geometry"]], geometry=gdf.geometry, crs=gdf.crs)
    return out.to_crs("EPSG:4326")


def standardize_osm_buildings(gdf):
    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame({c: [] for c in BUILDING_COLS if c != "geometry"},
                                geometry=[], crs="EPSG:4326")
    out = gdf.copy()
    out["source"] = "osm"
    out["source_id"] = _col(out, "osm_id")
    cls = _first(_col(out, "building"))
    out["class"] = cls.where(cls != "yes", "building").fillna("building")
    out["levels"] = _num(_col(out, "building:levels"))
    out["height_m"] = _num(_col(out, "height"))
    out["confidence"] = np.nan
    return _finish(out, BUILDING_COLS)


def standardize_open_buildings(gdf):
    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame({c: [] for c in BUILDING_COLS if c != "geometry"},
                                geometry=[], crs="EPSG:4326")
    out = gdf.copy()
    out["source"] = "open_buildings"
    out["source_id"] = None
    out["class"] = "building"
    out["levels"] = np.nan
    out["height_m"] = np.nan
    out["confidence"] = pd.to_numeric(_col(out, "confidence"), errors="coerce")
    return _finish(out, BUILDING_COLS)


def standardize_osm_roads(gdf):
    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame({c: [] for c in ROAD_COLS if c != "geometry"},
                                geometry=[], crs="EPSG:4326")
    out = gdf.copy()
    out["source"] = "osm"
    out["source_id"] = _first(_col(out, "osmid"))
    out["class"] = _first(_col(out, "highway"))
    out["name"] = _first(_col(out, "name"))
    out["lanes"] = _num(_col(out, "lanes"))
    out["maxspeed_kmh"] = _num(_col(out, "maxspeed"))
    ow = _col(out, "oneway").astype(str).str.lower()
    out["oneway"] = ow.isin(["true", "yes", "1"])
    return _finish(out, ROAD_COLS)


POI_KEYS = ["amenity", "shop", "public_transport", "railway", "highway", "tourism", "healthcare"]


def _empty(cols):
    return gpd.GeoDataFrame({c: [] for c in cols if c != "geometry"}, geometry=[], crs="EPSG:4326")


def standardize_pois(gdf):
    """Points of interest: source, source_id, category (OSM key), type (OSM value), name."""
    cols = ["source", "source_id", "category", "type", "name", "geometry"]
    if gdf is None or gdf.empty:
        return _empty(cols)
    out = gdf.copy()
    out["category"], out["type"] = None, None
    for key in POI_KEYS:
        if key not in out.columns:
            continue
        free = out["category"].isna() & out[key].notna()
        out.loc[free, "category"] = key
        out.loc[free, "type"] = out.loc[free, key].astype(str)
    out["source"] = "osm"
    out["source_id"] = _col(out, "osm_id")
    out["name"] = _col(out, "name")
    return _finish(out[out["category"].notna()], cols)


def standardize_landuse(gdf):
    """Land use / natural / leisure polygons: source, source_id, class_key, class, name."""
    cols = ["source", "source_id", "class_key", "class", "name", "geometry"]
    if gdf is None or gdf.empty:
        return _empty(cols)
    out = gdf.copy()
    out["class_key"], out["class"] = None, None
    for key in ["landuse", "natural", "leisure"]:
        if key not in out.columns:
            continue
        free = out["class"].isna() & out[key].notna()
        out.loc[free, "class_key"] = key
        out.loc[free, "class"] = out.loc[free, key].astype(str)
    out["source"] = "osm"
    out["source_id"] = _col(out, "osm_id")
    out["name"] = _col(out, "name")
    return _finish(out[out["class"].notna()], cols)


def standardize_boundaries(gdf):
    """Administrative boundaries: source, source_id, admin_level, name."""
    cols = ["source", "source_id", "admin_level", "name", "geometry"]
    if gdf is None or gdf.empty:
        return _empty(cols)
    out = gdf.copy()
    out["source"] = "osm"
    out["source_id"] = _col(out, "osm_id")
    out["admin_level"] = pd.to_numeric(_col(out, "admin_level"), errors="coerce")
    out["name"] = _col(out, "name")
    return _finish(out, cols)
