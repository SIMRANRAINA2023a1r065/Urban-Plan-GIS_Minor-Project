"""Tiling for big areas (e.g. a whole district).

make_tiles : split the AOI into non-overlapping tile "cores" (each also has a slightly larger "fetch" polygon to download).
combine    : merge per-tile results into one dataset WITHOUT duplicates and WITHOUT cutting features at tile edges.
merge_graphs: union the per-tile road graphs.

How duplicates are avoided:
* point / building / road features are KEPT by exactly one tile: the tile whose cell contains the feature's centre
  (buildings and POIs: a representative point; roads: the midpoint of the line).
* land-use and boundary polygons can be huge and span many tiles, so every piece from every tile is kept and
  pieces with the same OSM id are re-joined (dissolved) into one polygon.
"""
import logging
import math
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

log = logging.getLogger(__name__)
POLYGON_LAYERS = {"landuse", "boundaries"}


def make_tiles(aoi_poly, tile_km=10, overlap_deg=0.001):
    """Return a list of tiles: {id, ix, iy, origin, step, core, fetch}. Cores partition the AOI exactly."""
    minx, miny, maxx, maxy = aoi_poly.bounds
    mid_lat = (miny + maxy) / 2
    dy = tile_km / 111.0
    dx = tile_km / (111.32 * math.cos(math.radians(mid_lat)))
    nx_ = max(1, math.ceil((maxx - minx) / dx - 1e-9))
    ny_ = max(1, math.ceil((maxy - miny) / dy - 1e-9))
    tiles = []
    for ix in range(nx_):
        for iy in range(ny_):
            cell = box(minx + ix * dx, miny + iy * dy, minx + (ix + 1) * dx, miny + (iy + 1) * dy)
            core = cell.intersection(aoi_poly)
            if core.is_empty or core.area <= 0:
                continue
            tiles.append({"id": f"t{ix:02d}_{iy:02d}", "ix": ix, "iy": iy,
                          "origin": (minx, miny), "step": (dx, dy),
                          "core": core, "fetch": core.buffer(overlap_deg)})
    return tiles


def owned(gdf, tile):
    """Keep only the features that belong to this tile (exactly one tile owns each feature)."""
    if gdf is None or gdf.empty:
        return gdf
    g = gdf.geometry
    pts = g.representative_point()
    xs, ys = pts.x.values.copy(), pts.y.values.copy()
    is_line = (g.geom_type == "LineString").values
    if is_line.any():
        with warnings.catch_warnings():   # midpoint by fraction is fine in lon/lat for deciding ownership
            warnings.simplefilter("ignore")
            mid = g[is_line].interpolate(0.5, normalized=True)
        xs[is_line], ys[is_line] = mid.x.values, mid.y.values
    (minx, miny), (dx, dy) = tile["origin"], tile["step"]
    ix = np.floor((xs - minx) / dx + 1e-9).astype(int)
    iy = np.floor((ys - miny) / dy + 1e-9).astype(int)
    return gdf[(ix == tile["ix"]) & (iy == tile["iy"])]


def _concat(frames):
    frames = [f for f in frames if f is not None]
    if not frames:
        return None
    nonempty = [f for f in frames if not f.empty]
    if not nonempty:
        return frames[0]
    return gpd.GeoDataFrame(pd.concat(nonempty, ignore_index=True), geometry="geometry", crs="EPSG:4326")


def _drop_duplicate_ids(gdf):
    if gdf is None or gdf.empty or "source_id" not in gdf:
        return gdf
    dup = gdf["source_id"].notna() & gdf["source_id"].duplicated()
    return gdf[~dup].reset_index(drop=True)


def _rejoin(gdf):
    """Re-join polygon pieces that share an OSM id into one polygon."""
    if gdf is None or gdf.empty or "source_id" not in gdf:
        return gdf
    has_id = gdf["source_id"].notna()
    if not has_id.any():
        return gdf
    with_id = gdf[has_id].copy()
    with_id["geometry"] = with_id.geometry.make_valid()
    joined = with_id.dissolve(by="source_id", aggfunc="first").reset_index()[list(gdf.columns)]
    out = pd.concat([joined, gdf[~has_id]], ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs)


def combine(results):
    """results = [(tile, {layer: gdf or None}), ...]  ->  {layer: gdf or None}"""
    layers = {k for _, parts in results for k in parts}
    out = {}
    for layer in layers:
        frames = []
        for tile, parts in results:
            g = parts.get(layer)
            if g is None:
                continue
            frames.append(g if layer in POLYGON_LAYERS else owned(g, tile))
        merged = _concat(frames)
        if layer in POLYGON_LAYERS:
            out[layer] = _rejoin(merged)
        elif layer in ("buildings", "pois"):
            out[layer] = _drop_duplicate_ids(merged)
        else:  # roads: several segments share one OSM way id, so they are not de-duplicated by id
            out[layer] = merged
    return out


def merge_graphs(paths, out_path):
    """Union the per-tile road graphs into one GraphML. Returns True if the result is not empty."""
    if not paths:
        return False
    import networkx as nx
    import osmnx as ox
    G = nx.compose_all([ox.load_graphml(p) for p in paths])
    if len(G.nodes) == 0:
        return False
    ox.save_graphml(G, out_path)
    log.info("merged %d tile graphs: %d nodes, %d edges", len(paths), len(G.nodes), len(G.edges))
    return True
