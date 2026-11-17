import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Polygon, box

from aoi import build_aoi, union
from processing.clean import add_metrics, clean, merge_buildings
from processing.quality import coverage
from processing.standardize import (standardize_open_buildings,
                                    standardize_osm_buildings, standardize_osm_roads)

AOI = box(74.85, 32.70, 74.86, 32.71)
METRIC = "EPSG:32643"


def sq(x, y, d=0.0002):
    return box(x, y, x + d, y + d)


def osm_raw():
    return gpd.GeoDataFrame(
        {"osm_id": ["way/1", "way/2"], "building": ["yes", "house"],
         "building:levels": ["2", None], "height": ["7.5 m", None]},
        geometry=[sq(74.851, 32.701), sq(74.855, 32.705)], crs="EPSG:4326")


def test_standardize_osm_buildings():
    b = standardize_osm_buildings(osm_raw())
    assert list(b["class"]) == ["building", "house"]
    assert b.loc[0, "levels"] == 2 and b.loc[0, "height_m"] == 7.5
    assert b.crs.to_epsg() == 4326


def test_standardize_roads_handles_lists_and_missing():
    r = gpd.GeoDataFrame({"osmid": ["10;11"], "highway": ["residential;service"], "maxspeed": ["30 mph"],
                          "lanes": ["2"], "oneway": [True]},
                         geometry=[LineString([(74.851, 32.701), (74.856, 32.706)])], crs="EPSG:4326")
    out = standardize_osm_roads(r)
    assert out.loc[0, "class"] == "residential" and out.loc[0, "lanes"] == 2
    assert bool(out.loc[0, "oneway"]) is True


def test_clean_fixes_invalid_dedupes_and_filters_small():
    bowtie = Polygon([(74.851, 32.701), (74.8512, 32.7012), (74.8512, 32.701), (74.851, 32.7012)])
    tiny = sq(74.852, 32.702, 0.000001)
    g = gpd.GeoDataFrame({"source": ["osm"] * 4}, geometry=[bowtie, sq(74.853, 32.703), sq(74.853, 32.703), tiny],
                         crs="EPSG:4326")
    out = clean(g, AOI, METRIC, "buildings", min_area_m2=10)
    assert out.geometry.is_valid.all()
    assert len(out) == 3  # bowtie splits into 2 triangles + 1 unique square; duplicate and tiny removed
    assert not out.geometry.normalize().to_wkb().duplicated().any()


def test_merge_keeps_osm_and_adds_only_uncovered_open_buildings():
    osm = standardize_osm_buildings(osm_raw())
    ob_raw = gpd.GeoDataFrame({"confidence": [0.9, 0.9]},
                              geometry=[sq(74.851, 32.701), sq(74.8575, 32.7075)], crs="EPSG:4326")
    ob = standardize_open_buildings(ob_raw)
    merged = merge_buildings(osm, ob, METRIC, 0.5)
    assert len(merged) == 3
    assert (merged["source"] == "open_buildings").sum() == 1


def test_merge_with_empty_open_buildings():
    osm = standardize_osm_buildings(osm_raw())
    assert len(merge_buildings(osm, standardize_open_buildings(None), METRIC)) == 2


def test_coverage_report_flags_empty_cells():
    osm = add_metrics(standardize_osm_buildings(osm_raw()), METRIC, "buildings")
    roads = add_metrics(standardize_osm_roads(gpd.GeoDataFrame(
        {"highway": ["primary"]}, geometry=[LineString([(74.8505, 32.7005), (74.8595, 32.7005)])],
        crs="EPSG:4326")), METRIC, "roads")
    grid, summary = coverage(osm, roads, AOI, METRIC, size=300)
    assert summary["buildings_total"] == 2
    assert summary["road_km_total"] > 0.5
    assert "empty_cell" in grid.columns and summary["cells"] == len(grid)


def test_bbox_aoi():
    g = build_aoi({"bbox": [74.8, 32.6, 74.9, 32.7]})
    assert g.crs.to_epsg() == 4326 and union(g.geometry).bounds == (74.8, 32.6, 74.9, 32.7)
