"""Geometry cleaning, de-duplication and the building merge rule."""
import logging

import geopandas as gpd
import pandas as pd

log = logging.getLogger(__name__)


def _empty_like(gdf):
    return gdf.iloc[0:0].copy()


def clean(gdf, aoi_poly, metric_crs, kind="buildings", min_area_m2=10.0):
    """Fix geometry, keep only the right geometry type, clip to AOI, drop duplicates."""
    if gdf is None or gdf.empty:
        return gdf
    n0 = len(gdf)
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)

    wanted = {"buildings": ["Polygon"], "polygons": ["Polygon"],
              "roads": ["LineString"], "points": ["Point"]}[kind]
    gdf = gdf[gdf.geometry.type.isin(wanted)]
    if gdf.empty:
        return gdf

    aoi = gpd.GeoDataFrame(geometry=[aoi_poly], crs="EPSG:4326").to_crs(gdf.crs)
    gdf = gpd.clip(gdf, aoi).explode(index_parts=False).reset_index(drop=True)
    gdf = gdf[gdf.geometry.type.isin(wanted)]

    if kind == "buildings":
        gdf = gdf[gdf.to_crs(metric_crs).area >= min_area_m2]
    gdf = gdf[~gdf.geometry.normalize().to_wkb().duplicated()].reset_index(drop=True)
    log.info("clean(%s): %d -> %d features", kind, n0, len(gdf))
    return gdf


def merge_buildings(osm, ob, metric_crs, overlap_threshold=0.5):
    """Keep every OSM footprint; add an Open Buildings footprint only if less than
    `overlap_threshold` of its area is already covered by OSM."""
    parts = [g for g in (osm, ob) if g is not None and not g.empty]
    if not parts:
        return osm
    if ob is None or ob.empty:
        return osm.reset_index(drop=True)
    if osm is None or osm.empty:
        return ob.reset_index(drop=True)

    osm_m = osm.to_crs(metric_crs).reset_index(drop=True)
    ob_m = ob.to_crs(metric_crs).reset_index(drop=True)
    pairs = gpd.sjoin(ob_m[["geometry"]], osm_m[["geometry"]], how="inner", predicate="intersects")
    covered = set()
    if not pairs.empty:
        a = gpd.GeoSeries(ob_m.geometry.loc[pairs.index].values, crs=metric_crs)
        b = gpd.GeoSeries(osm_m.geometry.loc[pairs["index_right"]].values, crs=metric_crs)
        inter = pd.Series(a.intersection(b, align=False).area.values, index=pairs.index)
        frac = inter.groupby(level=0).sum() / ob_m.area.loc[inter.index.unique()]
        covered = set(frac[frac >= overlap_threshold].index)
    keep = ob.reset_index(drop=True).loc[[i for i in range(len(ob)) if i not in covered]]
    log.info("merge: %d OSM + %d of %d Open Buildings kept", len(osm), len(keep), len(ob))
    merged = pd.concat([osm, keep], ignore_index=True)
    return gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")


def add_metrics(gdf, metric_crs, kind="buildings"):
    if gdf is None or gdf.empty:
        return gdf
    gdf = gdf.copy()
    m = gdf.to_crs(metric_crs)
    if kind == "buildings":
        gdf["area_m2"] = m.area.round(1)
        gdf.insert(0, "id", [f"B{i:06d}" for i in range(1, len(gdf) + 1)])
    else:
        gdf["length_m"] = m.length.round(1)
        gdf.insert(0, "id", [f"R{i:06d}" for i in range(1, len(gdf) + 1)])
    return gdf
