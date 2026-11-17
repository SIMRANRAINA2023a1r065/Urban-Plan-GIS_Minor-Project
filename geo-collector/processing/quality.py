"""Coverage report: where do we have buildings/roads, and where are the gaps?"""
import json
import logging

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from shapely.geometry import box

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

log = logging.getLogger(__name__)


def make_grid(aoi_poly, metric_crs, size):
    area = gpd.GeoSeries([aoi_poly], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
    minx, miny, maxx, maxy = area.bounds
    cells = [box(x, y, x + size, y + size)
             for x in np.arange(minx, maxx, size) for y in np.arange(miny, maxy, size)]
    grid = gpd.GeoDataFrame(geometry=cells, crs=metric_crs)
    grid = grid[grid.intersects(area)].reset_index(drop=True)
    grid["cell_id"] = grid.index
    return grid


def coverage(buildings, roads, aoi_poly, metric_crs, size=500):
    grid = make_grid(aoi_poly, metric_crs, size)

    b_cols = ["n_buildings_osm", "n_buildings_open_buildings"]
    if buildings is not None and not buildings.empty:
        pts = buildings.to_crs(metric_crs).copy()
        pts["geometry"] = pts.geometry.representative_point()
        j = gpd.sjoin(pts[["source", "geometry"]], grid[["cell_id", "geometry"]], predicate="within")
        counts = j.groupby(["cell_id", "source"]).size().unstack(fill_value=0)
        counts.columns = [f"n_buildings_{c}" for c in counts.columns]
        grid = grid.merge(counts, left_on="cell_id", right_index=True, how="left")
    for c in b_cols:
        if c not in grid:
            grid[c] = 0
    grid[b_cols] = grid[b_cols].fillna(0).astype(int)
    grid["n_buildings"] = grid[b_cols].sum(axis=1)

    grid["road_km"] = 0.0
    if roads is not None and not roads.empty:
        seg = gpd.overlay(roads.to_crs(metric_crs)[["geometry"]], grid[["cell_id", "geometry"]],
                          how="intersection", keep_geom_type=True)
        km = (seg.length / 1000).groupby(seg["cell_id"]).sum()
        grid["road_km"] = grid["cell_id"].map(km).fillna(0.0).round(3)

    grid["no_buildings"] = grid["n_buildings"] == 0
    grid["no_roads"] = grid["road_km"] == 0
    grid["empty_cell"] = grid["no_buildings"] & grid["no_roads"]

    n = max(len(grid), 1)
    summary = {
        "cells": int(len(grid)), "cell_size_m": size,
        "buildings_total": int(grid["n_buildings"].sum()),
        "buildings_osm": int(grid["n_buildings_osm"].sum()),
        "buildings_open_buildings": int(grid["n_buildings_open_buildings"].sum()),
        "road_km_total": round(float(grid["road_km"].sum()), 2),
        "pct_cells_without_buildings": round(100 * grid["no_buildings"].sum() / n, 1),
        "pct_cells_without_roads": round(100 * grid["no_roads"].sum() / n, 1),
        "pct_cells_empty": round(100 * grid["empty_cell"].sum() / n, 1),
    }
    return grid.to_crs("EPSG:4326"), summary


def plot_coverage(grid, path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    grid.plot(column="n_buildings", cmap="YlOrRd", legend=True, ax=axes[0], edgecolor="grey", linewidth=0.2)
    axes[0].set_title("Buildings per cell")
    grid.plot(column="road_km", cmap="Blues", legend=True, ax=axes[1], edgecolor="grey", linewidth=0.2)
    axes[1].set_title("Road length (km) per cell")
    empty = grid[grid["empty_cell"]]
    if not empty.empty:
        for ax in axes:
            empty.boundary.plot(ax=ax, color="red", linewidth=0.8)
    for ax in axes:
        ax.set_axis_off()
    fig.suptitle("Coverage report (red outline = no data at all)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_summary(summary, status, path):
    with open(path, "w") as f:
        json.dump({"summary": summary, "source_status": status}, f, indent=2)
